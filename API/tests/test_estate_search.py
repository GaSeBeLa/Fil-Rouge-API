"""
test_estate_search.py — GET /estates/search (chantier FLX, fiche FLX9).

Sans Elasticsearch : le client est remplacé par un faux (`FakeES`), qui
garde la dernière requête reçue et rend une réponse au format de l'API
_search. La requête `bool` est testée à part (fonction pure).
"""

from collections.abc import Iterator
from typing import Any

import pytest
from elasticsearch import ConnectionError as ESConnectionError
from fastapi.testclient import TestClient

from src.app.main import app
from src.app.routes import estate_search_router
from src.app.services.estate_search_service import build_query
from src.app.utils.roles import CLIENT, get_principal

from .conftest import TEST_HEADERS, principal_as


class FakeES:
    def __init__(self, hits: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self.hits = hits or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {"hits": {"total": {"value": len(self.hits)}, "hits": self.hits}}


MOULINS = {"_id": "7", "_source": {"id": 7, "town": "Moulins", "estate_type": "Maison", "price": 180000}}


@pytest.fixture
def fake_es() -> Iterator[FakeES]:
    fake = FakeES(hits=[MOULINS])
    app.dependency_overrides[estate_search_router._es] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(estate_search_router._es, None)


# --- la route ---

def test_search_route_answers(client: TestClient, fake_es: FakeES):
    # Inclus après estate_router, « search » serait lu comme un id : 422.
    res = client.get("/estates/search", params={"city": "Moulins"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"] == [{"id": 7, "town": "Moulins", "estate_type": "Maison", "price": 180000}]
    assert fake_es.calls[0]["index"] == "estates"


def test_search_open_to_client_role(fake_es: FakeES):
    app.dependency_overrides[get_principal] = principal_as(CLIENT)
    try:
        res = TestClient(app, headers=TEST_HEADERS).get("/estates/search")
    finally:
        app.dependency_overrides.pop(get_principal, None)
    assert res.status_code == 200, res.text


def test_search_needs_a_token(fake_es: FakeES):
    res = TestClient(app, headers=TEST_HEADERS).get("/estates/search")
    assert res.status_code == 401


def test_search_503_when_elasticsearch_is_down(client: TestClient, fake_es: FakeES, caplog):
    fake_es.error = ESConnectionError("connexion refusée")
    res = client.get("/estates/search", params={"q": "jardin"})
    assert res.status_code == 503
    assert "Elasticsearch" in res.json()["detail"]
    assert "Recherche Elasticsearch en échec" in caplog.text


def test_search_503_when_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog):
    for name in ("ES_URL", "ES_API_USER", "ES_API_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    res = client.get("/estates/search")
    assert res.status_code == 503
    assert "ES_API_PASSWORD" in caplog.text


def test_search_paging(client: TestClient, fake_es: FakeES):
    res = client.get("/estates/search", params={"page": 3, "size": 10})
    assert res.status_code == 200
    assert (fake_es.calls[0]["from_"], fake_es.calls[0]["size"]) == (20, 10)


@pytest.mark.parametrize("params", [
    {"lat": 46.5, "lon": 3.3},                 # rayon manquant
    {"price_min": 300000, "price_max": 100000},
    {"type": "Cabane"},                        # hors du CHECK de estate_type
    {"size": 101},
])
def test_search_rejects_bad_params(client: TestClient, fake_es: FakeES, params: dict[str, Any]):
    assert client.get("/estates/search", params=params).status_code == 422
    assert fake_es.calls == []


# --- la requête bool ---

def test_query_without_criteria_matches_all():
    assert build_query() == {"match_all": {}}


def test_query_text_in_must_rest_in_filter():
    query = build_query(q="jardin", city="Moulins", estate_type="Maison", price_min=100000,
                        price_max=200000, surface_min=50)
    assert query["bool"]["must"] == [{"match": {"information": "jardin"}}]
    assert query["bool"]["filter"] == [
        {"term": {"town": "Moulins"}},
        {"term": {"estate_type": "Maison"}},
        {"range": {"price": {"gte": 100000, "lte": 200000}}},
        {"range": {"surface": {"gte": 50}}},
    ]


def test_query_geo_distance():
    query = build_query(lat=46.56, lon=3.33, radius_km=20)
    assert query["bool"]["filter"] == [
        {"geo_distance": {"distance": "20km", "location": {"lat": 46.56, "lon": 3.33}}}
    ]
