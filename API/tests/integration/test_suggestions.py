"""
test_suggestions.py — POST /search-requests/{id}/suggestions (fiche SUG8).

Le moteur de suggestion : le chasseur de la demande obtient jusqu'à 10 biens
qui collent aux derniers critères, écrits dans la sélection à l'état
`suggested`. Sans les biens vendus, ni ceux déjà dans la sélection de la
demande, quel que soit leur état.

Sans Elasticsearch : le client est remplacé par un faux (`FakeES`), qui rend
ses biens dans l'ordre en tenant compte de `must_not` (les ids exclus) et de
`size`, comme le vrai.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from elasticsearch import ConnectionError as ESConnectionError
from fastapi.testclient import TestClient

from src.app.main import app
from src.app.routes import estate_search_router
from src.app.utils.roles import CLIENT, HUNTER

from ..conftest import acting_as
from .test_constraints_db import ESTATE, HUNTER_ID, HUNTER_PROFILE, post_as_hunter, post_as_manager, sale_payload
from .test_signature_vente import new_request

OTHER_HUNTER = 6  # chasseur du mandat 16 (seed 02) : la demande neuve n'est pas à lui


class FakeES:
    """Un Elasticsearch de test : rend `estate_ids` dans l'ordre, sans les exclus, `size` au plus."""

    def __init__(self, estate_ids: list[int] | None = None, error: Exception | None = None):
        self.estate_ids = estate_ids or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, Any]:
        """La réponse de l'API _search ; lève `error` si elle est donnée."""
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        excluded = {value for clause in kwargs["query"]["bool"]["must_not"] for value in clause["ids"]["values"]}
        kept = [i for i in self.estate_ids if str(i) not in excluded][: kwargs.get("size", 10)]
        hits = [{"_id": str(i), "_source": {"id": i}} for i in kept]
        return {"hits": {"total": {"value": len(hits)}, "hits": hits}}


@pytest.fixture
def fake_es() -> Iterator[FakeES]:
    """Le faux client à la place de `_es`, vide ; un test le remplit (`estate_ids`)."""
    fake = FakeES()
    app.dependency_overrides[estate_search_router._es] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(estate_search_router._es, None)


def new_estates(db_client: TestClient, count: int) -> list[int]:
    """`count` biens neufs, aux références SUG8-0001 et suivantes."""
    ids = []
    for n in range(1, count + 1):
        created = post_as_hunter(db_client, "/estates", {**ESTATE, "reference": f"SUG8-{n:04d}"})
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])
    return ids


def suggest(db_client: TestClient, request_id: int, user_id: int = HUNTER_ID):
    """POST des suggestions, sous le chasseur `user_id`."""
    with acting_as(HUNTER, user_id):
        return db_client.post(f"/search-requests/{request_id}/suggestions")


def selection(db_client: TestClient, request_id: int) -> list[dict[str, Any]]:
    """Les lignes de sélection de la demande, lues par l'Admin."""
    rows = db_client.get("/estate-search-requests", params={"limit": 500}).json()
    return [row for row in rows if row["id_search_request"] == request_id]


# --- le cas nominal -------------------------------------------------------------


def test_suggestions_are_written_as_suggested(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client)
    fake_es.estate_ids = new_estates(db_client, 3)

    response = suggest(db_client, request_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert [row["id_estate"] for row in body] == fake_es.estate_ids
    assert {(row["status"], row["id_hunter"], row["id_search_request"]) for row in body} == {
        ("suggested", HUNTER_PROFILE, request_id)
    }
    assert len(selection(db_client, request_id)) == 3


def test_query_comes_from_the_latest_criteria(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client)  # première version : Appartement, 300 000 €
    first = db_client.get("/criteria", params={"limit": 500}).json()
    first_id = next(row["id"] for row in first if row["id_search_request"] == request_id)
    latest = {"id_author": HUNTER_ID, "id_search_request": request_id, "estate_type": "Maison",
              "budget_max": 450000, "id_previous_version": first_id, "change_reason": "Le client veut une maison."}
    assert post_as_hunter(db_client, "/criteria", latest).status_code == 201

    assert suggest(db_client, request_id).status_code == 201
    filters = fake_es.calls[0]["query"]["bool"]["filter"]
    assert {"term": {"estate_type": "Maison"}} in filters
    assert {"range": {"price": {"lte": 450000}}} in filters


def test_never_more_than_ten(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client)
    fake_es.estate_ids = new_estates(db_client, 12)

    response = suggest(db_client, request_id)
    assert response.status_code == 201, response.text
    assert len(response.json()) == 10
    assert fake_es.calls[0]["size"] == 10


# --- les exclusions -------------------------------------------------------------


def test_sold_estate_is_not_suggested(db_client: TestClient, fake_es: FakeES):
    sale = post_as_manager(db_client, "/sales", sale_payload(db_client))
    assert sale.status_code == 201, sale.text
    sold = sale.json()["id_estate"]
    request_id = new_request(db_client)
    fresh = new_estates(db_client, 1)
    fake_es.estate_ids = [sold, *fresh]

    response = suggest(db_client, request_id)
    assert response.status_code == 201, response.text
    assert [row["id_estate"] for row in response.json()] == fresh
    assert str(sold) in fake_es.calls[0]["query"]["bool"]["must_not"][0]["ids"]["values"]


def test_dismissed_estate_is_not_written_again(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client)
    dismissed, fresh = new_estates(db_client, 2)
    row = {"id_estate": dismissed, "id_search_request": request_id, "id_hunter": HUNTER_PROFILE, "status": "dismissed"}
    assert post_as_hunter(db_client, "/estate-search-requests", row).status_code == 201
    fake_es.estate_ids = [dismissed, fresh]

    response = suggest(db_client, request_id)
    assert response.status_code == 201, response.text
    assert [row["id_estate"] for row in response.json()] == [fresh]
    states = {r["id_estate"]: r["status"] for r in selection(db_client, request_id)}
    assert states == {dismissed: "dismissed", fresh: "suggested"}


# --- les refus ------------------------------------------------------------------


def test_another_hunter_gets_404(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client)
    fake_es.estate_ids = new_estates(db_client, 1)

    response = suggest(db_client, request_id, OTHER_HUNTER)
    assert response.status_code == 404, response.text
    assert selection(db_client, request_id) == []


def test_client_cannot_ask_for_suggestions(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client)
    with acting_as(CLIENT, 7):  # l'auteur de la demande : c'est le travail du chasseur
        response = db_client.post(f"/search-requests/{request_id}/suggestions")
    assert response.status_code == 403, response.text


def test_request_without_criteria_returns_409(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client, with_criteria=False)

    response = suggest(db_client, request_id)
    assert response.status_code == 409, response.text
    assert fake_es.calls == []


def test_elasticsearch_down_returns_503(db_client: TestClient, fake_es: FakeES):
    request_id = new_request(db_client)
    fake_es.error = ESConnectionError("Elasticsearch absent")

    response = suggest(db_client, request_id)
    assert response.status_code == 503, response.text
    assert selection(db_client, request_id) == []
