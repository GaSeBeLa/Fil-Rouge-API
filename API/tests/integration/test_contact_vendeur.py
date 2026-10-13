"""
test_contact_vendeur.py — Le contact du vendeur d'un bien (ADR-054).

- Lecture et écriture réservées à Admin, Hunter et Manager : Client et
  Reader reçoivent 403, même en lecture.
- `id_author` est le compte du jeton ; un PUT ne le change pas.
- La base refuse : un second contact pour le même bien (UNIQUE), un
  téléphone hors du format d'ADR-007, une ligne sans aucun renseignement.

Comptes du seed 02 : chasseurs 1 et 2, manager 25.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.app.utils.roles import ADMIN, CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as
from .test_constraints_db import ESTATE, HUNTER_ID, post_as_hunter

OTHER_HUNTER_ID = 2
MANAGER_ID = 25

CONTACT: dict[str, Any] = {
    "seller_type": "agency",
    "agency_name": "Agence du Centre",
    "contact_name": "Mme Martin",
    "phone_number": "+33612345678",
    "email": "contact@agence.test",
}


def new_estate(db_client: TestClient) -> int:
    created = post_as_hunter(db_client, "/estates", ESTATE)
    assert created.status_code == 201, created.text
    return created.json()["id"]


def post_contact(db_client: TestClient, payload: dict[str, Any]):
    with acting_as(HUNTER, HUNTER_ID):
        return db_client.post("/estate-contacts", json=payload)


# --- Droits --------------------------------------------------------------------


@pytest.mark.parametrize(("role", "user_id"), [(HUNTER, HUNTER_ID), (MANAGER, MANAGER_ID), (ADMIN, MANAGER_ID)])
def test_staff_writes_and_reads_a_contact(db_client: TestClient, role: str, user_id: int):
    payload = {**CONTACT, "id_estate": new_estate(db_client)}
    with acting_as(role, user_id):
        created = db_client.post("/estate-contacts", json=payload)
        assert created.status_code == 201, created.text
        read = db_client.get(f"/estate-contacts/{created.json()['id']}")
        listed = db_client.get("/estate-contacts")
    assert read.status_code == 200
    assert read.json()["phone_number"] == "+33612345678"
    assert listed.status_code == 200


@pytest.mark.parametrize("role", [CLIENT, READER])
def test_client_and_reader_cannot_read_contacts(db_client: TestClient, role: str):
    created = post_contact(db_client, {**CONTACT, "id_estate": new_estate(db_client)})
    assert created.status_code == 201, created.text
    with acting_as(role):
        listed = db_client.get("/estate-contacts")
        read = db_client.get(f"/estate-contacts/{created.json()['id']}")
    assert listed.status_code == 403
    assert read.status_code == 403


@pytest.mark.parametrize("role", [CLIENT, READER])
def test_client_and_reader_cannot_write_contacts(db_client: TestClient, role: str):
    with acting_as(role, HUNTER_ID):
        response = db_client.post("/estate-contacts", json={**CONTACT, "id_estate": new_estate(db_client)})
    assert response.status_code == 403
    assert db_client.get("/estate-contacts").json() == []  # rien n'a été écrit


# --- Auteur --------------------------------------------------------------------


def test_author_is_the_token_account_and_put_keeps_it(db_client: TestClient):
    payload = {**CONTACT, "id_estate": new_estate(db_client), "id_author": OTHER_HUNTER_ID}
    created = post_contact(db_client, payload)
    assert created.status_code == 201, created.text
    assert created.json()["id_author"] == HUNTER_ID

    with acting_as(MANAGER, MANAGER_ID):
        changed = db_client.put(
            f"/estate-contacts/{created.json()['id']}",
            json={**payload, "contact_name": "M. Durand", "id_author": MANAGER_ID},
        )
    assert changed.status_code == 200, changed.text
    assert changed.json()["contact_name"] == "M. Durand"
    assert changed.json()["id_author"] == HUNTER_ID


# --- Contraintes de la base ----------------------------------------------------


def test_one_contact_per_estate(db_client: TestClient):
    estate_id = new_estate(db_client)
    assert post_contact(db_client, {**CONTACT, "id_estate": estate_id}).status_code == 201
    second = post_contact(db_client, {**CONTACT, "id_estate": estate_id})
    assert second.status_code == 409


@pytest.mark.parametrize("phone", ["0612345678", "+0612345678", "06 12 34 56 78"])
def test_phone_must_follow_adr_007(db_client: TestClient, phone: str):
    response = post_contact(db_client, {**CONTACT, "phone_number": phone, "id_estate": new_estate(db_client)})
    assert response.status_code == 409


def test_contact_needs_at_least_one_detail(db_client: TestClient):
    response = post_contact(db_client, {"seller_type": "private", "id_estate": new_estate(db_client)})
    assert response.status_code == 409


def test_unknown_seller_type_is_allowed(db_client: TestClient):
    # ADR-054 : vide = inconnu ; un nom seul suffit.
    response = post_contact(db_client, {"contact_name": "M. Bernard", "id_estate": new_estate(db_client)})
    assert response.status_code == 201, response.text
    assert response.json()["seller_type"] is None
