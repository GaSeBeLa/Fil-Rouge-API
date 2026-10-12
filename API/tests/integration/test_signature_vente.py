"""
test_signature_vente.py — Signature du mandat et vente (fiche API8).

- ADR-044 : un mandat qui reçoit sa signature lance sa demande
  ('launched'), dans la même transaction.
- Q-MAN-06 : une vente sur un mandat non signé -> 409.
- P27 : une vente 'hunter' suit une offre 'accepted' sur ce bien et ce
  mandat -> sinon 409 ; 'client_alone' n'est pas contrôlé.
- P28 : la vente passe le mandat à 'completed', dans la même transaction.
- ADR-030 : la grille d'honoraires est celle en vigueur à la date de
  l'acte -> sinon 409.

Les ventes partent de sale_payload (test_constraints_db) : un mandat neuf
du chasseur 1, signé le 2026-02-01, un acte du 2026-03-01.
"""

from fastapi.testclient import TestClient

from .test_constraints_db import (
    ESTATE,
    HUNTER_ID,
    MANDATE,
    fees_grid,
    offered_estate,
    post_as_hunter,
    sale_payload,
)

UNSIGNED = {**MANDATE, "reference": "TEST-M-SIGN", "status": "pending_signature", "signature_date": None, "ends_at": None}
SIGNED = {"status": "active", "signature_date": "2026-02-01", "ends_at": "2026-08-01"}


def new_request(db_client: TestClient) -> int:
    """Une demande neuve du client 7, acceptée par le chasseur 1."""
    payload = {"id_author": 7, "id_client": 7, "id_hunter": HUNTER_ID, "status": "accepted"}
    response = db_client.post("/search-requests", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def request_status(db_client: TestClient, request_id: int) -> str:
    return db_client.get(f"/search-requests/{request_id}").json()["status"]


def mandate_status(db_client: TestClient, mandate_id: int) -> str:
    return db_client.get(f"/mandates/{mandate_id}").json()["status"]


def other_estate(db_client: TestClient) -> int:
    """Un bien neuf, sans offre sur aucun mandat."""
    response = post_as_hunter(db_client, "/estates", {**ESTATE, "reference": "TEST-0002"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --- ADR-044 : la signature lance la demande -------------------------------------


def test_signing_a_mandate_launches_its_request(db_client: TestClient):
    request_id = new_request(db_client)
    payload = {**UNSIGNED, "id_search_request": request_id}
    created = db_client.post("/mandates", json=payload)
    assert created.status_code == 201, created.text
    assert request_status(db_client, request_id) == "accepted"  # pas encore signé

    signed = db_client.put(f"/mandates/{created.json()['id']}", json={**payload, **SIGNED})
    assert signed.status_code == 200, signed.text
    assert request_status(db_client, request_id) == "launched"


def test_mandate_created_signed_launches_its_request(db_client: TestClient):
    request_id = new_request(db_client)

    response = db_client.post("/mandates", json={**UNSIGNED, **SIGNED, "id_search_request": request_id})
    assert response.status_code == 201, response.text
    assert request_status(db_client, request_id) == "launched"


def test_refused_mandate_does_not_launch_its_request(db_client: TestClient):
    # Même transaction : la base refuse le mandat (fin ≠ signature + 6 mois),
    # la demande reste 'accepted'.
    request_id = new_request(db_client)
    payload = {**UNSIGNED, **SIGNED, "ends_at": "2026-09-01", "id_search_request": request_id}

    assert db_client.post("/mandates", json=payload).status_code == 409
    assert request_status(db_client, request_id) == "accepted"


# --- Q-MAN-06 : un mandat signé ----------------------------------------------------


def test_sale_on_an_unsigned_mandate_returns_409(db_client: TestClient):
    payload = sale_payload(db_client)
    unsigned = db_client.post("/mandates", json=UNSIGNED)
    assert unsigned.status_code == 201, unsigned.text

    # 'client_alone' : P27 ne s'applique pas, seule la signature manque.
    sale = {**payload, "id_mandate": unsigned.json()["id"], "sale_origin": "client_alone"}
    response = db_client.post("/sales", json=sale)
    assert response.status_code == 409
    assert "Q-MAN-06" in response.text


# --- P27 : une vente 'hunter' suit une offre acceptée --------------------------------


def test_hunter_sale_with_an_accepted_offer_is_accepted(db_client: TestClient):
    response = db_client.post("/sales", json=sale_payload(db_client))
    assert response.status_code == 201, response.text


def test_hunter_sale_without_offer_returns_409(db_client: TestClient):
    payload = {**sale_payload(db_client), "id_estate": other_estate(db_client)}

    response = db_client.post("/sales", json=payload)
    assert response.status_code == 409
    assert "P27" in response.text


def test_hunter_sale_with_an_offer_not_yet_accepted_returns_409(db_client: TestClient):
    payload = sale_payload(db_client)
    pending = offered_estate(db_client, payload["id_mandate"], status="offer_pending", reference="TEST-0002")

    response = db_client.post("/sales", json={**payload, "id_estate": pending})
    assert response.status_code == 409
    assert "P27" in response.text


def test_client_alone_sale_without_offer_is_accepted(db_client: TestClient):
    payload = {**sale_payload(db_client), "id_estate": other_estate(db_client), "sale_origin": "client_alone"}

    response = db_client.post("/sales", json=payload)
    assert response.status_code == 201, response.text


# --- P28 : la vente clôt le mandat --------------------------------------------------


def test_sale_completes_its_mandate(db_client: TestClient):
    payload = sale_payload(db_client)
    assert mandate_status(db_client, payload["id_mandate"]) == "active"

    assert db_client.post("/sales", json=payload).status_code == 201
    assert mandate_status(db_client, payload["id_mandate"]) == "completed"


def test_refused_sale_leaves_its_mandate_active(db_client: TestClient):
    # Même transaction : la base refuse la vente (honoraires >= prix,
    # chk_fees_lower_than_price), le mandat reste 'active'.
    payload = {**sale_payload(db_client), "fees_amount": "400000.00"}

    assert db_client.post("/sales", json=payload).status_code == 409
    assert mandate_status(db_client, payload["id_mandate"]) == "active"


# --- ADR-030 : la grille en vigueur à la date de l'acte ------------------------------


def test_sale_with_an_older_grid_returns_409(db_client: TestClient):
    older = fees_grid(db_client, "2025-01-01")
    in_force = fees_grid(db_client, "2026-01-01")
    payload = sale_payload(db_client, id_parameters_fees=older)  # acte du 2026-03-01

    response = db_client.post("/sales", json=payload)
    assert response.status_code == 409
    assert "ADR-030" in response.text
    assert db_client.post("/sales", json={**payload, "id_parameters_fees": in_force}).status_code == 201


def test_sale_with_a_grid_not_yet_in_force_returns_409(db_client: TestClient):
    later = fees_grid(db_client, "2026-06-01")
    payload = sale_payload(db_client, id_parameters_fees=later)  # acte du 2026-03-01

    response = db_client.post("/sales", json=payload)
    assert response.status_code == 409
    assert "ADR-030" in response.text
