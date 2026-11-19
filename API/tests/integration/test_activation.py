"""
test_activation.py — Le particulier finalise lui-même son compte (user story 01, @creation-compte).

Trou trouvé par Gabriel le 2026-11-19 : un compte créé par le formulaire
(P5) ne pouvait être activé que par un Admin (PUT /users/{id}, champ
is_activated réservé). Désormais :
- POST /users/{id}/activation-code (Admin, ou le Manager de la demande) rend
  un code valable 7 jours ;
- POST /auth/activate (code + mot de passe choisi) active le compte et rend
  un jeton de connexion.
"""

from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from src.app.models import Client, RealEstateManager, SearchRequest, User
from src.app.main import app
from src.app.utils.roles import CLIENT, HUNTER, MANAGER, get_principal
from src.app.utils.security import create_activation_token

from ..conftest import acting_as

FORM: dict[str, Any] = {
    "email": "activation.api@exemple.fr",
    "first_name": "Jade",
    "last_name": "Martin",
    "phone_number": "+33612345679",
    "country_iso": "FR",
    "address": "3 rue des Lilas",
    "postal_code": "75020",
    "town": "Paris",
    "budget_max": 300000,
    "estate_type": "Appartement",
}
NEW_PASSWORD = "mon-nouveau-mot-de-passe"
SEED_MANAGER_USER = 25  # manager du seed 02
SEED_CLIENT_EMAIL = "alice.martin@mail.fr"  # user 7, compte repris, inactif


def _pending_user(db_client: TestClient, db_session: Session) -> User:
    """Dépose le formulaire et rend le compte inactif qu'il a créé."""
    assert db_client.post("/search-requests/submit", json=FORM).status_code == 202
    return db_session.exec(select(User).where(func.lower(User.email) == FORM["email"])).one()


def _code(db_client: TestClient, user_id: Optional[int]):
    return db_client.post(f"/users/{user_id}/activation-code")


def _activate(db_client: TestClient, code: str, password: str = NEW_PASSWORD):
    return db_client.post("/auth/activate", json={"code": code, "password": password})


def _login(db_client: TestClient, password: str = NEW_PASSWORD) -> int:
    return db_client.post("/auth/login", json={"email": FORM["email"], "password": password}).status_code


def test_visitor_finalises_own_account(db_client: TestClient, db_session: Session) -> None:
    user = _pending_user(db_client, db_session)
    assert _login(db_client) == 401  # pas encore de mot de passe

    issued = _code(db_client, user.id)  # Admin, par défaut dans db_client
    assert issued.status_code == 200, issued.text
    assert issued.json()["expires_in"] == 7 * 24 * 3600

    activated = _activate(db_client, issued.json()["code"])

    assert activated.status_code == 200, activated.text
    assert activated.json()["token_type"] == "bearer"
    assert _login(db_client) == 200
    db_session.refresh(user)
    assert user.is_activated is True


def test_code_works_only_once(db_client: TestClient, db_session: Session) -> None:
    user = _pending_user(db_client, db_session)
    code = _code(db_client, user.id).json()["code"]
    assert _activate(db_client, code).status_code == 200

    again = _activate(db_client, code, "un-autre-mot-de-passe")

    assert again.status_code == 400
    assert _login(db_client) == 200  # le premier mot de passe tient


def test_bad_code_refused(db_client: TestClient) -> None:
    assert _activate(db_client, "pas-un-code").status_code == 400


def test_short_password_refused(db_client: TestClient, db_session: Session) -> None:
    user = _pending_user(db_client, db_session)
    code = _code(db_client, user.id).json()["code"]

    assert _activate(db_client, code, "court").status_code == 422


def test_migrated_account_sets_its_own_password(db_client: TestClient, db_session: Session) -> None:
    # Les 25 comptes repris (02_migration.sql) : inactifs, mot de passe
    # MIGRATED_PLACEHOLDER. Choix de Sébastien du 2026-11-19 (« tout ») :
    # ils passent par le même code que les comptes du formulaire.
    seeded = db_session.exec(select(User).where(User.email == SEED_CLIENT_EMAIL)).one()
    seeded.is_activated = False  # db_client active le seed ; son vrai état est inactif
    db_session.add(seeded)
    db_session.commit()
    login = {"email": SEED_CLIENT_EMAIL, "password": NEW_PASSWORD}
    assert db_client.post("/auth/login", json=login).status_code == 401

    issued = _code(db_client, seeded.id)
    assert issued.status_code == 200, issued.text
    assert _activate(db_client, issued.json()["code"]).status_code == 200

    assert db_client.post("/auth/login", json=login).status_code == 200


def test_erased_account_cannot_be_woken_up(db_client: TestClient, db_session: Session) -> None:
    user = _pending_user(db_client, db_session)
    assert user.id is not None
    code = create_activation_token(user.id)  # code délivré avant l'effacement
    assert db_client.post(f"/users/{user.id}/anonymize").status_code == 200

    assert _activate(db_client, code).status_code == 400


def test_manager_gets_code_only_for_own_request(db_client: TestClient, db_session: Session) -> None:
    user = _pending_user(db_client, db_session)

    with acting_as(MANAGER, SEED_MANAGER_USER):
        assert _code(db_client, user.id).status_code == 404  # la demande n'est pas à lui

    manager = db_session.exec(select(RealEstateManager).where(RealEstateManager.id_user == SEED_MANAGER_USER)).one()
    client = db_session.exec(select(Client).where(Client.id_user == user.id)).one()
    request = db_session.exec(select(SearchRequest).where(SearchRequest.id_client == client.id)).one()
    request.id_realestatemanager = manager.id
    db_session.add(request)
    db_session.commit()

    with acting_as(MANAGER, SEED_MANAGER_USER):
        assert _code(db_client, user.id).status_code == 200


@pytest.mark.parametrize("role", (CLIENT, HUNTER))
def test_client_and_hunter_cannot_get_a_code(db_client: TestClient, db_session: Session, role: str) -> None:
    user = _pending_user(db_client, db_session)

    with acting_as(role):
        assert _code(db_client, user.id).status_code == 403


def test_activation_needs_no_token(db_client: TestClient, db_session: Session) -> None:
    user = _pending_user(db_client, db_session)
    code = _code(db_client, user.id).json()["code"]
    previous = app.dependency_overrides.pop(get_principal)  # plus de compte Admin simulé
    try:
        assert _activate(db_client, code).status_code == 200
    finally:
        app.dependency_overrides[get_principal] = previous
