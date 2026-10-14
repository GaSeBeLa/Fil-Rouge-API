"""
test_erreurs_api.py — Le 409 nomme la contrainte, le 500 donne un numéro.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Fiche FIN1 (décisions de Seb, Discord, 2026-10-14) :

- 409 = phrase + nom : un refus de la base dit sa sorte et nomme la
  contrainte, sans jamais recopier la valeur refusée ;
- 500 = message neutre + numéro : le même numéro dans la réponse et dans le
  log, avec la pile.

Le 500 se lit avec `raise_server_exceptions=False` : Starlette relance
l'exception après la réponse (ServerErrorMiddleware), le TestClient la
lèverait dans le test sinon.
============================================================================
"""

import logging
import re
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from src.app.conf.database import get_session
from src.app.main import app
from src.app.utils.roles import ADMIN, HUNTER, get_principal

from ..conftest import TEST_HEADERS, acting_as, principal_as
from .conftest import USER_PASSWORD

EMAIL = "doublon@exemple.fr"
UNKNOWN_CLIENT = 999999
HUNTER_ID = 1  # chasseur posé par 02 : il crée les demandes (Q-ACC-15)


def test_duplicate_email_names_the_constraint_without_the_email(
    db_client: TestClient, create_user: Callable[[str], int]
):
    create_user(EMAIL)
    response = db_client.post("/users", json={"email": EMAIL, "password": USER_PASSWORD, "id_role": 1})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "user_email_key" in detail
    assert EMAIL not in detail


def test_unknown_client_names_the_foreign_key(db_client: TestClient):
    payload = {"id_author": HUNTER_ID, "id_client": UNKNOWN_CLIENT, "id_hunter": HUNTER_ID, "status": "accepted"}
    with acting_as(HUNTER, HUNTER_ID):
        response = db_client.post("/search-requests", json=payload)
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "search_request_id_client_fkey" in detail
    assert str(UNKNOWN_CLIENT) not in detail


@pytest.fixture
def broken_client() -> Iterator[TestClient]:
    """La vraie app, dont la session lève RuntimeError : une panne imprévue."""

    def broken_session() -> Iterator[None]:
        raise RuntimeError("panne simulée")
        yield  # pragma: no cover — fait de cette fonction un générateur, comme get_session

    app.dependency_overrides[get_session] = broken_session
    app.dependency_overrides[get_principal] = principal_as(ADMIN)
    try:
        yield TestClient(app, headers=TEST_HEADERS, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_principal, None)


def test_unexpected_error_returns_500_with_logged_reference(
    broken_client: TestClient, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.ERROR, logger="src.app.main"):
        response = broken_client.get("/users")
    assert response.status_code == 500
    match = re.fullmatch(r"Erreur interne\. Référence : ([0-9a-f]{8})\.", response.json()["detail"])
    assert match is not None, response.json()
    reference = match.group(1)
    logged = [record for record in caplog.records if reference in record.getMessage()]
    assert logged, caplog.text
    assert logged[0].exc_info is not None  # la pile est dans le log
    assert "panne simulée" not in response.text  # rien de l'erreur dans la réponse
