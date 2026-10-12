"""
test_auth.py — Connexion par jeton JWT (ADR-052), sur la base de test.

Ici et pas dans tests/ : la règle à prouver est la RELECTURE du compte en
base à chaque appel, qui demande une vraie base (fixtures db_client).
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from src.app.utils.security import JWT_ALGORITHM, create_access_token

from .conftest import USER_PASSWORD


@pytest.fixture
def make_user(db_client: TestClient) -> Callable[..., int]:
    """Crée un compte (rôle 1 = Client) et renvoie son id."""

    def _make(email: str, is_activated: bool = True) -> int:
        response = db_client.post(
            "/users",
            json={"email": email, "password": USER_PASSWORD, "id_role": 1, "is_activated": is_activated},
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return _make


def _login(client: TestClient, email: str, password: str = USER_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def _me(client: TestClient, token: str):
    return client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_login_success_returns_token(db_client: TestClient, make_user: Callable[..., int]) -> None:
    user_id = make_user("auth-ok@example.com")

    response = _login(db_client, "auth-ok@example.com")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600  # ADR-052 : 60 minutes
    me = _me(db_client, body["access_token"])
    assert me.status_code == 200, me.text
    assert me.json()["id"] == user_id
    assert "password" not in me.json()


def test_login_wrong_password_401(db_client: TestClient, make_user: Callable[..., int]) -> None:
    make_user("auth-bad-pw@example.com")

    response = _login(db_client, "auth-bad-pw@example.com", "pas-le-bon-mot-de-passe")

    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_login_inactive_account_401_same_message(db_client: TestClient, make_user: Callable[..., int]) -> None:
    make_user("auth-active@example.com")
    make_user("auth-inactive@example.com", is_activated=False)

    inactive = _login(db_client, "auth-inactive@example.com")
    wrong_pw = _login(db_client, "auth-active@example.com", "pas-le-bon-mot-de-passe")

    assert inactive.status_code == 401
    # Même message : un inconnu ne doit pas apprendre qu'un compte existe.
    assert inactive.json()["detail"] == wrong_pw.json()["detail"]


def test_login_unknown_email_401(db_client: TestClient) -> None:
    assert _login(db_client, "auth-personne@example.com").status_code == 401


def test_expired_token_401(db_client: TestClient, make_user: Callable[..., int]) -> None:
    user_id = make_user("auth-expired@example.com")
    expired = create_access_token(user_id, expires_delta=timedelta(seconds=-1))

    assert _me(db_client, expired).status_code == 401


def test_account_deactivated_after_token_issued_401(db_client: TestClient, make_user: Callable[..., int]) -> None:
    user_id = make_user("auth-deactivated@example.com")
    token = _login(db_client, "auth-deactivated@example.com").json()["access_token"]
    assert _me(db_client, token).status_code == 200

    response = db_client.put(f"/users/{user_id}", json={"is_activated": False})
    assert response.status_code == 200, response.text

    # Le jeton est encore valable, mais le compte relu en base ne l'est plus.
    assert _me(db_client, token).status_code == 401


def test_missing_or_forged_token_401(db_client: TestClient, make_user: Callable[..., int]) -> None:
    user_id = make_user("auth-forged@example.com")
    # Bien formé et pas expiré : seule la signature (autre clé) le trahit.
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    forged = jwt.encode({"sub": str(user_id), "exp": exp}, "x" * 32 + "-une-autre-cle", algorithm=JWT_ALGORITHM)

    assert db_client.get("/auth/me").status_code == 401
    assert _me(db_client, forged).status_code == 401
    assert _me(db_client, "pas-un-jeton").status_code == 401
