"""
test_roles_db.py — Le rôle relu en base, de bout en bout (ADR-028, fiche API2).

db_client se présente en Admin ; ici on retire ce remplacement pour passer
par la vraie chaîne : jeton -> compte -> rôle lu dans la table role.
"""

from fastapi.testclient import TestClient

from src.app.main import app
from src.app.utils.roles import get_principal

from .conftest import USER_PASSWORD

READER_ROLE_ID = 5  # posé par 02 (LOT12)


def test_reader_token_reads_but_cannot_write(db_client: TestClient):
    created = db_client.post(
        "/users",
        json={"email": "role-reader@example.com", "password": USER_PASSWORD, "id_role": READER_ROLE_ID, "is_activated": True},
    )
    assert created.status_code == 201, created.text
    app.dependency_overrides.pop(get_principal, None)  # plus d'Admin d'office

    login = db_client.post("/auth/login", json={"email": "role-reader@example.com", "password": USER_PASSWORD})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert db_client.get("/roles", headers=headers).status_code == 200
    assert db_client.post("/roles", json={"wording": "Admin"}, headers=headers).status_code == 403
    assert db_client.get("/roles").status_code == 401
