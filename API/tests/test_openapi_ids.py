"""
test_openapi_ids.py — Le Swagger dit « numéro du compte » sous les id de compte.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
`id_client`, `id_hunter`, `id_realestatemanager` et `id_author` portent
`user.id`, pas l'`id` de la table de profil (fiche FIN2, piège soulevé par
Gabriel le 2026-10-14). Le test parcourt le schéma OpenAPI que sert `/docs`
et vérifie la description de chacun de ces champs, dans chaque schéma.
============================================================================
"""

from typing import Any

from src.app.main import app

ACCOUNT_FIELDS = ("id_client", "id_hunter", "id_realestatemanager", "id_author")


def account_fields(openapi: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(schéma, champ, description) de chaque id de compte du Swagger."""
    found: list[tuple[str, str, str]] = []
    for schema_name, schema in openapi["components"]["schemas"].items():
        for field, spec in schema.get("properties", {}).items():
            if field in ACCOUNT_FIELDS:
                found.append((schema_name, field, spec.get("description", "")))
    return found


def test_every_account_id_says_user_id():
    found = account_fields(app.openapi())
    # 20 champs dans 16 schémas au 2026-10-14 (15 dans les modèles, certains
    # en -Input et -Output) : un parcours vide ne prouverait rien.
    assert len(found) >= 20, found
    missing = [(schema, field) for schema, field, description in found if "user.id" not in description]
    assert missing == []
