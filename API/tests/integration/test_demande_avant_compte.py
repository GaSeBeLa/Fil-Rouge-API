"""
Demande déposée avant le compte (fiche API9, P5) : POST /search-requests/submit.

Le formulaire crée, en une transaction, un user inactif au mot de passe
factice, sa fiche client et la search_request. Un email déjà connu, aux
majuscules près (P2), retrouve son compte. Une erreur au milieu : rien
n'est écrit — c'est ce que comptent les tests « 0 ligne ».

La réponse est la même pour tous (202, RECEIPT, relecture de la série
API6 → API10) : les tests retrouvent le compte par son email, en base.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, SQLModel, select

from src.app.main import app
from src.app.models import Client, SearchRequest, User
from src.app.services.signup_service import RECEIPT
from src.app.utils.roles import get_principal
from src.app.utils.security import PENDING_SIGNUP_PASSWORD

SUBMIT = "/search-requests/submit"
ACCEPTED = (202, {"detail": RECEIPT})

FORM = {
    "email": "lea.dupont.api9@exemple.fr",
    "first_name": "Léa",
    "last_name": "Dupont",
    "phone_number": "+33612345678",
    "country_iso": "FR",
    "address": "12 rue de la Roquette",
    "postal_code": "75011",
    "town": "Paris",
}

SEED_CLIENT_EMAIL = "alice.martin@mail.fr"  # user 7, Client, fiche à Montpellier (02_migration.sql)
SEED_HUNTER_EMAIL = "m.roussel@chassimmo.fr"  # user 1, Hunter, sans fiche client


def _count(session: Session, model: type[SQLModel]) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def _counts(session: Session) -> tuple[int, int, int]:
    """Lignes de user, client et search_request."""
    return (_count(session, User), _count(session, Client), _count(session, SearchRequest))


def _answer(db_client: TestClient, form: dict[str, str]) -> tuple[int, object]:
    response = db_client.post(SUBMIT, json=form)
    return response.status_code, response.json()


def _user_of(session: Session, email: str) -> User:
    return session.exec(select(User).where(func.lower(User.email) == email.lower())).one()


def _requests_of(session: Session, user_id: int | None) -> list[SearchRequest]:
    return list(session.exec(select(SearchRequest).where(SearchRequest.id_client == user_id)).all())


def _login(db_client: TestClient, email: str, password: str) -> int:
    return db_client.post("/auth/login", json={"email": email, "password": password}).status_code


def test_new_form_creates_inactive_account_client_and_request(
    db_client: TestClient, db_session: Session
) -> None:
    users, clients, requests = _counts(db_session)

    assert _answer(db_client, FORM) == ACCEPTED

    assert _counts(db_session) == (users + 1, clients + 1, requests + 1)
    user = _user_of(db_session, FORM["email"])
    [request] = _requests_of(db_session, user.id)
    assert request.id_author == user.id
    assert request.status == "confirmed"
    assert request.id_hunter is None
    assert user.is_activated is False
    assert user.password == PENDING_SIGNUP_PASSWORD


def test_pending_account_cannot_log_in(db_client: TestClient) -> None:
    assert _answer(db_client, FORM) == ACCEPTED

    assert _login(db_client, FORM["email"], "un-mot-de-passe-au-hasard") == 401
    # Le mot de passe factice n'est pas une empreinte : il n'ouvre rien non plus.
    assert _login(db_client, FORM["email"], PENDING_SIGNUP_PASSWORD) == 401


def test_same_email_in_capitals_reuses_the_account(db_client: TestClient, db_session: Session) -> None:
    users, clients, requests = _counts(db_session)
    assert _answer(db_client, FORM) == ACCEPTED

    assert _answer(db_client, {**FORM, "email": FORM["email"].upper()}) == ACCEPTED

    assert len(_requests_of(db_session, _user_of(db_session, FORM["email"]).id)) == 2
    assert _counts(db_session) == (users + 1, clients + 1, requests + 2)


def test_known_client_keeps_their_record(db_client: TestClient, db_session: Session) -> None:
    users, clients, requests = _counts(db_session)
    alice_requests = len(_requests_of(db_session, 7))

    assert _answer(db_client, {**FORM, "email": SEED_CLIENT_EMAIL.upper(), "town": "Brest"}) == ACCEPTED

    assert len(_requests_of(db_session, 7)) == alice_requests + 1
    assert _counts(db_session) == (users, clients, requests + 1)
    client = db_session.exec(select(Client).where(Client.id_user == 7)).one()
    assert client.town == "Montpellier"  # un formulaire anonyme ne réécrit pas une fiche


def test_email_of_a_non_client_account_is_ignored_and_logged(
    db_client: TestClient, db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    before = _counts(db_session)

    with caplog.at_level(logging.WARNING, logger="src.app.services.signup_service"):
        assert _answer(db_client, {**FORM, "email": SEED_HUNTER_EMAIL}) == ACCEPTED

    assert _counts(db_session) == before
    assert "le compte 1 n'est pas un compte client" in caplog.text
    assert SEED_HUNTER_EMAIL not in caplog.text  # l'id, pas l'email (RGPD)


def test_same_answer_whoever_the_email(db_client: TestClient) -> None:
    # Relecture de la série : 409 pour un chasseur, id_client pour un client
    # connu — la réponse disait si l'email existait.
    emails = (FORM["email"], SEED_CLIENT_EMAIL, SEED_HUNTER_EMAIL)
    answers = [_answer(db_client, {**FORM, "email": email}) for email in emails]
    assert answers == [ACCEPTED] * len(emails)


def test_missing_address_422_nothing_written(db_client: TestClient, db_session: Session) -> None:
    before = _counts(db_session)
    form = {key: value for key, value in FORM.items() if key != "address"}

    response = db_client.post(SUBMIT, json=form)

    assert response.status_code == 422, response.text
    assert _counts(db_session) == before


def test_database_refusal_midway_writes_nothing(db_client: TestClient, db_session: Session) -> None:
    # Le user passe, puis la base refuse la fiche client (code postal FR sur
    # 4 chiffres, ck_client_postal_code_format) : le user doit partir avec elle.
    before = _counts(db_session)

    response = db_client.post(SUBMIT, json={**FORM, "postal_code": "3100"})

    assert response.status_code == 409, response.text
    assert _counts(db_session) == before


def test_activation_by_put_users_opens_login(db_client: TestClient, db_session: Session) -> None:
    assert _answer(db_client, FORM) == ACCEPTED
    user_id = _user_of(db_session, FORM["email"]).id
    password = "mon-mot-de-passe-choisi"

    response = db_client.put(f"/users/{user_id}", json={"password": password, "is_activated": True})

    assert response.status_code == 200, response.text
    assert _login(db_client, FORM["email"], password) == 200


def test_submit_needs_the_api_key_but_no_token(db_client: TestClient) -> None:
    app.dependency_overrides.pop(get_principal, None)  # plus de compte connecté

    assert _answer(db_client, FORM) == ACCEPTED
    assert TestClient(app).post(SUBMIT, json=FORM).status_code == 401  # sans X-API-Key
