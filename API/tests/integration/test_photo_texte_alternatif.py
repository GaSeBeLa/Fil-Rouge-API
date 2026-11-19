"""
test_photo_texte_alternatif.py — Le texte qui décrit une photo (`picture.alt_text`).

Note d'accessibilité PSH (Fil-Rouge, livrables/5-transverse/, 2026-11-19) :
un lecteur d'écran lit le texte d'une image ; sans lui, une personne aveugle
ne sait pas ce que montre la photo d'un bien (WCAG 2.2, critère 1.1.1).
Choix A de Sébastien : la colonne, facultative, 300 caractères au plus.
"""

from typing import Any

from fastapi.testclient import TestClient

from src.app.utils.roles import HUNTER

from ..conftest import acting_as
from .test_constraints_db import ESTATE

SEED_HUNTER = 1  # user 1, chasseur du seed 02


def _estate(db_client: TestClient, reference: str) -> int:
    with acting_as(HUNTER, SEED_HUNTER):
        response = db_client.post("/estates", json={**ESTATE, "reference": reference})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _picture(db_client: TestClient, payload: dict[str, Any]):
    with acting_as(HUNTER, SEED_HUNTER):
        return db_client.post("/pictures", json=payload)


def test_picture_keeps_its_alternative_text(db_client: TestClient) -> None:
    estate_id = _estate(db_client, "TEST-ALT-1")
    text = "Salon lumineux, cheminée en pierre, parquet clair"

    response = _picture(db_client, {"url": "https://exemple.test/salon.jpg", "id_estate": estate_id, "alt_text": text})

    assert response.status_code == 201, response.text
    assert response.json()["alt_text"] == text
    assert db_client.get(f"/pictures/{response.json()['id']}").json()["alt_text"] == text


def test_alternative_text_is_optional(db_client: TestClient) -> None:
    estate_id = _estate(db_client, "TEST-ALT-2")

    response = _picture(db_client, {"url": "https://exemple.test/vue.jpg", "id_estate": estate_id})

    assert response.status_code == 201, response.text
    assert response.json()["alt_text"] is None


def test_alternative_text_over_300_characters_refused(db_client: TestClient) -> None:
    estate_id = _estate(db_client, "TEST-ALT-3")

    response = _picture(db_client, {"url": "https://exemple.test/long.jpg", "id_estate": estate_id, "alt_text": "x" * 301})

    assert response.status_code in (409, 422), response.text
