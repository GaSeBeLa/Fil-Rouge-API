"""
test_le_sien.py — Le mécanisme « le sien » (ADR-027, point 2 ; fiche DRO4).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Table pilote : payment. Un Hunter ne voit que ses paiements (annexe d'ADR-027,
§ 4, « R les siens », H10) ; celui d'un autre chasseur rend 404, la même
réponse qu'un id qui n'existe pas. L'Admin voit tout.

Le PUT de /payments est réservé à l'Admin (DRO2) : un Hunter y reçoit 403
avant tout filtre (test_droits_par_role.py). Le 404 en modification se prouve
donc au service, par replace_visible, le chemin même du PUT de l'API
(crud_router.py, update_item).
============================================================================
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.app.models import Payment
from src.app.routes.payment_router import payment_service
from src.app.utils.exceptions import NotFoundError
from src.app.utils.roles import HUNTER

from ..conftest import acting_as, principal_as
from .test_constraints_db import (
    HUNTER_ID,
    SALE_MANDATE,
    offered_estate,
    payment_payload,
    post_as_hunter,
    post_as_manager,
    write_payment,
)

OTHER_HUNTER_ID = 2  # chasseur du seed 02, comme HUNTER_ID = 1


def another_sale(db_client: TestClient, first_sale: int) -> int:
    """Une seconde vente, aux montants de la première, sur un mandat et un bien neufs."""
    mandate = post_as_hunter(db_client, "/mandates", {**SALE_MANDATE, "reference": "TEST-M-VENTE-2"})
    assert mandate.status_code == 201, mandate.text
    mandate_id = mandate.json()["id"]
    first = db_client.get(f"/sales/{first_sale}").json()
    kept = ("signature_date", "purchase_amount", "fees_amount", "sale_origin", "id_parameters_fees")
    sale = {key: first[key] for key in kept}
    sale |= {"id_mandate": mandate_id, "id_estate": offered_estate(db_client, mandate_id, reference="TEST-0002")}
    response = post_as_manager(db_client, "/sales", sale)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def payments(db_client: TestClient, db_session: Session) -> tuple[int, int]:
    """Un paiement du chasseur 1, un du chasseur 2 ; leurs ids."""
    # La base de test n'a ni vente ni paiement, et une vente ne porte qu'un
    # paiement (payment.id_sale UNIQUE) : il faut deux ventes.
    payload = payment_payload(db_client)
    sales = (payload["id_sale"], another_sale(db_client, payload["id_sale"]))
    ids = []
    for hunter, sale in zip((HUNTER_ID, OTHER_HUNTER_ID), sales):
        payment = write_payment(db_session, {**payload, "id_hunter": hunter, "id_sale": sale})
        assert payment.id is not None
        ids.append(payment.id)
    return ids[0], ids[1]


def test_hunter_lists_only_his_payments(db_client: TestClient, payments: tuple[int, int]):
    mine, other = payments
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get("/payments")
    assert response.status_code == 200, response.text
    listed = response.json()
    assert mine in {p["id"] for p in listed}
    assert other not in {p["id"] for p in listed}
    assert {p["id_hunter"] for p in listed} == {HUNTER_ID}


def test_admin_lists_every_payment(db_client: TestClient, payments: tuple[int, int]):
    response = db_client.get("/payments")
    assert response.status_code == 200, response.text
    assert set(payments) <= {p["id"] for p in response.json()}


def test_hunter_reads_his_payment(db_client: TestClient, payments: tuple[int, int]):
    mine, _ = payments
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get(f"/payments/{mine}")
    assert response.status_code == 200, response.text
    assert response.json()["id_hunter"] == HUNTER_ID


def test_hunter_gets_404_on_another_hunter_payment(db_client: TestClient, payments: tuple[int, int]):
    _, other = payments
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.get(f"/payments/{other}")
        absent = db_client.get("/payments/999999")
    assert response.status_code == 404, response.text
    # Rien ne dit que la ligne existe : même réponse qu'un id absent.
    assert response.json() == absent.json()


def test_hunter_update_of_another_hunter_payment_is_not_found(db_session: Session, payments: tuple[int, int]):
    _, other = payments
    row = db_session.get(Payment, other)
    assert row is not None
    before = row.model_dump()
    data = Payment.model_validate({**before, "amount": "1.00"})

    with pytest.raises(NotFoundError):
        payment_service.replace_visible(db_session, other, data, principal_as(HUNTER, HUNTER_ID)())

    db_session.refresh(row)
    assert row.model_dump() == before


def test_hunter_update_of_his_payment_passes_the_filter(db_session: Session, payments: tuple[int, int]):
    mine, _ = payments
    row = db_session.get(Payment, mine)
    assert row is not None
    data = Payment.model_validate(row.model_dump())

    updated = payment_service.replace_visible(db_session, mine, data, principal_as(HUNTER, HUNTER_ID)())

    assert updated.id == mine
