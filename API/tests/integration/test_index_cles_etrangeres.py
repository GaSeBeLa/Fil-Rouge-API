"""
test_index_cles_etrangeres.py — Les index des filtres par chasseur et par demande.

PostgreSQL n'indexe pas une clé étrangère tout seul. La note d'indexation
(Fil-Rouge, livrables/2-modelisation/note-indexation.md, mesurée le
2026-11-19) montre trois filtres qui lisent toute la table sans index :
× 35, × 15 et × 100 avec. Choix A de Sébastien (2026-11-19) : les poser.
"""

import pytest
from sqlalchemy import text
from sqlmodel import Session

EXPECTED = {
    "idx_estate_searchrequest_request": ("estate_searchrequest", "(id_search_request)"),
    "idx_estate_searchrequest_hunter": ("estate_searchrequest", "(id_hunter)"),
    "idx_search_request_hunter_created": ("search_request", "(id_hunter, created_at DESC)"),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_index_exists_on_the_right_columns(db_session: Session, name: str) -> None:
    row = db_session.connection().execute(
        text("SELECT tablename, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname = :name"),
        {"name": name},
    ).first()

    assert row is not None, f"index {name} absent"
    table, columns = EXPECTED[name]
    assert row.tablename == table
    assert row.indexdef.endswith(columns), row.indexdef
