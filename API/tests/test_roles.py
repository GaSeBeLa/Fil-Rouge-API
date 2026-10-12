"""
test_roles.py — Les rôles sur les routes CRUD (ADR-028, fiche API2).

Sans base : une petite app monte build_crud_router sur un service factice
(MagicMock), plus le vrai routeur /hunter-performances ; get_session rend
None. get_principal est remplacé par un compte du rôle voulu. La chaîne
réelle (jeton -> compte -> rôle relu en base) est prouvée dans
tests/integration/test_roles_db.py.
"""

from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from src.app.conf.database import get_session
from src.app.routes import hunter_performance_router
from src.app.routes.crud_router import build_crud_router
from src.app.services.base_service import BaseService
from src.app.utils.roles import ADMIN, READER, get_principal

from .conftest import TEST_HEADERS, principal_as


class Thing(SQLModel):
    """Modèle minimal, pas une table : seuls les droits sont testés."""

    id: Optional[int] = None
    name: str


SCORE = {"score": "62.5", "scored_at": "2026-03-02T10:00:00Z", "trigger_type": "initial", "id_hunter": 1}


@pytest.fixture
def service() -> MagicMock:
    mock = MagicMock(spec=BaseService)
    mock.list_all.return_value = [Thing(id=1, name="a")]
    mock.create.return_value = Thing(id=2, name="b")
    return mock


@pytest.fixture
def test_app(service: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(build_crud_router(service=service, prefix="/things", tag="things", response_model=Thing))
    app.include_router(hunter_performance_router.router)
    app.dependency_overrides[get_session] = lambda: None
    return app


def client_as(app: FastAPI, role: str) -> TestClient:
    app.dependency_overrides[get_principal] = principal_as(role)
    return TestClient(app, headers=TEST_HEADERS)


def test_no_token_returns_401(test_app: FastAPI, service: MagicMock):
    client = TestClient(test_app, headers=TEST_HEADERS)  # get_principal non remplacé : vraie chaîne

    assert client.get("/things").status_code == 401
    assert client.post("/things", json={"name": "b"}).status_code == 401
    service.list_all.assert_not_called()


def test_reader_can_read(test_app: FastAPI):
    response = client_as(test_app, READER).get("/things")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "a"}]


def test_reader_cannot_write(test_app: FastAPI, service: MagicMock):
    # ADR-028 : Reader consulte sans écrire.
    client = client_as(test_app, READER)

    assert client.post("/things", json={"name": "b"}).status_code == 403
    assert client.put("/things/1", json={"name": "b"}).status_code == 403
    assert client.delete("/things/1").status_code == 403
    service.create.assert_not_called()
    service.replace.assert_not_called()
    service.delete.assert_not_called()


def test_admin_can_create(test_app: FastAPI):
    response = client_as(test_app, ADMIN).post("/things", json={"name": "b"})

    assert response.status_code == 201
    assert response.json() == {"id": 2, "name": "b"}


def test_hunter_performance_closed_to_writes_even_for_admin(test_app: FastAPI):
    # ADR-035 : jamais saisie à la main ; le service d'API12 l'écrira.
    client = client_as(test_app, ADMIN)

    assert client.post("/hunter-performances", json=SCORE).status_code == 403
    assert client.put("/hunter-performances/1", json=SCORE).status_code == 403


def test_health_and_login_stay_open():
    from src.app.main import app

    client = TestClient(app)
    assert client.get("/").status_code == 200
    # Corps invalide : 422, pas 401 — la route ne demande aucun jeton
    # (mais la clé d'API, oui : fiche API3).
    assert client.post("/auth/login", json={}, headers=TEST_HEADERS).status_code == 422
