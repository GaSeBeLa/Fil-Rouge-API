"""
« Le sien » du Client suit le numéro de sa fiche, pas son compte (fiche PRF3).

Depuis le chantier PRF (2026-10-15), search_request.id_client et
mandate.id_client citent client.id. Un client dont la fiche a un id
différent de son id_user doit voir ses demandes, ses mandats et leurs
visites (client_rows.mandates_of), et pas ceux d'un autre client (404,
comme un id absent).

Une fiche bouche-trou est créée avant les deux clients du test : leurs
numéros de fiche ne peuvent pas tomber sur leurs numéros de compte, même
dans une base où ils coïncideraient.
"""

from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.app.models import Client, Mandate, SearchRequest, Visit
from src.app.utils.roles import CLIENT, HUNTER

from ..conftest import acting_as
from .test_constraints_db import CLIENT_ADDRESS, ESTATE, HUNTER_ID

# HUNTER_ID : chasseur 1 du seed 02, dont la fiche a aussi le numéro 1.


def new_client(db_session: Session, user_id: int, phone: str) -> Client:
    client = Client(id_user=user_id, first_name="Test", last_name="PRF3", phone_number=phone, **CLIENT_ADDRESS)
    db_session.add(client)
    db_session.flush()
    return client


def request_mandate_visit(
    db_client: TestClient, db_session: Session, client: Client, reference: str
) -> tuple[int, int, int]:
    """Une demande, un mandat et une visite du client ; leurs ids."""
    assert client.id is not None
    request = SearchRequest(id_author=client.id_user, id_client=client.id, id_hunter=HUNTER_ID, status="launched")
    db_session.add(request)
    db_session.flush()
    assert request.id is not None
    mandate = Mandate(
        reference=reference,
        status="pending_signature",
        is_exclusive=False,
        id_hunter=HUNTER_ID,
        id_client=client.id,
        id_search_request=request.id,
    )
    db_session.add(mandate)
    db_session.flush()
    assert mandate.id is not None
    with acting_as(HUNTER, HUNTER_ID):  # estate.id_author : un compte qui crée des biens (ADR-047)
        estate = db_client.post("/estates", json={**ESTATE, "reference": reference})
    assert estate.status_code == 201, estate.text
    visit = Visit(visit_date=date(2026, 2, 10), visitor_type="client", id_estate=estate.json()["id"], id_mandate=mandate.id)
    db_session.add(visit)
    db_session.flush()
    assert visit.id is not None
    return request.id, mandate.id, visit.id


def test_client_whose_id_differs_from_account_sees_his_own(
    db_client: TestClient, db_session: Session, create_user: Callable[[str], int]
):
    new_client(db_session, create_user("bouche-trou.prf3@exemple.fr"), "+33600000001")
    me = new_client(db_session, create_user("moi.prf3@exemple.fr"), "+33600000002")
    other = new_client(db_session, create_user("autre.prf3@exemple.fr"), "+33600000003")
    assert me.id != me.id_user and other.id != other.id_user
    my_request, my_mandate, my_visit = request_mandate_visit(db_client, db_session, me, "TEST-PRF3-MOI")
    their_request, their_mandate, their_visit = request_mandate_visit(db_client, db_session, other, "TEST-PRF3-AUTRE")
    db_session.commit()

    with acting_as(CLIENT, me.id_user):
        requests = {row["id"] for row in db_client.get("/search-requests").json()}
        mandates = {row["id"] for row in db_client.get("/mandates").json()}
        visits = {row["id"] for row in db_client.get("/visits").json()}
        read_mine = db_client.get(f"/mandates/{my_mandate}")
        read_theirs = db_client.get(f"/mandates/{their_mandate}")
        read_their_request = db_client.get(f"/search-requests/{their_request}")

    assert my_request in requests and their_request not in requests
    assert my_mandate in mandates and their_mandate not in mandates
    assert my_visit in visits and their_visit not in visits
    assert read_mine.status_code == 200, read_mine.text
    assert read_theirs.status_code == 404, read_theirs.text
    assert read_their_request.status_code == 404, read_their_request.text
