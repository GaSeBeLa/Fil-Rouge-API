#!/usr/bin/env bash
# ============================================================================
# compare_v2_v3.sh — Banc « base neuve = base migrée » (chantier LOT).
# ============================================================================
#
# POURQUOI : chaque fiche du lot change le schéma par DEUX chemins — dans
# init-v3/ (une base neuve) et dans migrations/v2-vers-v3/ (une base v2 qui
# existe déjà). Le banc vérifie que les deux chemins mènent au même endroit.
#
# CE QU'IL FAIT :
#   1. recrée cmp_v2_migree : les *.sql de init-v2/ (01, 02, 03), puis chaque
#      migrations/v2-vers-v3/*.sql, par ordre de nom ;
#   2. recrée cmp_v3_neuve : les *.sql de init-v3/ (01, 02, 03) ;
#      « tous les *.sql par ordre de nom » : comme docker-entrypoint-initdb.d ;
#   3. décrit chaque base en lignes triées — colonnes (nom, type, nullable,
#      défaut), contraintes (pg_get_constraintdef), index, triggers,
#      fonctions, et le nombre de lignes par table ;
#   4. rend IDENTIQUES et 0, ou le diff et 1 (2 : le banc n'a pas pu
#      conclure) ; supprime ses deux bases dans tous les cas.
#
# PAS DE `pg_dump -s` : ADD COLUMN met la colonne en dernier, le CREATE TABLE
# de v3 ailleurs — le diff serait faux. La description ignore cet ordre.
#
# Les fichiers passent par l'entrée standard (`psql < fichier`) : init-v2/
# n'est plus monté dans le conteneur depuis LOT1.
#
# DOSSIERS : V2_DIR, V3_DIR, MIG_DIR (par défaut les vrais, à côté de ce
# script). Les mutants jouent sur une copie temporaire, jamais sur ces
# dossiers :
#     V3_DIR=/tmp/v3-mutant bash docker/compare_v2_v3.sh
#
# LANCER (depuis n'importe où, conteneur `db` démarré) :
#     bash docker/compare_v2_v3.sh
#
# docker-compose.yml n'est pas modifié : on passe par `docker compose exec`.
# ============================================================================

set -euo pipefail
export LC_ALL=C   # ordre des *.sql : octet par octet, comme l'entrypoint

HERE="$(cd "$(dirname "$0")" && pwd)"
# Résolus depuis le dossier de l'appelant, avant le cd : un chemin relatif
# passé en variable garde son sens.
V2_DIR="$(cd "${V2_DIR:-$HERE/init-v2}" && pwd)"
V3_DIR="$(cd "${V3_DIR:-$HERE/init-v3}" && pwd)"
MIG_DIR="$(cd "${MIG_DIR:-$HERE/migrations/v2-vers-v3}" && pwd)"
cd "$HERE"   # docker compose lit docker-compose.yml ici

V2_DB="${CMP_V2_DB:-cmp_v2_migree}"
V3_DB="${CMP_V3_DB:-cmp_v3_neuve}"

# Garde-fou : ce script efface les bases qu'il vise.
for db in "$V2_DB" "$V3_DB"; do
    if [ "$db" = "fil_rouge_immobilier" ] || [ "$db" = "fil_rouge_test" ]; then
        echo "Refusé : $db est la base de développement ou de test." >&2
        exit 2
    fi
done

shopt -s nullglob
v2_files=("$V2_DIR"/*.sql)
mig_files=("$MIG_DIR"/*.sql)
v3_files=("$V3_DIR"/*.sql)
if [ ${#v2_files[@]} -eq 0 ] || [ ${#v3_files[@]} -eq 0 ]; then
    echo "Aucun .sql dans $V2_DIR ou $V3_DIR." >&2
    exit 2
fi

DESC_V2="$(mktemp)"
DESC_V3="$(mktemp)"

supprimer_bases() {
    docker compose exec -T db sh -c "
        export PGOPTIONS='-c client_min_messages=warning'
        dropdb --if-exists --force -U \"\$POSTGRES_USER\" $V2_DB
        dropdb --if-exists --force -U \"\$POSTGRES_USER\" $V3_DB
    " || echo "Attention : bases $V2_DB / $V3_DB non supprimées." >&2
    rm -f "$DESC_V2" "$DESC_V3"
}
trap supprimer_bases EXIT

# SQL lu sur l'entrée standard, exécuté dans la base $1. Les NOTICE
# (« extension already exists »…) sont coupés ; les erreurs restent.
psql_dans() {
    docker compose exec -T db sh -c "
        PGOPTIONS='-c client_min_messages=warning' \
        psql -X -q -tA -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d $1
    "
}

# Recrée la base $1, puis y charge les fichiers suivants, dans l'ordre.
recreer_et_charger() {
    local db="$1"; shift
    docker compose exec -T db sh -c "
        export PGOPTIONS='-c client_min_messages=warning'
        dropdb --if-exists --force -U \"\$POSTGRES_USER\" $db
        createdb -U \"\$POSTGRES_USER\" $db
    "
    local f
    for f in "$@"; do
        if ! psql_dans "$db" < "$f" > /dev/null; then
            echo "ÉCHEC du chargement : $f dans $db" >&2
            exit 2
        fi
    done
    echo "$db : ${#@} fichier(s) chargé(s)"
}

# Description triée de la base $1, une ligne par fait, écrite dans $2.
decrire() {
    psql_dans "$1" > "$2" <<'SQL'
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
SQL
}

recreer_et_charger "$V2_DB" "${v2_files[@]}" "${mig_files[@]}"
recreer_et_charger "$V3_DB" "${v3_files[@]}"
decrire "$V2_DB" "$DESC_V2"
decrire "$V3_DB" "$DESC_V3"

# Garde : une description vide ferait dire IDENTIQUES à un banc muet.
n_v2=$(wc -l < "$DESC_V2")
n_v3=$(wc -l < "$DESC_V3")
if [ "$n_v2" -eq 0 ] || [ "$n_v3" -eq 0 ]; then
    echo "GARDE : description vide ($V2_DB $n_v2 lignes, $V3_DB $n_v3 lignes)." >&2
    exit 2
fi

if diff -u --label "$V2_DB" --label "$V3_DB" "$DESC_V2" "$DESC_V3"; then
    echo "IDENTIQUES — $n_v2 faits comparés, ${SECONDS} s"
    exit 0
fi
echo "DIFFÉRENTES — $V2_DB $n_v2 faits, $V3_DB $n_v3 faits, ${SECONDS} s"
exit 1
