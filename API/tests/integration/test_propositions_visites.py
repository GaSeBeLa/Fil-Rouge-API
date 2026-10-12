"""
test_propositions_visites.py — Propositions et visites (fiche API7).

Règles entre tables, dans les services (ADR-040) ; un refus -> 409 :
- P19 : un bien proposé est dans la sélection de la demande du mandat ;
- P20 : on ne propose que sur un mandat 'active' ;
- P23 : une visite 'client' porte sur un bien proposé sur ce mandat ; les
  visites 'hunter' ne sont pas contrôlées ;
- P25 : une visite tombe dans les dates du mandat, son statut n'est pas
  regardé ;
- ADR-044 : pas de visite avant la signature du mandat.

Mandats du seed 02 : 15 ('active', chasseur 1, demande 15, du 2026-03-25 au
2026-09-25) ; 3 ('completed') et 11 ('expired'), chasseur 1 ; 16
('canceled', chasseur 6, du 2026-04-12 au 2026-10-12).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from .test_constraints_db import (
    ACTIVE_MANDATE,
    ACTIVE_REQUEST,
    HUNTER_ID,
    MANDATE,
    selected_estate,
)

CANCELED_MANDATE = 16


def proposal(estate_id: int, mandate: int = ACTIVE_MANDATE) -> dict[str, Any]:
    return {"proposition_status": "proposed", "id_hunter": HUNTER_ID, "id_estate": estate_id, "id_mandate": mandate}


def visit(estate_id: int, visit_date: str, visitor_type: str = "client", mandate: int = ACTIVE_MANDATE) -> dict[str, Any]:
    return {"visit_date": visit_date, "visitor_type": visitor_type, "id_estate": estate_id, "id_mandate": mandate}


def proposed_estate(db_client: TestClient) -> int:
    """Un bien de la sélection, proposé sur le mandat 15."""
    estate_id = selected_estate(db_client)
    response = db_client.post("/estate-proposed", json=proposal(estate_id))
    assert response.status_code == 201, response.text
    return estate_id


# --- P19 : le bien vient de la sélection de la demande --------------------------


def test_selected_estate_can_be_proposed(db_client: TestClient):
    response = db_client.post("/estate-proposed", json=proposal(selected_estate(db_client)))
    assert response.status_code == 201, response.text


def test_estate_selected_for_another_request_cannot_be_proposed(db_client: TestClient):
    # Sélectionné pour la demande 3, proposé sur le mandat 15 (demande 15).
    estate_id = selected_estate(db_client, search_request=3)

    response = db_client.post("/estate-proposed", json=proposal(estate_id))
    assert response.status_code == 409
    assert "P19" in response.text


def test_moving_a_proposal_to_an_unselected_estate_returns_409(db_client: TestClient):
    payload = proposal(selected_estate(db_client))
    created = db_client.post("/estate-proposed", json=payload).json()
    other = selected_estate(db_client, search_request=3, reference="TEST-0002")

    response = db_client.put(f"/estate-proposed/{created['id']}", json={**payload, "id_estate": other})
    assert response.status_code == 409
    assert "P19" in response.text


def test_updating_a_proposal_in_place_is_accepted(db_client: TestClient):
    payload = proposal(selected_estate(db_client))
    created = db_client.post("/estate-proposed", json=payload).json()

    changed = {**payload, "comment_client": "À visiter vite."}
    response = db_client.put(f"/estate-proposed/{created['id']}", json=changed)
    assert response.status_code == 200, response.text


# --- P20 : seulement sur un mandat actif ------------------------------------------


@pytest.mark.parametrize(("mandate", "request_id"), [(3, 3), (11, 11)])
def test_proposal_on_a_closed_mandate_returns_409(db_client: TestClient, mandate: int, request_id: int):
    # Le bien est dans la sélection de la demande : seule P20 refuse.
    estate_id = selected_estate(db_client, search_request=request_id)

    response = db_client.post("/estate-proposed", json=proposal(estate_id, mandate))
    assert response.status_code == 409
    assert "P20" in response.text


# --- P23 : le client visite un bien proposé ----------------------------------------


def test_client_visit_on_a_proposed_estate_is_accepted(db_client: TestClient):
    response = db_client.post("/visits", json=visit(proposed_estate(db_client), "2026-05-10"))
    assert response.status_code == 201, response.text


def test_client_visit_on_an_unproposed_estate_returns_409(db_client: TestClient):
    # Sélectionné, mais jamais proposé sur ce mandat.
    response = db_client.post("/visits", json=visit(selected_estate(db_client), "2026-05-10"))
    assert response.status_code == 409
    assert "P23" in response.text


def test_hunter_visit_on_an_unproposed_estate_is_accepted(db_client: TestClient):
    response = db_client.post("/visits", json=visit(selected_estate(db_client), "2026-05-10", "hunter"))
    assert response.status_code == 201, response.text


# --- P25 et ADR-044 : dans les dates du mandat ----------------------------------------


@pytest.mark.parametrize("visit_date", ["2026-03-25", "2026-09-25"])
def test_visit_on_the_mandate_bounds_is_accepted(db_client: TestClient, visit_date: str):
    response = db_client.post("/visits", json=visit(proposed_estate(db_client), visit_date))
    assert response.status_code == 201, response.text


def test_visit_after_the_mandate_end_returns_409(db_client: TestClient):
    response = db_client.post("/visits", json=visit(proposed_estate(db_client), "2026-09-26"))
    assert response.status_code == 409
    assert "P25" in response.text


def test_visit_on_a_canceled_mandate_within_its_dates_is_accepted(db_client: TestClient):
    # P25 : le statut n'est pas regardé ; visite du chasseur, P23 ne s'applique pas.
    payload = visit(selected_estate(db_client), "2026-05-01", "hunter", CANCELED_MANDATE)
    response = db_client.post("/visits", json=payload)
    assert response.status_code == 201, response.text


def test_visit_before_the_signature_returns_409(db_client: TestClient):
    response = db_client.post("/visits", json=visit(proposed_estate(db_client), "2026-03-24"))
    assert response.status_code == 409
    assert "ADR-044" in response.text


def test_visit_on_an_unsigned_mandate_returns_409(db_client: TestClient):
    unsigned = {**MANDATE, "status": "pending_signature", "signature_date": None, "ends_at": None}
    mandate = db_client.post("/mandates", json=unsigned)
    assert mandate.status_code == 201, mandate.text

    payload = visit(selected_estate(db_client), "2026-05-01", "hunter", mandate.json()["id"])
    response = db_client.post("/visits", json=payload)
    assert response.status_code == 409
    assert "ADR-044" in response.text


def test_moving_a_visit_after_the_mandate_end_returns_409(db_client: TestClient):
    payload = visit(proposed_estate(db_client), "2026-05-10")
    created = db_client.post("/visits", json=payload).json()

    response = db_client.put(f"/visits/{created['id']}", json={**payload, "visit_date": "2026-09-30"})
    assert response.status_code == 409
    assert "P25" in response.text


def test_request_of_the_active_mandate_is_the_seeded_one(db_client: TestClient):
    # Garde-fou des tests ci-dessus : le mandat 15 du seed vise bien la demande 15.
    mandate = db_client.get(f"/mandates/{ACTIVE_MANDATE}").json()
    assert (mandate["status"], mandate["id_search_request"]) == ("active", ACTIVE_REQUEST)
