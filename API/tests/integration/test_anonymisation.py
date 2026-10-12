"""
Effacer un compte (fiche API10, ADR-049) : POST /users/{id}/anonymize, et
plus aucune route DELETE.

- Tout de suite : compte désactivé ; email, mot de passe, téléphone,
  adresse, naissance et situation, textes écrits rendus anonymes.
- Prénom et nom : seulement quand le plus long délai est fini, 10 ans après
  la fin du dernier mandat de la chaîne ou après le paiement (Décision 5).

Seed 02 : chasseur 1 (Marina Roussel), mandats jusqu'au 2026-09-25 et
critères qu'il a écrits ; client 21, mandat 15 ('active', fin 2026-09-25).
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.app.models import Client, Criteria, EstateProposed, Hunter, User
from src.app.services.anonymization_service import (
    ANONYMIZED_PASSWORD,
    AnonymizationService,
    names_kept_until,
    plus_years,
)
from src.app.utils.roles import CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as
from .conftest import USER_PASSWORD
from .test_constraints_db import (
    ACTIVE_MANDATE,
    ACTIVE_REQUEST,
    HUNTER_ID,
    MANDATE,
    advance,
    payment_payload,
    selected_estate,
)

ACTIVE_MANDATE_CLIENT = 21
ACTIVE_MANDATE_END = date(2026, 9, 25)

CLIENT_RECORD = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "phone_number": "+33600000000",
    "gender": "female",
    "birth_date": "1990-05-04",
    "is_married": True,
    "nb_children": 2,
    "country_iso": "FR",
    "address": "1 rue de la Paix",
    "address_complement": "Bâtiment B",
    "postal_code": "31000",
    "town": "Toulouse",
}


def _anonymize(db_client: TestClient, user_id: int):
    return db_client.post(f"/users/{user_id}/anonymize")


def _client_of(db_session: Session, user_id: int) -> Client:
    return db_session.exec(select(Client).where(Client.id_user == user_id)).one()


def _login(db_client: TestClient, email: str, password: str) -> int:
    return db_client.post("/auth/login", json={"email": email, "password": password}).status_code


def _paid_on(db_client: TestClient, paid: date) -> None:
    """Un paiement versé au chasseur 1 ce jour-là (ADR-038, pas à pas)."""
    payload = payment_payload(db_client, announced_at=f"{paid - timedelta(days=30)}T09:00:00Z")
    scheduled = {"status": "scheduled", "scheduled_for": str(paid)}
    advance(db_client, payload, scheduled, {**scheduled, "status": "paid", "paid_at": f"{paid}T00:00:00Z"})


# --- Tout de suite : ce que rien n'oblige à garder (Décisions 4, 6, 7) ----------


def test_client_without_mandate_is_fully_anonymized(db_client: TestClient, db_session: Session) -> None:
    email = "ada.api10@exemple.fr"
    account = {"email": email, "password": USER_PASSWORD, "id_role": 1, "is_activated": True}
    user_id = db_client.post("/users", json=account).json()["id"]
    created = db_client.post("/clients", json={**CLIENT_RECORD, "id_user": user_id})
    assert created.status_code == 201, created.text
    assert _login(db_client, email, USER_PASSWORD) == 200  # actif avant

    response = _anonymize(db_client, user_id)

    assert response.status_code == 200, response.text
    assert response.json() == {"id_user": user_id, "names_anonymized": True, "names_kept_until": None}
    user = db_session.get(User, user_id)
    assert user is not None
    assert (user.is_activated, user.email, user.password) == (
        False,
        f"anonyme-{user_id}@exemple.invalid",
        ANONYMIZED_PASSWORD,
    )
    client = _client_of(db_session, user_id)
    assert (client.first_name, client.last_name) == ("Anonyme", "Anonyme")
    assert (client.phone_number, client.address, client.postal_code, client.town, client.country_iso) == (
        "+33000000000",
        "anonyme",
        "00000",
        "anonyme",
        "FR",
    )
    assert [client.address_complement, client.birth_date, client.gender] == [None, None, None]
    assert [client.is_married, client.is_civil_solidarity_pact, client.nb_children] == [None, None, None]
    assert _login(db_client, email, USER_PASSWORD) == 401
    assert _login(db_client, user.email, ANONYMIZED_PASSWORD) == 401


def test_client_comment_is_cleared_and_name_waits_for_the_mandate(
    db_client: TestClient, db_session: Session
) -> None:
    offer = db_client.post(
        "/estate-proposed",
        json={
            "proposition_status": "proposed",
            "id_hunter": HUNTER_ID,
            "id_estate": selected_estate(db_client),
            "id_mandate": ACTIVE_MANDATE,
            "comment_client": "Trop sombre, et le voisin du dessus est bruyant.",
        },
    )
    assert offer.status_code == 201, offer.text
    client = _client_of(db_session, ACTIVE_MANDATE_CLIENT)
    name = (client.first_name, client.last_name)

    response = _anonymize(db_client, ACTIVE_MANDATE_CLIENT)

    assert response.status_code == 200, response.text
    assert response.json()["names_anonymized"] is False
    assert response.json()["names_kept_until"] == str(plus_years(ACTIVE_MANDATE_END, 10))
    assert (client.first_name, client.last_name) == name
    assert client.address == "anonyme"
    stored = db_session.get(EstateProposed, offer.json()["id"])
    assert stored is not None and stored.comment_client is None


# --- Le nom attend la fin du plus long délai (Décision 5) ------------------------


def test_hunter_paid_two_years_ago_keeps_name_rest_anonymized(
    db_client: TestClient, db_session: Session
) -> None:
    _paid_on(db_client, date.today() - timedelta(days=730))

    response = _anonymize(db_client, HUNTER_ID)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["names_anonymized"] is False
    assert date.fromisoformat(body["names_kept_until"]) > date.today()
    hunter = db_session.exec(select(Hunter).where(Hunter.id_user == HUNTER_ID)).one()
    assert (hunter.first_name, hunter.last_name) == ("Marina", "Roussel")
    assert hunter.phone_number == "+33000000000"
    user = db_session.get(User, HUNTER_ID)
    assert user is not None and user.is_activated is False
    assert user.email == f"anonyme-{HUNTER_ID}@exemple.invalid"
    written = db_session.exec(select(Criteria).where(Criteria.id_author == HUNTER_ID)).all()
    assert written and all(version.change_reason is None for version in written)


def test_payment_made_today_holds_the_name_ten_years(db_client: TestClient) -> None:
    # Versé après la fin des mandats du chasseur 1 (2026-09-25) : c'est le
    # paiement qui fixe la date, pas un mandat.
    _paid_on(db_client, date.today())

    body = _anonymize(db_client, HUNTER_ID).json()

    assert body["names_kept_until"] == str(plus_years(date.today(), 10))


def test_payment_not_yet_paid_holds_the_name_from_today(db_client: TestClient) -> None:
    # Annoncé, pas encore versé : le délai n'a pas commencé.
    advance(db_client, payment_payload(db_client))

    body = _anonymize(db_client, HUNTER_ID).json()

    assert body["names_kept_until"] == str(plus_years(date.today(), 10))


def test_renewal_by_another_hunter_extends_the_delay(db_client: TestClient) -> None:
    # Mandat 15 (chasseur 1) renouvelé par le chasseur 2 : la base ne compare
    # pas le chasseur (Q-MAN-08). La fin de la chaîne compte pour le chasseur 1.
    renewal = {
        **MANDATE,
        "reference": "TEST-M-RENOUV",
        "signature_date": "2026-09-26",
        "ends_at": "2027-03-26",
        "id_hunter": 2,
        "id_client": ACTIVE_MANDATE_CLIENT,
        "id_search_request": ACTIVE_REQUEST,
        "id_mandate_parent": ACTIVE_MANDATE,
    }
    assert (created := db_client.post("/mandates", json=renewal)).status_code == 201, created.text

    body = _anonymize(db_client, HUNTER_ID).json()

    assert body["names_kept_until"] == str(plus_years(date(2027, 3, 26), 10))


def test_second_call_after_the_delay_finishes_the_work(db_client: TestClient, db_session: Session) -> None:
    first = _anonymize(db_client, HUNTER_ID).json()
    later = date.fromisoformat(first["names_kept_until"])

    report = AnonymizationService().anonymize(db_session, HUNTER_ID, today=later)

    assert report.names_anonymized is True
    hunter = db_session.exec(select(Hunter).where(Hunter.id_user == HUNTER_ID)).one()
    assert (hunter.first_name, hunter.last_name) == ("Anonyme", "Anonyme")


def test_paid_date_alone_holds_the_name_ten_years() -> None:
    paid = date.today() - timedelta(days=730)
    assert names_kept_until([paid]) == plus_years(paid, 10)
    assert names_kept_until([date(2014, 1, 31)]) == date(2024, 1, 31)  # délai fini
    assert names_kept_until([]) is None  # aucun délai : tout de suite


def test_february_29_becomes_february_28() -> None:
    assert plus_years(date(2024, 2, 29), 10) == date(2034, 2, 28)


# --- Droits et DELETE (Décisions 3 et 10) ----------------------------------------


def test_delete_client_is_gone_405(db_client: TestClient) -> None:
    assert db_client.delete("/clients/1").status_code == 405


@pytest.mark.parametrize("role", [CLIENT, HUNTER, MANAGER, READER])
def test_only_admin_anonymizes(db_client: TestClient, db_session: Session, role: str) -> None:
    with acting_as(role):
        response = _anonymize(db_client, 7)

    assert response.status_code == 403
    user = db_session.get(User, 7)
    assert user is not None and user.email == "alice.martin@mail.fr"


def test_unknown_user_404(db_client: TestClient) -> None:
    assert _anonymize(db_client, 999999).status_code == 404
