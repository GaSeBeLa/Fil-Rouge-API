"""
test_scenarios_restants.py — Les scénarios des user stories qui n'avaient pas leur test.

Relevé par la matrice des tests fonctionnels (Fil-Rouge,
livrables/4-application/4.3-tests-fonctionnels.md, 2026-11-19) ; « go tout » de
Sébastien le même jour. Un test par scénario, nommé d'après lui :

- 00:30 : en non exclusif, un autre chasseur peut agir pour le même client ;
- 03:19, 06:37 : l'offre refusée par le vendeur, puis une nouvelle offre, ou
  de nouvelles propositions ;
- 03:25, 06:44 : l'offre acceptée par le vendeur ;
- 04:17 : le chasseur refuse une demande, qui est réaffectée ;
- 10:277 : le montant annoncé au chasseur est celui qui sera payé.
"""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session as SQLModelSession

from src.app.utils.roles import CLIENT, HUNTER, MANAGER

from ..conftest import acting_as
from .test_constraints_db import (
    ACTIVE_MANDATE_CLIENT,
    MANDATE,
    hunter_profile,
    post_as_hunter,
    selected_estate,
)
from .test_propositions_visites import offer_url, proposal
from .test_versions_paiement import ANNOUNCED, SCHEDULED, create_payment

SEED_MANAGER = 25  # user 25, manager des chasseurs 1 à 6 du seed 02
OTHER_HUNTER = 2  # user 2, un autre chasseur du même manager


def _offer_pending(db_client: TestClient, reference: str = "TEST-OFFRE-1") -> int:
    """Un bien proposé au client 21, et son offre faite : l'id de la proposition."""
    created = post_as_hunter(db_client, "/estate-proposed", proposal(selected_estate(db_client, reference=reference)))
    assert created.status_code == 201, created.text
    with acting_as(CLIENT, ACTIVE_MANDATE_CLIENT):
        offered = db_client.post(offer_url(created.json()["id"]), json={"amount_proposition": 280000})
    assert offered.status_code == 200, offered.text
    return created.json()["id"]


def _hunter_sets(db_client: TestClient, proposal_id: int, status: str):
    """Le chasseur 1 rapporte la réponse du vendeur sur la proposition."""
    body = db_client.get(f"/estate-proposed/{proposal_id}").json()
    with acting_as(HUNTER, 1):
        return db_client.put(f"/estate-proposed/{proposal_id}", json={**body, "proposition_status": status})


# --- 00:30 ---------------------------------------------------------------


def test_00_30_another_hunter_can_act_under_a_non_exclusive_mandate(db_client: TestClient) -> None:
    first = post_as_hunter(db_client, "/mandates", {**MANDATE, "is_exclusive": False})
    assert first.status_code == 201, first.text

    # Le second chasseur suit sa propre demande pour le même client (Q-ACC-15),
    # avec ses critères (M1) : un mandat se signe sur une demande qu'il suit.
    with acting_as(HUNTER, OTHER_HUNTER):
        request = db_client.post("/search-requests", json={
            "id_author": OTHER_HUNTER, "id_client": MANDATE["id_client"],
            "id_hunter": hunter_profile(OTHER_HUNTER), "status": "accepted",
        })
        assert request.status_code == 201, request.text
        criteria = db_client.post("/criteria", json={
            "id_author": OTHER_HUNTER, "id_search_request": request.json()["id"],
            "estate_type": "Appartement", "budget_max": 300000,
        })
        assert criteria.status_code == 201, criteria.text
        second = db_client.post("/mandates", json={
            **MANDATE, "reference": "TEST-M-0002", "is_exclusive": False,
            "id_hunter": hunter_profile(OTHER_HUNTER), "id_search_request": request.json()["id"],
        })

    assert second.status_code == 201, second.text


# --- 03:19, 06:37 ----------------------------------------------------------


def test_06_37_seller_refuses_the_offer(db_client: TestClient) -> None:
    proposal_id = _offer_pending(db_client)

    refused = _hunter_sets(db_client, proposal_id, "rejected")

    assert refused.status_code == 200, refused.text
    assert refused.json()["proposition_status"] == "rejected"


def test_06_37_a_new_offer_can_follow_a_refusal(db_client: TestClient) -> None:
    proposal_id = _offer_pending(db_client)
    assert _hunter_sets(db_client, proposal_id, "rejected").status_code == 200

    with acting_as(CLIENT, ACTIVE_MANDATE_CLIENT):
        again = db_client.post(offer_url(proposal_id), json={"amount_proposition": 295000})

    assert again.status_code == 200, again.text
    assert (again.json()["proposition_status"], again.json()["amount_proposition"]) == ("offer_pending", 295000)


def test_03_19_after_a_refusal_the_hunter_proposes_other_estates(db_client: TestClient) -> None:
    proposal_id = _offer_pending(db_client)
    assert _hunter_sets(db_client, proposal_id, "rejected").status_code == 200

    other = post_as_hunter(db_client, "/estate-proposed", proposal(selected_estate(db_client, reference="TEST-OFFRE-2")))

    assert other.status_code == 201, other.text


# --- 03:25, 06:44 ----------------------------------------------------------


def test_06_44_seller_accepts_the_offer(db_client: TestClient) -> None:
    proposal_id = _offer_pending(db_client)

    accepted = _hunter_sets(db_client, proposal_id, "accepted")

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["proposition_status"] == "accepted"


# --- 04:17 -----------------------------------------------------------------


def test_04_17_hunter_refuses_and_the_request_is_reassigned(db_client: TestClient) -> None:
    submitted: dict[str, Any] = {
        "email": "refus.chasseur@exemple.fr", "first_name": "Léo", "last_name": "Blanc",
        "phone_number": "+33612348888", "country_iso": "FR", "address": "2 rue Saint-Maur",
        "postal_code": "75011", "town": "Paris", "budget_max": 300000, "estate_type": "Appartement",
    }
    assert db_client.post("/search-requests/submit", json=submitted).status_code == 202
    request = next(r for r in db_client.get("/search-requests").json() if r["status"] == "confirmed" and r["id_hunter"] is None)
    manager = next(m for m in db_client.get("/real-estate-managers").json() if m["id_user"] == SEED_MANAGER)
    with acting_as(MANAGER, SEED_MANAGER):
        taken = db_client.put(
            f"/search-requests/{request['id']}",
            json={**request, "id_realestatemanager": manager["id"], "id_hunter": hunter_profile(1)},
        )
    assert taken.status_code == 200, taken.text

    with acting_as(HUNTER, 1):
        refused = db_client.put(f"/search-requests/{request['id']}", json={**taken.json(), "status": "rejected"})
    assert refused.status_code == 200, refused.text

    with acting_as(MANAGER, SEED_MANAGER):
        reassigned = db_client.put(
            f"/search-requests/{request['id']}", json={**refused.json(), "id_hunter": hunter_profile(OTHER_HUNTER)}
        )
    assert reassigned.status_code == 200, reassigned.text
    with acting_as(HUNTER, 1):  # « n'est pas prise en charge par moi »
        assert db_client.get(f"/search-requests/{request['id']}").status_code == 404
    with acting_as(HUNTER, OTHER_HUNTER):
        accepted = db_client.put(f"/search-requests/{request['id']}", json={**reassigned.json(), "status": "accepted"})
    assert accepted.status_code == 200, accepted.text


# --- 10:277 ----------------------------------------------------------------


def test_10_277_announced_amount_cannot_change_before_payment(
    db_client: TestClient, db_session: SQLModelSession
) -> None:
    payment_id, payload = create_payment(db_client, db_session)
    assert payload["status"] == ANNOUNCED["status"]

    changed = db_client.put(f"/payments/{payment_id}", json={**payload, **SCHEDULED, "amount": "1.00"})

    assert changed.status_code == 409, changed.text
