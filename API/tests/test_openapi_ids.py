"""
test_openapi_ids.py — Le Swagger dit quel numéro porte chaque id : fiche ou compte.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Depuis le chantier PRF (2026-10-15), `id_client`, `id_hunter` et
`id_realestatemanager` portent le numéro de la fiche (`client.id`,
`hunter.id`, `real_estate_manager.id`) ; `id_author` porte le numéro du
compte (`user.id`). Piège soulevé par Gabriel le 2026-10-14 (fiche FIN2).
Le test parcourt le schéma OpenAPI que sert `/docs` et vérifie la
description de chacun de ces champs, dans chaque schéma.

L'autre bout : dans les fiches `Client`, `Hunter` et `RealEstateManager`,
`id` se dit « numéro de la fiche » et `id_user` « numéro du compte », et
`{item_id}` de leurs routes reprend la phrase de `id` (soulevé par Laurence
le 2026-10-14).
============================================================================
"""

from typing import Any

from src.app.main import app

# Le champ, et la colonne qu'il cite : c'est elle que sa description doit nommer.
REFERENCE_FIELDS = {
    "id_client": "client.id",
    "id_hunter": "hunter.id",
    "id_realestatemanager": "real_estate_manager.id",
    "id_author": "user.id",
}


def reference_fields(openapi: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(schéma, champ, description) de chaque id de fiche ou de compte du Swagger."""
    found: list[tuple[str, str, str]] = []
    for schema_name, schema in openapi["components"]["schemas"].items():
        for field, spec in schema.get("properties", {}).items():
            if field in REFERENCE_FIELDS:
                found.append((schema_name, field, spec.get("description", "")))
    return found


def test_every_reference_names_the_column_it_cites():
    found = reference_fields(app.openapi())
    # 20 champs dans 16 schémas au 2026-10-14 (15 dans les modèles, certains
    # en -Input et -Output) : un parcours vide ne prouverait rien.
    assert len(found) >= 20, found
    wrong = [
        (schema, field) for schema, field, description in found if REFERENCE_FIELDS[field] not in description
    ]
    assert wrong == []


PROFILES = {"Client": "/clients", "Hunter": "/hunters", "RealEstateManager": "/real-estate-managers"}


def test_profile_ids_say_which_is_which():
    openapi = app.openapi()
    for schema_name in PROFILES:
        properties = openapi["components"]["schemas"][schema_name]["properties"]
        assert "Numéro de la fiche" in properties["id"].get("description", ""), schema_name
        assert "user.id" in properties["id_user"].get("description", ""), schema_name


def test_profile_routes_say_item_id_is_the_profile_id():
    openapi = app.openapi()
    for prefix in PROFILES.values():
        operations = openapi["paths"][f"{prefix}/{{item_id}}"]
        assert set(operations) == {"get", "put"}, prefix
        for method, operation in operations.items():
            (param,) = [p for p in operation["parameters"] if p["name"] == "item_id"]
            assert "Numéro de la fiche" in param.get("description", ""), (method, prefix)
