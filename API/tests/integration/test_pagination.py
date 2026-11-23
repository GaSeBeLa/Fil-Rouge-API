"""
test_pagination.py — Les listes de l'API se lisent par pages (choix PAGIN, 2026-11-23).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Avant : `GET /estates` rendait toute la table d'un coup (1,25 s pour
3 219 biens, contre 70 ms pour un seul ; mesure du 2026-11-20). OWASP API
n° 4 : une liste doit avoir une taille bornée.

Toutes les listes du routeur commun (`crud_router.py`) prennent
`?limit=` (100 par défaut, 1 000 au plus) et `?offset=` (0 par défaut),
dans l'ordre des `id`. L'en-tête `X-Total-Count` dit combien de lignes
la liste entière compte, pour savoir s'il reste des pages. « Le sien »
s'applique avant : un chasseur ne compte que ses lignes.
============================================================================
"""

import pytest
from fastapi.testclient import TestClient

from src.app.utils.roles import HUNTER

from ..conftest import acting_as
from .test_constraints_db import ESTATE, HUNTER_ID, post_as_hunter


def new_estates(db_client: TestClient, count: int) -> list[int]:
    """Crée `count` biens (sous le chasseur 1) ; rend leurs id."""
    ids = []
    for n in range(count):
        response = post_as_hunter(db_client, "/estates", {**ESTATE, "reference": f"PAGE-{n:04d}"})
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


def test_a_page_is_cut_by_limit_and_offset_in_id_order(db_client: TestClient):
    new_estates(db_client, 5)
    every_id = [e["id"] for e in db_client.get("/estates?limit=1000").json()]

    page = db_client.get("/estates?limit=2&offset=1")

    assert page.status_code == 200, page.text
    assert [e["id"] for e in page.json()] == every_id[1:3]
    assert every_id == sorted(every_id)


def test_the_total_count_header_counts_the_whole_list(db_client: TestClient):
    new_estates(db_client, 3)
    total = len(db_client.get("/estates?limit=1000").json())

    page = db_client.get("/estates?limit=1")

    assert len(page.json()) == 1
    assert page.headers["X-Total-Count"] == str(total)


def test_the_default_page_holds_100_rows(db_client: TestClient):
    new_estates(db_client, 101)

    page = db_client.get("/estates")

    assert len(page.json()) == 100
    assert int(page.headers["X-Total-Count"]) >= 101


@pytest.mark.parametrize("query", ["limit=0", "limit=1001", "offset=-1", "limit=abc"])
def test_an_out_of_range_page_returns_422(db_client: TestClient, query: str):
    assert db_client.get(f"/estates?{query}").status_code == 422


def test_the_total_count_follows_the_own_rows_rule(db_client: TestClient):
    # « Le sien » (ADR-027) : le chasseur ne compte que ses mandats.
    with acting_as(HUNTER, HUNTER_ID):
        page = db_client.get("/mandates?limit=1000")
    assert page.status_code == 200, page.text
    assert page.headers["X-Total-Count"] == str(len(page.json()))
    assert len(page.json()) < len(db_client.get("/mandates?limit=1000").json())
