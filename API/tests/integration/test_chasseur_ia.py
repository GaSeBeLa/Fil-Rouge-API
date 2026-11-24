"""
test_chasseur_ia.py — Le chasseur IA a des droits réduits (ADR-058).

Un chasseur IA garde le rôle `Hunter` et sa fiche ; `hunter.is_hunter_ai`
réduit ses droits, par une liste blanche fermée par défaut
(`utils/roles.py`, AI_HUNTER_ALLOWED). Il lit ses demandes, ses mandats et
les biens, et il propose des biens ; tout le reste rend 403 :

- rien qui engage de l'argent ou un contrat (offre, vente, paiement, mandat) ;
- pas le contact du vendeur (ADR-054) ;
- pas de visite : il ne visite pas (question ouverte de l'ADR, tranchée ici) ;
- rien d'écrit par un humain ne change sous sa main (critères, biens,
  photos, notes, sa fiche, son compte).

Le chasseur 1 du seed 02 (compte 1, fiche 1001, demande et mandat 15) passe
chasseur IA dans la transaction du test, annulée à la fin.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, update

from src.app.main import app
from src.app.models import Hunter
from src.app.utils.roles import AI_HUNTER_ALLOWED, HUNTER, ai_hunter_may

from ..conftest import acting_as
from .test_constraints_db import ACTIVE_MANDATE, ACTIVE_REQUEST, ESTATE, HUNTER_ID, HUNTER_PROFILE, post_as_hunter


def make_ai(db_session: Session, is_ai: bool = True) -> None:
    """Le chasseur 1 devient chasseur IA (ou redevient humain) le temps du test."""
    db_session.exec(update(Hunter).where(col(Hunter.id) == HUNTER_PROFILE).values(is_hunter_ai=is_ai))
    db_session.commit()


def call(db_client: TestClient, method: str, path: str, body: Any = None):
    """Un appel sous le compte du chasseur 1, avec un corps pour POST et PUT."""
    with acting_as(HUNTER, HUNTER_ID):
        if method in ("POST", "PUT"):
            return db_client.request(method, path, json=body if body is not None else {})
        return db_client.request(method, path)


# Ce que le chasseur IA ne peut pas faire, et qu'un chasseur humain peut
# tenter (le rôle Hunter lui ouvre la route).
FORBIDDEN: list[tuple[str, str]] = [
    ("GET", "/estate-contacts"),            # contact du vendeur (ADR-054)
    ("GET", "/payments"),                   # argent
    ("GET", "/sales"),                      # contrat
    ("POST", "/mandates"),                  # contrat
    ("PUT", f"/mandates/{ACTIVE_MANDATE}"),
    ("POST", "/visits"),                    # il ne visite pas
    ("POST", "/criteria"),                  # les souhaits du client
    ("POST", "/estates"),                   # un bien est saisi par un humain
    ("POST", "/pictures"),
    ("POST", "/review-media"),
    ("PUT", f"/hunters/{HUNTER_PROFILE}"),  # sa propre fiche
    ("PUT", f"/users/{HUNTER_ID}"),         # son compte
]


@pytest.mark.parametrize(("method", "path"), FORBIDDEN)
def test_ai_hunter_gets_403_outside_the_whitelist(db_client: TestClient, db_session: Session, method: str, path: str):
    make_ai(db_session)
    response = call(db_client, method, path)
    assert response.status_code == 403, response.text
    assert "ADR-058" in response.json()["detail"]


@pytest.mark.parametrize(("method", "path"), [("GET", "/estate-contacts"), ("GET", "/payments"), ("GET", "/sales")])
def test_human_hunter_keeps_these_reads(db_client: TestClient, db_session: Session, method: str, path: str):
    make_ai(db_session, is_ai=False)
    assert call(db_client, method, path).status_code == 200


@pytest.mark.parametrize(
    "path", ["/search-requests", f"/search-requests/{ACTIVE_REQUEST}", "/criteria", "/mandates",
             f"/mandates/{ACTIVE_MANDATE}", "/estates", "/pictures", "/estate-search-requests", "/estate-proposed"],
)
def test_ai_hunter_reads_its_work(db_client: TestClient, db_session: Session, path: str):
    make_ai(db_session)
    assert call(db_client, "GET", path).status_code == 200


def test_ai_hunter_selects_keeps_and_proposes_an_estate(db_client: TestClient, db_session: Session):
    # Le bien est saisi par le chasseur encore humain : l'IA ne crée pas de bien.
    estate = post_as_hunter(db_client, "/estates", {**ESTATE, "reference": "TEST-IA-0001"})
    assert estate.status_code == 201, estate.text
    estate_id = estate.json()["id"]
    make_ai(db_session)

    selection = {"id_estate": estate_id, "id_search_request": ACTIVE_REQUEST, "id_hunter": HUNTER_PROFILE, "status": "suggested"}
    added = call(db_client, "POST", "/estate-search-requests", selection)
    assert added.status_code == 201, added.text
    kept = call(db_client, "PUT", f"/estate-search-requests/{added.json()['id']}", {**selection, "status": "kept"})
    assert kept.status_code == 200, kept.text
    proposal = {"proposition_status": "proposed", "id_hunter": HUNTER_PROFILE, "id_estate": estate_id, "id_mandate": ACTIVE_MANDATE}
    proposed = call(db_client, "POST", "/estate-proposed", proposal)
    assert proposed.status_code == 201, proposed.text

    # Une fois proposée, la ligne ne change plus sous sa main.
    changed = call(db_client, "PUT", f"/estate-proposed/{proposed.json()['id']}", {**proposal, "client_priority": 1})
    assert changed.status_code == 403, changed.text


def test_whitelist_is_closed_by_default():
    assert not ai_hunter_may("GET", "/route-ajoutee-demain")
    assert not ai_hunter_may("DELETE", "/estate-proposed/{item_id}")
    assert ai_hunter_may("POST", "/estate-proposed")


def test_every_whitelisted_route_exists():
    """Une faute de frappe dans la liste blanche fermerait une route sans bruit."""
    paths = app.openapi()["paths"]
    missing = [(m, p) for m, p in AI_HUNTER_ALLOWED if m.lower() not in paths.get(p, {})]
    assert missing == []
