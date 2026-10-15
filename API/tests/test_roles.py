"""
test_roles.py — Les rôles sur les routes CRUD (ADR-028, fiche API2).

Sans base : une petite app monte build_crud_router sur un service factice
(MagicMock), plus le vrai routeur /hunter-performances ; get_session rend
None. get_principal est remplacé par un compte du rôle voulu ; en fin de
fichier, get_principal lui-même, sur une session factice (PRF7). La chaîne
réelle (jeton -> compte -> rôle relu en base) est prouvée dans
tests/integration/test_roles_db.py.
"""

from typing import Any, Optional, cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from src.app.conf.database import get_session
from src.app.models import Client, Hunter, RealEstateManager, User
from src.app.routes import hunter_performance_router, role_router, user_router
from src.app.routes.crud_router import build_crud_router
from src.app.services.base_service import BaseService
from src.app.utils.roles import ADMIN, ALL_ROLES, CLIENT, HUNTER, MANAGER, READER, WRITER_ROLES, get_principal

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
    mock.create_as.return_value = Thing(id=2, name="b")
    return mock


@pytest.fixture
def test_app(service: MagicMock) -> FastAPI:
    app = FastAPI()
    # Les droits d'avant DRO1, déclarés : tout compte lit, Reader n'écrit pas.
    things = build_crud_router(
        service=service,
        prefix="/things",
        tag="things",
        response_model=Thing,
        read_roles=ALL_ROLES,
        write_roles=WRITER_ROLES,
    )
    app.include_router(things)
    # Aucun rôle déclaré : fermé à tous (DRO1).
    app.include_router(build_crud_router(service=service, prefix="/closed", tag="closed", response_model=Thing))
    app.include_router(hunter_performance_router.router)
    app.include_router(user_router.router)
    app.include_router(role_router.router)
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
    service.create_as.assert_not_called()
    service.replace_visible.assert_not_called()


def test_admin_can_create(test_app: FastAPI):
    response = client_as(test_app, ADMIN).post("/things", json={"name": "b"})

    assert response.status_code == 201
    assert response.json() == {"id": 2, "name": "b"}


@pytest.mark.parametrize("role", [ADMIN, CLIENT, HUNTER, MANAGER, READER])
def test_router_without_roles_is_closed_to_all(test_app: FastAPI, service: MagicMock, role: str):
    # DRO1 : fermé par défaut ; une table ouvre ce que la cible lui donne.
    client = client_as(test_app, role)

    assert client.get("/closed").status_code == 403
    assert client.get("/closed/1").status_code == 403
    assert client.post("/closed", json={"name": "b"}).status_code == 403
    assert client.put("/closed/1", json={"name": "b"}).status_code == 403
    service.list_all.assert_not_called()
    service.create_as.assert_not_called()


def test_hunter_performance_closed_to_writes_even_for_admin(test_app: FastAPI):
    # ADR-035 : jamais saisie à la main ; PaymentService l'écrit au passage à 'paid' (API12).
    client = client_as(test_app, ADMIN)

    assert client.post("/hunter-performances", json=SCORE).status_code == 403
    assert client.put("/hunter-performances/1", json=SCORE).status_code == 403


@pytest.mark.parametrize("role", [CLIENT, HUNTER, MANAGER, READER])
def test_only_admin_creates_users(test_app: FastAPI, role: str):
    # Sinon un compte choisissait son system_role, donc se créait Admin.
    body = {"email": "x@exemple.fr", "password": "un-mot-de-passe-assez-long"}

    assert client_as(test_app, role).post("/users", json=body).status_code == 403


def test_reader_does_not_update_users(test_app: FastAPI):
    # Sinon un compte changeait le mot de passe d'un Admin, puis se
    # connectait à sa place (relecture de la série API). Le Client, le
    # Hunter et le Manager modifient leur seul compte (DRO5, DRO6, DRO7,
    # tests/integration/test_le_sien.py).
    role = READER
    response = client_as(test_app, role).put("/users/1", json={"password": "un-autre-mot-de-passe"})

    assert response.status_code == 403


@pytest.mark.parametrize("role", [ADMIN, CLIENT, HUNTER, MANAGER, READER])
def test_nobody_writes_roles(test_app: FastAPI, role: str):
    # Sinon un Client supprimait le rôle Admin vide, puis renommait le sien
    # en « Admin » : tous les Clients devenaient Admin. Depuis DRO1, l'Admin
    # non plus (ADR-027, annexe § 1) : les 5 rôles viennent du seed.
    client = client_as(test_app, role)

    assert client.post("/roles", json={"wording": "Admin"}).status_code == 403
    assert client.put("/roles/1", json={"wording": "Admin"}).status_code == 403


def test_health_and_login_stay_open():
    from src.app.main import app

    client = TestClient(app)
    assert client.get("/").status_code == 200
    # Corps invalide : 422, pas 401 — la route ne demande aucun jeton
    # (mais la clé d'API, oui : fiche API3).
    assert client.post("/auth/login", json={}, headers=TEST_HEADERS).status_code == 422


# --- get_principal : le rôle lu sur system_role ou sur la fiche (PRF7) ---


class FakeSession:
    """Session sans base : (id, role_wording) de la fiche du compte, dans la seule table `table`."""

    def __init__(self, table: Optional[type] = None, row: Optional[tuple[int, str]] = None):
        self.table = table
        self.row = row

    def exec(self, statement: Any) -> MagicMock:
        result = MagicMock()
        entity = statement.column_descriptions[0]["entity"]
        result.first.return_value = self.row if entity is self.table else None
        return result


def account(system_role: Optional[str] = None) -> User:
    return User(id=7, email="compte@test.local", password="-", is_activated=True, system_role=system_role)


@pytest.mark.parametrize(
    ("table", "role"), [(Client, CLIENT), (Hunter, HUNTER), (RealEstateManager, MANAGER)]
)
def test_role_and_profile_id_come_from_the_profile(table: type, role: str):
    principal = get_principal(account(), cast(Session, FakeSession(table, (1042, role))))

    assert (principal.role, principal.profile_id) == (role, 1042)


@pytest.mark.parametrize("role", [ADMIN, READER])
def test_role_comes_from_system_role_without_profile(role: str):
    principal = get_principal(account(system_role=role), cast(Session, FakeSession()))

    assert (principal.role, principal.profile_id) == (role, None)


def test_account_without_profile_nor_system_role_gets_403():
    with pytest.raises(HTTPException) as refused:
        get_principal(account(), cast(Session, FakeSession()))

    assert refused.value.status_code == 403
