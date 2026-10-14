"""
test_openapi_ids.py — Le Swagger dit « numéro du compte » sous les id de compte.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
`id_client`, `id_hunter`, `id_realestatemanager` et `id_author` portent
`user.id`, pas l'`id` de la table de profil (fiche FIN2, piège soulevé par
Gabriel le 2026-10-14). Le test parcourt le schéma OpenAPI que sert `/docs`
et vérifie la description de chacun de ces champs, dans chaque schéma.

L'autre bout : dans les fiches `Client`, `Hunter` et `RealEstateManager`,
`id` se dit « id technique » et `id_user` « numéro du compte », et
`{item_id}` de leurs routes reprend la phrase de `id` (soulevé par Laurence
le 2026-10-14).
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


PROFILES = {"Client": "/clients", "Hunter": "/hunters", "RealEstateManager": "/real-estate-managers"}


def test_profile_ids_say_which_is_which():
    openapi = app.openapi()
    for schema_name in PROFILES:
        properties = openapi["components"]["schemas"][schema_name]["properties"]
        assert "Id technique" in properties["id"].get("description", ""), schema_name
        assert "user.id" in properties["id_user"].get("description", ""), schema_name


def test_profile_routes_say_item_id_is_the_technical_id():
    openapi = app.openapi()
    for prefix in PROFILES.values():
        operations = openapi["paths"][f"{prefix}/{{item_id}}"]
        assert set(operations) == {"get", "put"}, prefix
        for method, operation in operations.items():
            (param,) = [p for p in operation["parameters"] if p["name"] == "item_id"]
            assert "Id technique" in param.get("description", ""), (method, prefix)
