"""
Les clés étrangères vers les fiches visent leur numéro (fiche PRF2).

Décision de Seb du 2026-10-15 (chantier PRF) : id_client, id_hunter et
id_realestatemanager citent client(id), hunter(id), real_estate_manager(id),
plus id_user. Seules sept colonnes citent encore "user"(id) : les id_user
des trois fiches et les id_author de quatre tables.

On lit pg_constraint dans la base de test, créée par docker/init-v3/01 :
une REFERENCES … (id_user) remise dans 01 fait tomber le test. La migration
jumelle, docker/migrations/v2-vers-v3/45_cles-vers-les-fiches.sql, est
gardée alignée par le banc v2/v3.
"""

from sqlalchemy import text
from sqlmodel import Session

PROFILES = ("client", "hunter", "real_estate_manager")

# (table, colonne) -> table visée, colonne visée : les 11 FK vers les fiches.
PROFILE_FKS = {
    ("hunter", "id_realestatemanager"): ("real_estate_manager", "id"),
    ("search_request", "id_client"): ("client", "id"),
    ("search_request", "id_hunter"): ("hunter", "id"),
    ("search_request", "id_realestatemanager"): ("real_estate_manager", "id"),
    ("mandate", "id_client"): ("client", "id"),
    ("mandate", "id_hunter"): ("hunter", "id"),
    ("estate_searchrequest", "id_hunter"): ("hunter", "id"),
    ("estate_proposed", "id_hunter"): ("hunter", "id"),
    ("commission_scale", "id_hunter"): ("hunter", "id"),
    ("payment", "id_hunter"): ("hunter", "id"),
    ("hunter_performance", "id_hunter"): ("hunter", "id"),
}

USER_FKS = {
    ("client", "id_user"),
    ("hunter", "id_user"),
    ("real_estate_manager", "id_user"),
    ("search_request", "id_author"),
    ("criteria", "id_author"),
    ("estate", "id_author"),
    ("estate_contact", "id_author"),
}

# Une ligne par FK à une seule colonne : table, colonne, table visée, colonne visée.
SINGLE_COLUMN_FKS = text(
    """
    SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text, fa.attname
    FROM pg_constraint c
    JOIN pg_attribute a  ON a.attrelid = c.conrelid  AND a.attnum = c.conkey[1]
    JOIN pg_attribute fa ON fa.attrelid = c.confrelid AND fa.attnum = c.confkey[1]
    WHERE c.contype = 'f' AND cardinality(c.conkey) = 1
    """
)


def single_column_fks(db_session: Session) -> list[tuple[str, str, str, str]]:
    rows = db_session.connection().execute(SINGLE_COLUMN_FKS).all()
    return [(table, column, target.strip('"'), target_column) for table, column, target, target_column in rows]


def test_no_foreign_key_targets_profile_id_user(db_session: Session):
    wrong = [fk for fk in single_column_fks(db_session) if fk[2] in PROFILES and fk[3] == "id_user"]
    assert wrong == []


def test_the_eleven_profile_foreign_keys_target_id(db_session: Session):
    found = {(t, c): (ft, fc) for t, c, ft, fc in single_column_fks(db_session) if ft in PROFILES}
    assert found == PROFILE_FKS


def test_only_seven_columns_target_user(db_session: Session):
    found = {(t, c) for t, c, ft, _ in single_column_fks(db_session) if ft == "user"}
    assert found == USER_FKS
