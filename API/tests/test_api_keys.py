"""
test_api_keys.py — La clé d'API par programme (ADR-028, points 4 à 6, fiche API3).

Sans base : la vraie app, avec une session factice qui rend un compte
activé et son rôle. Le jeton, lui, est un vrai jeton signé : la chaîne
clé -> jeton -> compte -> rôle est celle de la production.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from src.app.conf.database import get_session
from src.app.main import app
from src.app.models import Role, User
from src.app.utils import api_keys
from src.app.utils.security import create_access_token

from .conftest import TEST_API_KEY, TEST_HEADERS

USER = User(id=7, email="cle@test.local", password="-", is_activated=True, id_role=4)
ROLE = Role(id=4, wording="Admin")


def _fake_session() -> MagicMock:
    session = MagicMock()
    session.get.side_effect = lambda model, _id: USER if model is User else ROLE
    return session


@pytest.fixture
def client() -> Iterator[TestClient]:
    """La vraie app, sans clé par défaut ; session factice, aucun rôle remplacé."""
    app.dependency_overrides[get_session] = _fake_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(7)}"}


def test_no_key_returns_401(client: TestClient):
    assert client.get("/roles", headers=_bearer()).status_code == 401
    assert client.post("/auth/login", json={"email": "a", "password": "b"}).status_code == 401


def test_unknown_key_returns_401(client: TestClient):
    headers = {**_bearer(), api_keys.API_KEY_HEADER: "une-cle-que-personne-ne-connait-0000000"}
    assert client.get("/roles", headers=headers).status_code == 401


def test_good_key_and_good_token_returns_200(client: TestClient):
    response = client.get("/auth/me", headers={**_bearer(), **TEST_HEADERS})

    assert response.status_code == 200, response.text
    assert response.json()["id"] == 7


def test_good_key_without_token_returns_401(client: TestClient):
    assert client.get("/roles", headers=TEST_HEADERS).status_code == 401


def test_health_needs_no_key(client: TestClient):
    assert client.get("/").status_code == 200


def test_calling_program_name_is_kept_for_logs():
    small = FastAPI()

    @small.get("/whoami", dependencies=[Depends(api_keys.require_api_key)])
    def whoami(request: Request) -> str:
        return request.state.api_client

    response = TestClient(small).get("/whoami", headers={api_keys.API_KEY_HEADER: TEST_API_KEY})
    assert response.json() == "TEST"


# --- Lecture des variables au démarrage ---------------------------------------


@pytest.fixture
def no_api_key_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for variable in list(api_keys.os.environ):
        if variable.startswith(api_keys.API_KEY_PREFIX):
            monkeypatch.delenv(variable)
    return monkeypatch


def test_load_reads_every_api_key_variable(no_api_key_env: pytest.MonkeyPatch):
    no_api_key_env.setenv("API_KEY_FRONT", "f" * 64)
    no_api_key_env.setenv("API_KEY_BATCH", "b" * 64)
    no_api_key_env.setenv("API_KEY_VIDE", "")  # ignorée, avec un avertissement

    assert api_keys._load_api_keys() == {"FRONT": "f" * 64, "BATCH": "b" * 64}


def test_load_refuses_to_start_without_any_key(no_api_key_env: pytest.MonkeyPatch):
    with pytest.raises(RuntimeError, match="Aucune clé"):
        api_keys._load_api_keys()


def test_load_refuses_a_short_key(no_api_key_env: pytest.MonkeyPatch):
    no_api_key_env.setenv("API_KEY_FRONT", "court")
    with pytest.raises(RuntimeError, match="trop courte"):
        api_keys._load_api_keys()
