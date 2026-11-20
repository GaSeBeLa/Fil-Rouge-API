"""
Le client ne fait que signer son mandat (ADR-027, annexe § 2, P3).

Avant le 2026-11-20, `mandate_service.py` ne filtrait aucun champ : un client
pouvait changer l'exclusivité, les dates ou le statut de son propre mandat.
Il ne change plus que la signature : `signature_date`, `signature_type`,
`ends_at`, et le statut seulement de 'pending_signature' à 'active'. Tout
autre changement lève 403, la ligne intacte. Une date de signature future
lève 409 : elle prolongerait le mandat. Le chasseur garde ses droits.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.app.utils.roles import CLIENT, HUNTER

from ..conftest import acting_as
from .test_constraints_db import MANDATE, post_as_hunter
from .test_le_sien import CLIENT_ID, HUNTER_ID

# Une date passée : un mandat papier peut avoir été signé avant sa saisie.
SIGNATURE = {"status": "active", "signature_date": "2026-11-01", "signature_type": "paper", "ends_at": "2027-05-01"}


@pytest.fixture
def pending(db_client: TestClient) -> dict[str, Any]:
    """Un mandat du client 7 en attente de signature, créé par son chasseur ; son corps lu par l'Admin."""
    payload = {
        **MANDATE, "reference": "TEST-M-SIGNE", "status": "pending_signature",
        "signature_date": None, "ends_at": None,
    }
    response = post_as_hunter(db_client, "/mandates", payload)
    assert response.status_code == 201, response.text
    return db_client.get(f"/mandates/{response.json()['id']}").json()


def test_client_cannot_change_exclusivity_of_his_mandate(db_client: TestClient, pending: dict[str, Any]):
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/mandates/{pending['id']}", json={**pending, "is_exclusive": True})

    assert response.status_code == 403, response.text
    assert "is_exclusive" in response.json()["detail"]
    assert db_client.get(f"/mandates/{pending['id']}").json() == pending


def test_client_cannot_cancel_his_mandate(db_client: TestClient, pending: dict[str, Any]):
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/mandates/{pending['id']}", json={**pending, "status": "canceled"})

    assert response.status_code == 403, response.text
    assert db_client.get(f"/mandates/{pending['id']}").json() == pending


def test_client_signs_his_mandate(db_client: TestClient, pending: dict[str, Any]):
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/mandates/{pending['id']}", json={**pending, **SIGNATURE})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"
    assert response.json()["signature_date"] == "2026-11-01"


def test_client_cannot_move_the_signature_of_an_active_mandate(db_client: TestClient, pending: dict[str, Any]):
    # Signé, le mandat est clos pour lui : déplacer la date prolongerait sa
    # validité (droit à rémunération, délai mandat → acte).
    with acting_as(CLIENT, CLIENT_ID):
        signed = db_client.put(f"/mandates/{pending['id']}", json={**pending, **SIGNATURE})
        assert signed.status_code == 200, signed.text
        moved = {**signed.json(), "signature_date": "2026-10-01", "ends_at": "2027-04-01"}
        response = db_client.put(f"/mandates/{pending['id']}", json=moved)

    assert response.status_code == 403, response.text
    assert db_client.get(f"/mandates/{pending['id']}").json()["signature_date"] == "2026-11-01"


def test_client_cannot_sign_in_the_future(db_client: TestClient, pending: dict[str, Any]):
    future = {**SIGNATURE, "signature_date": "2099-01-01", "ends_at": "2099-07-01"}
    with acting_as(CLIENT, CLIENT_ID):
        response = db_client.put(f"/mandates/{pending['id']}", json={**pending, **future})

    assert response.status_code == 409, response.text
    assert db_client.get(f"/mandates/{pending['id']}").json() == pending


def test_hunter_still_changes_exclusivity(db_client: TestClient, pending: dict[str, Any]):
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.put(f"/mandates/{pending['id']}", json={**pending, "is_exclusive": True})

    assert response.status_code == 200, response.text
    assert response.json()["is_exclusive"] is True
