"""
test_constraints_db.py — Contraintes du schéma init-v3, vues par l'API.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Chaque test vise UNE contrainte de docker/init-v3/01 (ou sa correction
dans 02) et vérifie le code HTTP qui en sort :

- estate : prix en euros entiers (INTEGER, Q-REM-01 du 2026-10-05),
  CHECK price >= 0, liste fermée de estate_type, NOT NULL, UNIQUE ;
- client : ck_client_address_all_or_nothing telle que corrigée par 02
  (ville seule acceptée, adresse sans ville refusée), et
  ck_client_marital_status_exclusive (marié ET pacsé refusé).

Depuis le 2026-10-05, le routeur commun revalide l'entrée (crud_router.py,
`_validated`) : un type faux ou un champ obligatoire manquant donne 422,
avant la base ; une contrainte que seul PostgreSQL connaît (CHECK, UNIQUE)
donne 409.
============================================================================
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

ESTATE: dict[str, Any] = {
    "reference": "TEST-0001",
    "estate_type": "Maison",
    "surface": "120.50",
    "town": "Toulouse",
    "price": 354712,
}


def client_payload(user_id: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id_user": user_id,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_number": "0600000000",
    }
    payload.update(overrides)
    return payload


# --- estate ------------------------------------------------------------------


def test_estate_price_is_whole_euros(db_client: TestClient):
    created = db_client.post("/estates", json=ESTATE)
    assert created.status_code == 201, created.text

    read = db_client.get(f"/estates/{created.json()['id']}")
    assert read.json()["price"] == 354712


# Sans la validation du routeur (avant le 2026-10-05), 199999.5 était arrondi
# en silence à 200000 par PostgreSQL — tranche du dessus — et "199999.50"
# faisait planter l'insertion. Un prix est en euros entiers (Q-REM-01).
@pytest.mark.parametrize("price", [199999.5, "199999.50"])
def test_estate_price_with_cents_returns_422(db_client: TestClient, price: Any):
    response = db_client.post("/estates", json={**ESTATE, "price": price})
    assert response.status_code == 422
    assert db_client.get("/estates").json() == []  # rien n'a été écrit


def test_estate_missing_required_field_returns_422(db_client: TestClient):
    # surface : NOT NULL en base, obligatoire dans le modèle.
    response = db_client.post("/estates", json={**ESTATE, "surface": None})
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price", "-1"),  # CHECK (price >= 0)
        ("estate_type", "Péniche"),  # CHECK estate_type IN (...)
        ("surface", "0"),  # CHECK (surface > 0)
    ],
)
def test_estate_constraint_violation_returns_409(db_client: TestClient, field: str, value: Any):
    response = db_client.post("/estates", json={**ESTATE, field: value})
    assert response.status_code == 409


def test_estate_duplicate_reference_returns_409(db_client: TestClient):
    assert db_client.post("/estates", json=ESTATE).status_code == 201
    assert db_client.post("/estates", json=ESTATE).status_code == 409


# --- client ------------------------------------------------------------------


def test_client_town_without_address_is_accepted(db_client: TestClient, create_user: Callable[[str], int]):
    # Correction de 02 : connaître la ville sans l'adresse est un cas normal.
    response = db_client.post("/clients", json=client_payload(create_user("ville@exemple.fr"), town="Toulouse"))
    assert response.status_code == 201, response.text


def test_client_address_without_town_returns_409(db_client: TestClient, create_user: Callable[[str], int]):
    payload = client_payload(create_user("adresse@exemple.fr"), address="1 rue de la Paix")
    assert db_client.post("/clients", json=payload).status_code == 409


def test_client_married_and_pacs_returns_409(db_client: TestClient, create_user: Callable[[str], int]):
    payload = client_payload(create_user("pacs@exemple.fr"), is_married=True, is_civil_solidarity_pact=True)
    assert db_client.post("/clients", json=payload).status_code == 409


def test_client_second_profile_for_same_user_returns_409(
    db_client: TestClient, create_user: Callable[[str], int]
):
    user_id = create_user("double@exemple.fr")
    assert db_client.post("/clients", json=client_payload(user_id)).status_code == 201
    assert db_client.post("/clients", json=client_payload(user_id)).status_code == 409  # UNIQUE(id_user)
