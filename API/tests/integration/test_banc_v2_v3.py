"""
test_banc_v2_v3.py — Banc « base neuve = base migrée » (chantier BAN).

============================================================================
POURQUOI
============================================================================
Chaque changement du schéma passe par DEUX chemins : docker/init-v3/ (une
base neuve) et docker/migrations/v2-vers-v3/ (une base v2 qui existe
déjà). Ce test vérifie que les deux mènent au même endroit, à chaque
pytest : un écart casse la suite au lieu de passer inaperçu.

CE QU'IL FAIT
  1. recrée deux bases jetables sur le serveur de DATABASE_URL :
     cmp_v2_migree (les *.sql de init-v2/, puis ceux de v2-vers-v3/) et
     cmp_v3_neuve (les *.sql de init-v3/), chaque dossier par ordre de nom,
     octet par octet, comme docker-entrypoint-initdb.d ;
  2. joue chaque fichier avec le vrai `psql` (ON_ERROR_STOP=1) : deux
     d'entre eux exigent psql (\\getenv, \\if, \\gset, \\gexec) ;
  3. décrit chaque base en lignes triées — colonnes (nom, type, nullable,
     défaut), contraintes, index, triggers, fonctions, et le nombre de
     lignes par table, hors tables de démo ;
  4. échoue en montrant le diff si les deux descriptions diffèrent ;
     supprime ses deux bases dans tous les cas.

PAS DE `pg_dump -s` : ADD COLUMN met la colonne en dernier, le CREATE TABLE
de v3 ailleurs — le diff serait faux. La description ignore cet ordre.

LE RÔLE fil_rouge_reader est commun à tout le serveur. init-v3/04 et
migrations/12 lui ôtent la connexion (NOLOGIN) quand POSTGRES_READER_PASSWORD
est vide, et le conteneur api ne l'a pas. Le test note donc son état (droit
de connexion, empreinte du mot de passe) avant de jouer les fichiers, et le
remet à la fin (choix A de Sébastien, 14/10/2026).

DOSSIERS : BANC_V2_DIR, BANC_V3_DIR, BANC_MIG_DIR (par défaut les montages
/api/sql/… du conteneur api, docker-compose.yml). Absents : test sauté. Les
mutants jouent sur une copie, jamais sur ces dossiers :
    BANC_V3_DIR=/tmp/v3-mutant python -m pytest -q tests/integration/test_banc_v2_v3.py

TABLES DE DÉMO : BANC_DEMO_TABLES (noms séparés par des espaces) remplace la
liste ; vide, toutes les tables sont comptées.

LANCER depuis docker/ : `bash compare_v2_v3.sh`, ou la commande pytest
ci-dessus dans le conteneur api.
============================================================================
"""

import difflib
import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from src.app.conf.database import DATABASE_URL

from .conftest import TEST_DB

V2_DIR = Path(os.getenv("BANC_V2_DIR", "/api/sql/init-v2"))
V3_DIR = Path(os.getenv("BANC_V3_DIR", "/api/sql/init-v3"))
MIG_DIR = Path(os.getenv("BANC_MIG_DIR", "/api/sql/v2-vers-v3"))

V2_DB = "cmp_v2_migree"
V3_DB = "cmp_v3_neuve"

# Tables de démo, dont on ne compte pas les lignes (leur schéma reste comparé) :
# - estate_contact : 2 469 contacts de démo, remplis par
#   init-v3/06_populate_estate_contact.sql ; aucune migration ne pousse de
#   faux contacts dans une base réelle (ADR-054).
DEMO_TABLES = os.getenv("BANC_DEMO_TABLES", "estate_contact").split()

READER_ROLE = "fil_rouge_reader"

# Description triée d'une base, une ligne par fait (reprise telle quelle du
# script compare_v2_v3.sh d'avant BAN3).
DESCRIBE_SQL = r"""
WITH tbl AS (
    SELECT c.oid, n.nspname, c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname NOT LIKE 'pg\_toast%'
      AND n.nspname NOT LIKE 'pg\_temp%'
)
SELECT ligne FROM (
    -- colonnes : nom, type, nullable, défaut — l'ordre des colonnes est ignoré
    SELECT format('colonne %s.%s.%s %s%s%s%s%s',
                  t.nspname, t.relname, a.attname,
                  format_type(a.atttypid, a.atttypmod),
                  CASE WHEN a.attnotnull THEN ' NOT NULL' ELSE ' NULL' END,
                  ' DEFAULT ' || pg_get_expr(d.adbin, d.adrelid),
                  CASE a.attidentity WHEN 'a' THEN ' IDENTITY ALWAYS'
                                     WHEN 'd' THEN ' IDENTITY BY DEFAULT' END,
                  CASE a.attgenerated WHEN 's' THEN ' GENERATED' END) AS ligne
    FROM tbl t
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum > 0 AND NOT a.attisdropped
    LEFT JOIN pg_attrdef d ON d.adrelid = t.oid AND d.adnum = a.attnum
    UNION ALL
    -- contraintes : nom et définition
    SELECT format('contrainte %s.%s %s %s', t.nspname, t.relname,
                  co.conname, pg_get_constraintdef(co.oid))
    FROM tbl t
    JOIN pg_constraint co ON co.conrelid = t.oid
    UNION ALL
    -- index (ceux des clés et des UNIQUE compris)
    SELECT format('index %s.%s %s', i.schemaname, i.indexname, i.indexdef)
    FROM pg_indexes i
    WHERE i.schemaname NOT IN ('pg_catalog', 'information_schema')
    UNION ALL
    -- triggers posés par le schéma (pas ceux internes aux clés étrangères)
    SELECT format('trigger %s.%s %s', t.nspname, t.relname, pg_get_triggerdef(tg.oid))
    FROM tbl t
    JOIN pg_trigger tg ON tg.tgrelid = t.oid AND NOT tg.tgisinternal
    UNION ALL
    -- fonctions du schéma, hors celles des extensions (btree_gist)
    SELECT format('fonction %s.%s(%s) %s', n.nspname, p.proname,
                  pg_get_function_identity_arguments(p.oid),
                  regexp_replace(pg_get_functiondef(p.oid), '\s+', ' ', 'g'))
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND p.prokind IN ('f', 'p')
      AND NOT EXISTS (SELECT 1 FROM pg_depend dep
                      WHERE dep.classid = 'pg_proc'::regclass
                        AND dep.objid = p.oid AND dep.deptype = 'e')
    UNION ALL
    -- nombre de lignes par table
    SELECT format('lignes %s.%s %s', t.nspname, t.relname,
                  (xpath('/row/n/text()',
                         query_to_xml(format('SELECT count(*) AS n FROM %I.%I',
                                             t.nspname, t.relname),
                                      false, true, '')))[1]::text)
    FROM tbl t
) faits
ORDER BY ligne COLLATE "C";
"""


def psql_env() -> dict[str, str]:
    """Connexion de psql : celle de DATABASE_URL, par les variables PG*."""
    url = make_url(DATABASE_URL)
    env = dict(os.environ)
    env.update(
        PGHOST=url.host or "localhost",
        PGPORT=str(url.port or 5432),
        PGUSER=url.username or "postgres",
        PGPASSWORD=url.password or "",
        # Les NOTICE (« extension already exists »…) sont coupés ; les erreurs restent.
        PGOPTIONS="-c client_min_messages=warning",
    )
    return env


def psql(database: str, sql: str, *variables: str) -> str:
    """Joue `sql` (lu sur l'entrée standard) dans `database`, rend la sortie brute."""
    args = ["psql", "-X", "-q", "-tA", "-v", "ON_ERROR_STOP=1", "-d", database]
    for variable in variables:
        args += ["-v", variable]
    result = subprocess.run(args, input=sql, capture_output=True, text=True, env=psql_env())
    if result.returncode != 0:
        raise RuntimeError(f"psql a échoué dans {database} :\n{result.stderr}")
    return result.stdout


def sql_files(folder: Path) -> list[Path]:
    """Les *.sql du dossier, par nom, octet par octet (LC_ALL=C), comme l'entrypoint."""
    return sorted(folder.glob("*.sql"), key=lambda path: path.name.encode())


def load(database: str, files: list[Path]) -> None:
    psql("postgres", f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE);')
    psql("postgres", f'CREATE DATABASE "{database}";')
    for path in files:
        try:
            psql(database, path.read_text(encoding="utf-8"))
        except RuntimeError as error:
            raise RuntimeError(f"ÉCHEC du chargement : {path}") from error


def describe(database: str) -> list[str]:
    """Description triée, sans le nombre de lignes des tables de démo."""
    demo = re.compile(
        r"^lignes [^ ]*\.(" + "|".join(map(re.escape, DEMO_TABLES)) + r") "
    ) if DEMO_TABLES else None
    lines = psql(database, DESCRIBE_SQL).splitlines()
    return [line for line in lines if not (demo and demo.match(line))]


@pytest.fixture
def banc_databases() -> Iterator[None]:
    """
    Les deux bases jetables, supprimées à la fin quoi qu'il arrive, et le
    rôle fil_rouge_reader remis dans l'état noté avant le test.
    """
    for folder in (V2_DIR, V3_DIR, MIG_DIR):
        if not sql_files(folder):
            pytest.skip(f"Banc v2/v3 : aucun .sql dans {folder} (montages de docker-compose.yml).")
    if shutil.which("psql") is None:
        pytest.skip("Banc v2/v3 : psql absent (postgresql-client, API/Dockerfile).")

    # Garde-fou : ce test efface les bases qu'il vise.
    dev_db = make_url(DATABASE_URL).database
    for database in (V2_DB, V3_DB):
        if database in ("fil_rouge_immobilier", "fil_rouge_test", dev_db, TEST_DB):
            raise RuntimeError(f"Refusé : {database} est la base de développement ou de test.")

    try:
        reader = psql(
            "postgres",
            f"SELECT rolcanlogin, coalesce(rolpassword, '') FROM pg_authid "
            f"WHERE rolname = '{READER_ROLE}';",
        ).strip()
    except RuntimeError as error:
        pytest.skip(f"Banc v2/v3 : serveur PostgreSQL injoignable ({error}).")

    try:
        yield
    finally:
        for database in (V2_DB, V3_DB):
            psql("postgres", f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE);')
        restore_reader(reader)


def restore_reader(reader: str) -> None:
    """Remet fil_rouge_reader tel qu'il était : absent, ou son login et son mot de passe."""
    if not reader:
        psql("postgres", f"DROP ROLE IF EXISTS {READER_ROLE};")
        return
    can_login, password = reader.split("|", 1)
    login = "LOGIN" if can_login == "t" else "NOLOGIN"
    if password:
        # Une empreinte SCRAM est reconnue et gardée telle quelle par PostgreSQL.
        psql("postgres", f"ALTER ROLE {READER_ROLE} {login} PASSWORD :'password';", f"password={password}")
    else:
        psql("postgres", f"ALTER ROLE {READER_ROLE} {login} PASSWORD NULL;")


def test_new_database_equals_migrated_database(banc_databases: None):
    load(V2_DB, sql_files(V2_DIR) + sql_files(MIG_DIR))
    load(V3_DB, sql_files(V3_DIR))
    migrated = describe(V2_DB)
    new = describe(V3_DB)

    # Garde : une description vide ferait dire IDENTIQUES à un banc muet.
    assert migrated and new, f"Description vide : {V2_DB} {len(migrated)} lignes, {V3_DB} {len(new)} lignes."

    diff = list(difflib.unified_diff(migrated, new, fromfile=V2_DB, tofile=V3_DB, lineterm=""))
    assert not diff, (
        f"DIFFÉRENTES — {V2_DB} {len(migrated)} faits, {V3_DB} {len(new)} faits\n" + "\n".join(diff)
    )
