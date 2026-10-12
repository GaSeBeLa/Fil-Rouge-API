"""
test_auteurs.py — Qui saisit un bien, qui ajoute un média (fiche API6).

- ADR-047 : POST /estates est réservé à Hunter et Manager (403 sinon) ;
  `id_author` est le compte du jeton, la valeur envoyée est ignorée, et un
  PUT ne la change pas.
- ADR-051 : POST /review-media est réservé au chasseur qui a écrit la note
  (`estate_searchrequest.id_hunter`) ; un autre compte -> 403.

Comptes du seed 02 : chasseurs 1 et 2, manager 25.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.app.utils.roles import ADMIN, CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as
from .test_constraints_db import ESTATE, HUNTER_ID, post_as_hunter, review_payload

OTHER_HUNTER_ID = 2
MANAGER_ID = 25


# --- ADR-047 : l'auteur d'un bien ---------------------------------------------


@pytest.mark.parametrize(("role", "user_id"), [(HUNTER, HUNTER_ID), (MANAGER, MANAGER_ID)])
def test_estate_author_is_the_connected_account(db_client: TestClient, role: str, user_id: int):
    # Le chasseur 2 est envoyé comme auteur : ignoré, l'auteur est celui du jeton.
    with acting_as(role, user_id):
        response = db_client.post("/estates", json={**ESTATE, "id_author": OTHER_HUNTER_ID})
    assert response.status_code == 201, response.text

    read = db_client.get(f"/estates/{response.json()['id']}")
    assert read.json()["id_author"] == user_id


@pytest.mark.parametrize("role", [CLIENT, ADMIN, READER])
def test_other_roles_cannot_create_an_estate(db_client: TestClient, role: str):
    with acting_as(role):
        response = db_client.post("/estates", json=ESTATE)
    assert response.status_code == 403
    assert db_client.get("/estates").json() == []  # rien n'a été écrit


def test_put_keeps_the_author(db_client: TestClient):
    created = post_as_hunter(db_client, "/estates", ESTATE)
    assert created.status_code == 201, created.text

    # db_client est Admin : PUT lui reste ouvert ; l'auteur envoyé est ignoré.
    changed = {**ESTATE, "town": "Vichy", "id_author": OTHER_HUNTER_ID}
    response = db_client.put(f"/estates/{created.json()['id']}", json=changed)
    assert response.status_code == 200, response.text
    assert response.json()["town"] == "Vichy"
    assert response.json()["id_author"] == HUNTER_ID


# --- ADR-051 : l'auteur d'un média ----------------------------------------------

MEDIA = {"media_url": "https://exemple.test/a.mp3", "media_type": "audio"}


def media_on_new_review(db_client: TestClient) -> dict[str, Any]:
    """Un média pour une note neuve, écrite par le chasseur 1."""
    review = db_client.post("/estate-search-requests", json=review_payload(db_client))
    assert review.status_code == 201, review.text
    return {**MEDIA, "id_estate_searchrequest": review.json()["id"]}


def test_review_author_adds_a_media(db_client: TestClient):
    media = media_on_new_review(db_client)
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.post("/review-media", json=media)
    assert response.status_code == 201, response.text


def test_other_hunter_cannot_add_a_media(db_client: TestClient):
    media = media_on_new_review(db_client)
    with acting_as(HUNTER, OTHER_HUNTER_ID):
        response = db_client.post("/review-media", json=media)
    assert response.status_code == 403
    assert "ADR-051" in response.text


@pytest.mark.parametrize("role", [ADMIN, MANAGER, CLIENT])
def test_other_roles_cannot_add_a_media(db_client: TestClient, role: str):
    # Même avec l'id du chasseur auteur : le rôle est refusé avant le service.
    media = media_on_new_review(db_client)
    with acting_as(role, HUNTER_ID):
        response = db_client.post("/review-media", json=media)
    assert response.status_code == 403
