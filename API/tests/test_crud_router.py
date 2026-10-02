"""
test_crud_router.py — Tests unitaires de build_crud_router, sans base.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
On construit une mini-application FastAPI qui ne contient QUE le router
généré par build_crud_router, branché sur un service factice (MagicMock).
La dépendance get_session est remplacée (dependency_overrides) : aucune
session PostgreSQL n'est jamais ouverte.

Ce qu'on prouve : la traduction des erreurs "métier" en codes HTTP, qui
vaut pour les 18 ressources de l'API.

- NotFoundError -> 404, avec le message du service
- ConflictError -> 409, avec le message du service
- POST réussi -> 201
- id non entier -> 422 (FastAPI), sans appeler le service
============================================================================
"""

from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from src.app.conf.database import get_session
from src.app.routes.crud_router import build_crud_router
from src.app.services.base_service import BaseService
from src.app.utils.exceptions import ConflictError, NotFoundError

NOT_FOUND = "Chose introuvable"
CONFLICT = "Contrainte violée"


class Thing(SQLModel):
    """Modèle minimal, pas une table : seul le router est testé."""

    id: Optional[int] = None
    name: str


@pytest.fixture
def service() -> MagicMock:
    return MagicMock(spec=BaseService)


@pytest.fixture
def api(service: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(build_crud_router(service=service, prefix="/things", tag="things", response_model=Thing))
    app.dependency_overrides[get_session] = lambda: None
    return TestClient(app)


def test_list_returns_200(api: TestClient, service: MagicMock):
    service.list_all.return_value = [Thing(id=1, name="a")]
    response = api.get("/things")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "a"}]


def test_get_unknown_id_returns_404(api: TestClient, service: MagicMock):
    service.get_by_id.side_effect = NotFoundError(NOT_FOUND)
    response = api.get("/things/999")
    assert response.status_code == 404
    assert response.json() == {"detail": NOT_FOUND}


def test_get_non_integer_id_returns_422_without_calling_service(api: TestClient, service: MagicMock):
    response = api.get("/things/abc")
    assert response.status_code == 422
    service.get_by_id.assert_not_called()


def test_post_returns_201(api: TestClient, service: MagicMock):
    service.create.return_value = Thing(id=1, name="a")
    response = api.post("/things", json={"name": "a"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "a"}


def test_post_conflict_returns_409(api: TestClient, service: MagicMock):
    service.create.side_effect = ConflictError(CONFLICT)
    response = api.post("/things", json={"name": "a"})
    assert response.status_code == 409
    assert response.json() == {"detail": CONFLICT}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(NotFoundError(NOT_FOUND), 404), (ConflictError(CONFLICT), 409)],
)
def test_put_translates_errors(api: TestClient, service: MagicMock, error: Exception, expected_status: int):
    service.replace.side_effect = error
    response = api.put("/things/1", json={"name": "b"})
    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(NotFoundError(NOT_FOUND), 404), (ConflictError(CONFLICT), 409)],
)
def test_delete_translates_errors(api: TestClient, service: MagicMock, error: Exception, expected_status: int):
    service.delete.side_effect = error
    response = api.delete("/things/1")
    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}
