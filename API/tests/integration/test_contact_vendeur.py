"""
test_contact_vendeur.py — Le contact du vendeur d'un bien (ADR-054).

- Lecture et écriture réservées à Admin, Hunter et Manager : Client et
  Reader reçoivent 403, même en lecture.
- `id_author` est le compte du jeton ; un PUT ne le change pas.
- La base refuse : un second contact pour le même bien (UNIQUE), un
  téléphone hors du format d'ADR-007, une ligne sans aucun renseignement.
- `is_private` est obligatoire, et gardé avec un nom d'agence (questions 1, 2).
- Le rôle PostgreSQL `fil_rouge_reader` ne lit pas la table (question 5).
- Effacement (question 4) : anonyme 3 ans après la dernière activité du
  bien, par POST /estate-contacts/anonymize-expired, Admin seul.

Comptes du seed 02 : chasseurs 1 et 2, manager 25.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session

from src.app.models import EstateContact
from src.app.repositories.estate_contact_repository import EstateContactRepository
from src.app.services.anonymization_service import ANONYMOUS_NAME, plus_years
from src.app.services.estate_contact_service import EstateContactService
from src.app.utils.roles import ADMIN, CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as
from .test_constraints_db import ESTATE, HUNTER_ID, post_as_hunter, selected_estate

OTHER_HUNTER_ID = 2
MANAGER_ID = 25

# Un contact créé aujourd'hui : 3 ans plus tard, à 2 jours près (minuit UTC).
IN_THREE_YEARS = plus_years(date.today(), 3)
DAYS_2 = timedelta(days=2)

CONTACT: dict[str, Any] = {
    "is_private": False,
    "agency_name": "Agence du Centre",
    "contact_name": "Mme Martin",
    "phone_number": "+33612345678",
    "email": "contact@agence.test",
}


def new_estate(db_client: TestClient) -> int:
    created = post_as_hunter(db_client, "/estates", ESTATE)
    assert created.status_code == 201, created.text
    return created.json()["id"]


def post_contact(db_client: TestClient, payload: dict[str, Any]):
    with acting_as(HUNTER, HUNTER_ID):
        return db_client.post("/estate-contacts", json=payload)


# --- Droits --------------------------------------------------------------------


@pytest.mark.parametrize(("role", "user_id"), [(HUNTER, HUNTER_ID), (MANAGER, MANAGER_ID), (ADMIN, MANAGER_ID)])
def test_staff_writes_and_reads_a_contact(db_client: TestClient, role: str, user_id: int):
    payload = {**CONTACT, "id_estate": new_estate(db_client)}
    with acting_as(role, user_id):
        created = db_client.post("/estate-contacts", json=payload)
        assert created.status_code == 201, created.text
        read = db_client.get(f"/estate-contacts/{created.json()['id']}")
        listed = db_client.get("/estate-contacts")
    assert read.status_code == 200
    assert read.json()["phone_number"] == "+33612345678"
    assert listed.status_code == 200


@pytest.mark.parametrize("role", [CLIENT, READER])
def test_client_and_reader_cannot_read_contacts(db_client: TestClient, role: str):
    created = post_contact(db_client, {**CONTACT, "id_estate": new_estate(db_client)})
    assert created.status_code == 201, created.text
    with acting_as(role):
        listed = db_client.get("/estate-contacts")
        read = db_client.get(f"/estate-contacts/{created.json()['id']}")
    assert listed.status_code == 403
    assert read.status_code == 403


@pytest.mark.parametrize("role", [CLIENT, READER])
def test_client_and_reader_cannot_write_contacts(db_client: TestClient, role: str):
    with acting_as(role, HUNTER_ID):
        response = db_client.post("/estate-contacts", json={**CONTACT, "id_estate": new_estate(db_client)})
    assert response.status_code == 403
    assert db_client.get("/estate-contacts").json() == []  # rien n'a été écrit


# --- Auteur --------------------------------------------------------------------


def test_author_is_the_token_account_and_put_keeps_it(db_client: TestClient):
    payload = {**CONTACT, "id_estate": new_estate(db_client), "id_author": OTHER_HUNTER_ID}
    created = post_contact(db_client, payload)
    assert created.status_code == 201, created.text
    assert created.json()["id_author"] == HUNTER_ID

    with acting_as(MANAGER, MANAGER_ID):
        changed = db_client.put(
            f"/estate-contacts/{created.json()['id']}",
            json={**payload, "contact_name": "M. Durand", "id_author": MANAGER_ID},
        )
    assert changed.status_code == 200, changed.text
    assert changed.json()["contact_name"] == "M. Durand"
    assert changed.json()["id_author"] == HUNTER_ID


# --- Contraintes de la base ----------------------------------------------------


def test_one_contact_per_estate(db_client: TestClient):
    estate_id = new_estate(db_client)
    assert post_contact(db_client, {**CONTACT, "id_estate": estate_id}).status_code == 201
    second = post_contact(db_client, {**CONTACT, "id_estate": estate_id})
    assert second.status_code == 409


@pytest.mark.parametrize("phone", ["0612345678", "+0612345678", "06 12 34 56 78"])
def test_phone_must_follow_adr_007(db_client: TestClient, phone: str):
    response = post_contact(db_client, {**CONTACT, "phone_number": phone, "id_estate": new_estate(db_client)})
    assert response.status_code == 409


def test_contact_needs_at_least_one_detail(db_client: TestClient):
    response = post_contact(db_client, {"is_private": True, "id_estate": new_estate(db_client)})
    assert response.status_code == 409


def test_private_seller_keeps_its_agency(db_client: TestClient):
    # ADR-054, question 1 : « particulier » et une agence, on garde les deux.
    payload = {**CONTACT, "is_private": True, "id_estate": new_estate(db_client)}
    response = post_contact(db_client, payload)
    assert response.status_code == 201, response.text
    assert response.json()["is_private"] is True
    assert response.json()["agency_name"] == "Agence du Centre"


def test_is_private_is_required(db_client: TestClient):
    # ADR-054, question 2 : vrai ou faux, jamais vide.
    response = post_contact(db_client, {"contact_name": "M. Bernard", "id_estate": new_estate(db_client)})
    assert response.status_code == 422


# --- Rôle PostgreSQL en lecture seule (ADR-054, question 5) --------------------


def test_reader_role_cannot_read_contacts(db_session: Session):
    # SET LOCAL ROLE : les droits de fil_rouge_reader jusqu'au rollback de la fixture.
    connection = db_session.connection()
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        connection.execute(text("SELECT phone_number FROM estate_contact"))


# --- Effacement à 3 ans (ADR-054, question 4) -----------------------------------


def contact_on_new_estate(db_client: TestClient) -> int:
    created = post_contact(db_client, {**CONTACT, "id_estate": new_estate(db_client)})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def stored(db_session: Session, contact_id: int) -> EstateContact:
    contact = db_session.get(EstateContact, contact_id)
    assert contact is not None
    return contact


def test_contact_is_kept_before_three_years(db_client: TestClient, db_session: Session):
    contact_id = contact_on_new_estate(db_client)
    report = EstateContactService(EstateContactRepository()).anonymize_expired(db_session, IN_THREE_YEARS - DAYS_2)
    assert report.anonymized == 0
    assert stored(db_session, contact_id).phone_number == "+33612345678"


def test_contact_is_anonymized_after_three_years(db_client: TestClient, db_session: Session):
    contact_id = contact_on_new_estate(db_client)
    service = EstateContactService(EstateContactRepository())
    report = service.anonymize_expired(db_session, IN_THREE_YEARS + DAYS_2)
    assert report.anonymized == 1
    contact = stored(db_session, contact_id)
    assert (contact.contact_name, contact.agency_name, contact.phone_number, contact.email) == (
        ANONYMOUS_NAME, None, None, None,
    )
    assert contact.is_private is False and contact.id_author == HUNTER_ID  # gardés
    # Rejouée : rien de nouveau.
    assert service.anonymize_expired(db_session, IN_THREE_YEARS + DAYS_2).anonymized == 0


def test_later_activity_delays_anonymization(db_client: TestClient, db_session: Session):
    # Une sélection du bien un an plus tard repousse les 3 ans d'autant.
    estate_id = selected_estate(db_client)
    contact = post_contact(db_client, {**CONTACT, "id_estate": estate_id})
    assert contact.status_code == 201, contact.text
    db_session.connection().execute(
        text("UPDATE estate_searchrequest SET created_at = created_at + interval '1 year' WHERE id_estate = :e"),
        {"e": estate_id},
    )
    service = EstateContactService(EstateContactRepository())
    assert service.anonymize_expired(db_session, IN_THREE_YEARS + DAYS_2).anonymized == 0
    assert service.anonymize_expired(db_session, plus_years(IN_THREE_YEARS, 1) + DAYS_2).anonymized == 1


@pytest.mark.parametrize("role", [HUNTER, MANAGER, CLIENT, READER])
def test_only_admin_runs_the_anonymization(db_client: TestClient, role: str):
    with acting_as(role, HUNTER_ID):
        response = db_client.post("/estate-contacts/anonymize-expired")
    assert response.status_code == 403


def test_admin_runs_the_anonymization(db_client: TestClient):
    contact_id = contact_on_new_estate(db_client)
    response = db_client.post("/estate-contacts/anonymize-expired")
    assert response.status_code == 200, response.text
    assert response.json()["cutoff"] == plus_years(date.today(), -3).isoformat()
    # Contact du jour : gardé.
    assert db_client.get(f"/estate-contacts/{contact_id}").json()["contact_name"] == "Mme Martin"
