"""
test_users_db.py — /users contre la base de test.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Ce que les tests unitaires ne pouvaient pas prouver :

- le mot de passe est STOCKÉ haché dans PostgreSQL (lu en base, pas dans
  la réponse) ;
- UNIQUE(email), la clé étrangère id_role et ON DELETE RESTRICT donnent
  bien 409, avec le message attendu ;
- le PUT partiel ne touche pas les champs omis, une fois écrit en base.
============================================================================
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.app.models import User

from .conftest import USER_PASSWORD

EMAIL = "compte@exemple.fr"
WRITE_CONFLICT = "Contrainte violée (valeur en double ou référence inexistante)."
DELETE_CONFLICT = "Suppression impossible : cette ligne est encore référencée ailleurs."


def test_post_returns_201_without_password(db_client: TestClient):
    response = db_client.post("/users", json={"email": EMAIL, "password": USER_PASSWORD, "id_role": 1})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    assert "password" not in body


def test_post_without_is_activated_stores_false(db_client: TestClient, db_session: Session):
    # NOT NULL DEFAULT FALSE (88ab154, migration 13) : omis, il vaut FALSE en base.
    response = db_client.post("/users", json={"email": EMAIL, "password": USER_PASSWORD, "id_role": 1})
    assert response.status_code == 201, response.text
    stored = db_session.get(User, response.json()["id"])
    assert stored is not None and stored.is_activated is False


def test_password_is_stored_hashed(create_user: Callable[[str], int], db_session: Session):
    stored = db_session.get(User, create_user(EMAIL))
    assert stored is not None
    assert stored.password != USER_PASSWORD
    assert stored.password.startswith("$argon2id$")


def test_duplicate_email_returns_409(db_client: TestClient, create_user: Callable[[str], int]):
    create_user(EMAIL)
    response = db_client.post("/users", json={"email": EMAIL, "password": USER_PASSWORD, "id_role": 1})
    assert response.status_code == 409
    assert response.json()["detail"] == WRITE_CONFLICT


def test_unknown_role_returns_409(db_client: TestClient):
    response = db_client.post("/users", json={"email": EMAIL, "password": USER_PASSWORD, "id_role": 9999})
    assert response.status_code == 409


def test_put_partial_keeps_omitted_fields(
    db_client: TestClient, create_user: Callable[[str], int], db_session: Session
):
    user_id = create_user(EMAIL)
    stored = db_session.get(User, user_id)
    assert stored is not None
    hash_before = stored.password

    response = db_client.put(f"/users/{user_id}", json={"is_activated": True})

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL
    assert response.json()["is_activated"] is True
    db_session.refresh(stored)
    assert stored.password == hash_before


def test_get_unknown_id_returns_404(db_client: TestClient):
    response = db_client.get("/users/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Utilisateur introuvable"


def test_delete_free_user_then_404(db_client: TestClient, create_user: Callable[[str], int]):
    user_id = create_user(EMAIL)
    assert db_client.delete(f"/users/{user_id}").status_code == 200
    assert db_client.get(f"/users/{user_id}").status_code == 404


def test_delete_user_referenced_by_client_returns_409(db_client: TestClient, create_user: Callable[[str], int]):
    user_id = create_user(EMAIL)
    client = db_client.post(
        "/clients",
        json={"id_user": user_id, "first_name": "Ada", "last_name": "Lovelace", "phone_number": "+33600000000"},
    )
    assert client.status_code == 201, client.text

    response = db_client.delete(f"/users/{user_id}")
    assert response.status_code == 409
    assert response.json()["detail"] == DELETE_CONFLICT
