"""
test_constraints_db.py — Contraintes du schéma init-v3, vues par l'API.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Chaque test vise UNE contrainte de docker/init-v3/01 (ou sa correction
dans 02) et vérifie le code HTTP qui en sort :

- estate : prix en euros entiers (INTEGER, Q-REM-01 du 2026-10-05),
  CHECK price >= 0, liste fermée de estate_type, NOT NULL, UNIQUE ;
  auteur connu de "user" (Q-ACC-09) ;
- client : adresse, code postal, ville et pays obligatoires (ADR-053, P3),
  adresse neutre d'un client rendu anonyme acceptée (ADR-049), et
  ck_client_marital_status_exclusive (marié ET pacsé refusé) ;
- client, hunter, real_estate_manager : téléphone au format international
  d'ADR-007 (Q-PRO-08), numéro factice +33000000000 accepté (Q-MIG-07) ;
- estate, client, criteria : code postal par pays, contrôlé sur estate
  depuis LOT8 (Q-SCH-11) ; Eircode sans espace (Q-SCH-12) ;
- mandate : statut de fin 'lost' (Q-REM-02, Q-REM-14) ;
  chk_status_signature, qui permet 'canceled' sans signature (Q-MAN-07) ;
  chk_mandate_six_months (Q-MAN-01) ; trigger d'exclusivité (Q-MAN-02) ;
- estate_proposed : offre 'signed' (Q-SCH-04) ; priorité du client de 1 à
  5 (D6, Q-SCH-05) ;
- payment : final_rate entre 0,20 et 0,60 (Q-REM-19), exigé hors refus et
  interdit sur un refus (chk_refused, Q-REM-10) ; score figé (Q-REM-03) ;
  une date par étape, chk_announced et chk_scheduled (Q-REM-17) ; termes
  du calcul en JSONB (Q-REM-04) ; ancienneté et performance bornées au
  domaine d'un taux (Q-REM-05) ;
- commission_scale : taux de tranche > 0 (Q-SCH-15) ;
- parameters_fees : une grille par date de départ (Q-SCH-17) ;
- sale : clé vers sa grille d'honoraires (Q-REM-13) ;
- hunter_performance : journal des notes, une note par paiement ou mandat
  (Q-SCH-06) ;
- hunter_rate_parameters : une version par date de départ (Q-REM-05) ;
- fil_rouge_reader : le rôle PostgreSQL en lecture seule lit, n'écrit pas
  (Q14, LOT12) — vu en SQL, pas par l'API : c'est un droit de la base.

Depuis le 2026-10-05, le routeur commun revalide l'entrée (crud_router.py,
`_validated`) : un type faux ou un champ obligatoire manquant donne 422,
avant la base ; une contrainte que seul PostgreSQL connaît (CHECK, UNIQUE)
donne 409.
============================================================================
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session  # mère de sqlmodel.Session, la fixture db_session
from sqlmodel import Session as SQLModelSession

from src.app.models import HunterPerformance
from src.app.repositories.hunter_performance_repository import HunterPerformanceRepository
from src.app.services.hunter_performance_service import HunterPerformanceService
from src.app.utils.exceptions import ConflictError

ESTATE: dict[str, Any] = {
    "reference": "TEST-0001",
    "estate_type": "Maison",
    "surface": "120.50",
    "town": "Toulouse",
    "price": 354712,
}


# Obligatoire sur client (ADR-053, P3).
CLIENT_ADDRESS: dict[str, Any] = {
    "address": "1 rue de la Paix",
    "postal_code": "31000",
    "town": "Toulouse",
    "country_iso": "FR",
}


def person_fields(user_id: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id_user": user_id,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone_number": "+33600000000",  # format d'ADR-007 (Q-PRO-08)
    }
    payload.update(overrides)
    return payload


def client_payload(user_id: int, **overrides: Any) -> dict[str, Any]:
    return person_fields(user_id, **{**CLIENT_ADDRESS, **overrides})


# --- estate ------------------------------------------------------------------


def test_estate_price_is_whole_euros(db_client: TestClient):
    created = db_client.post("/estates", json=ESTATE)
    assert created.status_code == 201, created.text

    read = db_client.get(f"/estates/{created.json()['id']}")
    assert read.json()["price"] == 354712


# Sans la validation du routeur (avant le 2026-10-05), 199999.5 était arrondi
# en silence à 200000 par PostgreSQL — tranche du dessus — et "199999.50"
# faisait planter l'insertion. Un prix est en euros entiers (Q-REM-01).
@pytest.mark.parametrize("price", [199999.5, "199999.50"])
def test_estate_price_with_cents_returns_422(db_client: TestClient, price: Any):
    response = db_client.post("/estates", json={**ESTATE, "price": price})
    assert response.status_code == 422
    assert db_client.get("/estates").json() == []  # rien n'a été écrit


def test_estate_missing_required_field_returns_422(db_client: TestClient):
    # surface : NOT NULL en base, obligatoire dans le modèle.
    response = db_client.post("/estates", json={**ESTATE, "surface": None})
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price", "-1"),  # CHECK (price >= 0)
        ("estate_type", "Péniche"),  # CHECK estate_type IN (...)
        ("surface", "0"),  # CHECK (surface > 0)
    ],
)
def test_estate_constraint_violation_returns_409(db_client: TestClient, field: str, value: Any):
    response = db_client.post("/estates", json={**ESTATE, field: value})
    assert response.status_code == 409


def test_estate_duplicate_reference_returns_409(db_client: TestClient):
    assert db_client.post("/estates", json=ESTATE).status_code == 201
    assert db_client.post("/estates", json=ESTATE).status_code == 409


def test_estate_unknown_author_returns_409(db_client: TestClient):
    # Auteur d'un bien saisi à la main : clé vers "user" (Q-ACC-09, Q-JEF-24).
    response = db_client.post("/estates", json={**ESTATE, "id_author": 999999})
    assert response.status_code == 409


def test_estate_known_author_is_accepted(db_client: TestClient):
    response = db_client.post("/estates", json={**ESTATE, "id_author": 1})  # chasseur posé par 02
    assert response.status_code == 201, response.text


# --- client ------------------------------------------------------------------


# Adresse obligatoire (ADR-053, P3) : un champ manquant donne 422, avant la
# base. Une adresse inconnue s'écrit 'non renseigné', comme pour les 18
# clients repris (Q-SCH-18).
@pytest.mark.parametrize("field", list(CLIENT_ADDRESS))
def test_client_without_address_field_returns_422(
    db_client: TestClient, create_user: Callable[[str], int], field: str
):
    payload = client_payload(create_user("sans-adresse@exemple.fr"))
    del payload[field]
    assert db_client.post("/clients", json=payload).status_code == 422


def test_client_without_address_is_refused_by_the_database(db_session: Session):
    # Le NOT NULL tient aussi sans l'API : un script SQL ne passe pas.
    with pytest.raises(IntegrityError, match="violates not-null constraint"):
        db_session.execute(
            text(
                "INSERT INTO client (id_user, first_name, last_name, phone_number) "
                "VALUES (1, 'Ada', 'Lovelace', '+33600000000')"
            )
        )


def test_client_anonymized_address_is_accepted(db_client: TestClient, create_user: Callable[[str], int]):
    # Adresse neutre d'un client rendu anonyme (ADR-049, ADR-053) : elle doit
    # passer tous les CHECK de la base.
    neutral = {"address": "anonyme", "postal_code": "00000", "town": "anonyme", "country_iso": "FR"}
    response = db_client.post("/clients", json=client_payload(create_user("anonyme@exemple.fr"), **neutral))
    assert response.status_code == 201, response.text


def test_client_married_and_pacs_returns_409(db_client: TestClient, create_user: Callable[[str], int]):
    payload = client_payload(create_user("pacs@exemple.fr"), is_married=True, is_civil_solidarity_pact=True)
    assert db_client.post("/clients", json=payload).status_code == 409


def test_client_second_profile_for_same_user_returns_409(
    db_client: TestClient, create_user: Callable[[str], int]
):
    user_id = create_user("double@exemple.fr")
    assert db_client.post("/clients", json=client_payload(user_id)).status_code == 201
    assert db_client.post("/clients", json=client_payload(user_id)).status_code == 409  # UNIQUE(id_user)


# --- téléphone : client, hunter, real_estate_manager ---------------------------

# ADR-007 (Q-PRO-08) : un seul champ international, indicatif compris, même
# CHECK sur les trois tables. +33000000000 est le numéro factice des données
# reprises (Q-MIG-07) : un format trop strict le refuserait.
PERSON_FIELDS: dict[str, dict[str, Any]] = {
    "/clients": {},
    "/hunters": {"hire_date": "2024-01-02", "id_realestatemanager": 25},  # manager posé par 02
    "/real-estate-managers": {},
}


def person_payload(endpoint: str, user_id: int, phone_number: str) -> dict[str, Any]:
    payload = client_payload if endpoint == "/clients" else person_fields
    return {**payload(user_id, phone_number=phone_number), **PERSON_FIELDS[endpoint]}


@pytest.mark.parametrize("endpoint", list(PERSON_FIELDS))
def test_person_national_phone_returns_409(
    db_client: TestClient, create_user: Callable[[str], int], endpoint: str
):
    payload = person_payload(endpoint, create_user("national@exemple.fr"), "0612345678")
    assert db_client.post(endpoint, json=payload).status_code == 409


@pytest.mark.parametrize("phone_number", ["+33612345678", "+33000000000"])
@pytest.mark.parametrize("endpoint", list(PERSON_FIELDS))
def test_person_international_phone_is_accepted(
    db_client: TestClient, create_user: Callable[[str], int], endpoint: str, phone_number: str
):
    payload = person_payload(endpoint, create_user("international@exemple.fr"), phone_number)
    response = db_client.post(endpoint, json=payload)
    assert response.status_code == 201, response.text


# --- code postal : estate, client, criteria ------------------------------------

# Format par pays, même CASE sur les trois tables : estate le contrôle depuis
# LOT8 (Q-SCH-11), et l'Eircode irlandais s'écrit sans espace (Q-SCH-12).


def test_estate_french_postal_code_with_four_digits_returns_409(db_client: TestClient):
    payload = {**ESTATE, "country_iso": "FR", "postal_code": "3100"}
    assert db_client.post("/estates", json=payload).status_code == 409


def test_estate_french_postal_code_with_five_digits_is_accepted(db_client: TestClient):
    payload = {**ESTATE, "country_iso": "FR", "postal_code": "31000"}
    response = db_client.post("/estates", json=payload)
    assert response.status_code == 201, response.text


EIRCODE_ENDPOINTS = ["/estates", "/clients", "/criteria"]

# Demande 1 : une seule version de départ, les suivantes s'enchaînent avec un
# motif (audit P8, P9).
NEXT_CRITERIA_VERSION: dict[str, Any] = {
    "id_author": 1, "id_search_request": 1, "id_previous_version": 1, "change_reason": "test",
}


def eircode_payload(create_user: Callable[[str], int], endpoint: str, postal_code: str) -> dict[str, Any]:
    location = {"country_iso": "IE", "postal_code": postal_code}
    if endpoint == "/estates":
        return {**ESTATE, **location, "town": "Dublin"}
    if endpoint == "/clients":
        user_id = create_user("eircode@exemple.fr")
        return client_payload(user_id, address="1 Main Street", town="Dublin", **location)
    # criteria : l'auteur 1, la demande 1 et sa version de départ 1 sont posés
    # par 02 ; une nouvelle version pointe vers celle d'avant (P8, P9).
    return {**NEXT_CRITERIA_VERSION, "estate_type": "Appartement", "budget_max": 300000, **location}


@pytest.mark.parametrize("endpoint", EIRCODE_ENDPOINTS)
def test_eircode_with_space_returns_409(
    db_client: TestClient, create_user: Callable[[str], int], endpoint: str
):
    payload = eircode_payload(create_user, endpoint, "D02 X285")
    assert db_client.post(endpoint, json=payload).status_code == 409


@pytest.mark.parametrize("endpoint", EIRCODE_ENDPOINTS)
def test_eircode_without_space_is_accepted(
    db_client: TestClient, create_user: Callable[[str], int], endpoint: str
):
    payload = eircode_payload(create_user, endpoint, "D02X285")
    response = db_client.post(endpoint, json=payload)
    assert response.status_code == 201, response.text


# chk_criteria_district_needs_town (8024210, migration 13) : un quartier exige
# une ville. L'auteur 1, la demande 1 et sa version de départ sont posés par 02.
CRITERIA: dict[str, Any] = {
    **NEXT_CRITERIA_VERSION, "estate_type": "Appartement",
    "budget_max": 300000, "country_iso": "FR", "district": "Écusson",
}


def test_criteria_district_without_town_returns_409(db_client: TestClient):
    assert db_client.post("/criteria", json=CRITERIA).status_code == 409


def test_criteria_district_with_town_is_accepted(db_client: TestClient):
    response = db_client.post("/criteria", json={**CRITERIA, "town": "Montpellier"})
    assert response.status_code == 201, response.text


# --- mandate -----------------------------------------------------------------

# Chasseur 1, client 7 et demande 1 : posés par 02 (MAND-0001). Dates en
# 2030 : aucun mandat repris ne les chevauche, la règle d'exclusivité ne
# s'en mêle pas.
MANDATE: dict[str, Any] = {
    "reference": "TEST-M-0001",
    "status": "active",
    "signature_date": "2030-01-01",
    "ends_at": "2030-07-01",
    "is_exclusive": False,
    "id_hunter": 1,
    "id_client": 7,
    "id_search_request": 1,
}


def test_mandate_lost_status_is_accepted(db_client: TestClient):
    # Q-REM-02, Q-REM-14 : vente perdue, personne n'est payé sur ce mandat.
    response = db_client.post("/mandates", json={**MANDATE, "status": "lost"})
    assert response.status_code == 201, response.text


def test_mandate_unknown_status_returns_409(db_client: TestClient):
    response = db_client.post("/mandates", json={**MANDATE, "status": "sold_elsewhere"})
    assert response.status_code == 409


def test_mandate_canceled_without_signature_is_accepted(db_client: TestClient):
    # Q-MAN-07 : un client peut renoncer avant de signer — ni date, ni fin.
    payload = {**MANDATE, "status": "canceled", "signature_date": None, "ends_at": None}
    response = db_client.post("/mandates", json=payload)
    assert response.status_code == 201, response.text


def test_mandate_active_without_signature_returns_409(db_client: TestClient):
    # chk_status_signature reste strict hors 'pending_signature' et 'canceled'.
    payload = {**MANDATE, "signature_date": None, "ends_at": None}
    assert db_client.post("/mandates", json=payload).status_code == 409


def test_mandate_six_months_is_accepted(db_client: TestClient):
    # Q-MAN-01 : signé le 2030-01-01, fini le 2030-07-01.
    response = db_client.post("/mandates", json=MANDATE)
    assert response.status_code == 201, response.text


def test_mandate_seven_months_returns_409(db_client: TestClient):
    # Q-MAN-01 : exactement 6 mois ; 7 mois passaient avec le CHECK v2.
    payload = {**MANDATE, "ends_at": "2030-08-01"}
    assert db_client.post("/mandates", json=payload).status_code == 409


def test_mandate_second_mandate_during_exclusive_returns_409(db_client: TestClient):
    # Q-MAN-02 : un exclusif bloque tout autre mandat du même client.
    first = db_client.post("/mandates", json={**MANDATE, "is_exclusive": True})
    assert first.status_code == 201, first.text
    second = {**MANDATE, "reference": "TEST-M-0002", "is_exclusive": True}
    assert db_client.post("/mandates", json=second).status_code == 409


def test_mandate_accepted_after_exclusive_canceled(db_client: TestClient):
    # Q-JEF-06 : l'annulation d'un exclusif libère le client tout de suite.
    first_payload = {**MANDATE, "is_exclusive": True}
    first = db_client.post("/mandates", json=first_payload)
    assert first.status_code == 201, first.text
    canceled = db_client.put(f"/mandates/{first.json()['id']}", json={**first_payload, "status": "canceled"})
    assert canceled.status_code == 200, canceled.text

    second = {**MANDATE, "reference": "TEST-M-0002", "is_exclusive": True}
    response = db_client.post("/mandates", json=second)
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("closed_status", ["completed", "lost"])
def test_mandate_accepted_after_exclusive_closed(db_client: TestClient, closed_status: str):
    # ADR-039, Décision 5 (D1a, 2026-10-09) : un exclusif clos, vente faite ou
    # perdue, libère le client tout de suite, comme une annulation.
    first_payload = {**MANDATE, "is_exclusive": True}
    first = db_client.post("/mandates", json=first_payload)
    assert first.status_code == 201, first.text
    closed = db_client.put(f"/mandates/{first.json()['id']}", json={**first_payload, "status": closed_status})
    assert closed.status_code == 200, closed.text

    second = {**MANDATE, "reference": "TEST-M-0002", "is_exclusive": True}
    response = db_client.post("/mandates", json=second)
    assert response.status_code == 201, response.text


def test_mandate_renewal_of_exclusive_is_accepted(db_client: TestClient):
    # Q-MAN-02 : le renouvellement, signé à l'échéance, touche la fin de son
    # parent ; le parent est exclu du contrôle, et le parent reste modifiable.
    parent_payload = {**MANDATE, "is_exclusive": True}
    parent = db_client.post("/mandates", json=parent_payload)
    assert parent.status_code == 201, parent.text
    parent_id = parent.json()["id"]

    renewal = {
        **MANDATE,
        "reference": "TEST-M-0002",
        "signature_date": "2030-07-01",
        "ends_at": "2031-01-01",
        "is_exclusive": True,
        "id_mandate_parent": parent_id,
    }
    response = db_client.post("/mandates", json=renewal)
    assert response.status_code == 201, response.text

    # 'renewed' est le statut de l'ANCIEN mandat (décision du 2026-10-08).
    closed = db_client.put(f"/mandates/{parent_id}", json={**parent_payload, "status": "renewed"})
    assert closed.status_code == 200, closed.text


def test_mandate_second_successor_returns_409(db_client: TestClient):
    # Pas d'avenant : un mandat n'a qu'un successeur (UNIQUE sur id_mandate_parent).
    parent = db_client.post("/mandates", json=MANDATE)
    assert parent.status_code == 201, parent.text
    parent_id = parent.json()["id"]

    first = {**MANDATE, "reference": "TEST-M-0002", "signature_date": "2030-07-01",
             "ends_at": "2031-01-01", "id_mandate_parent": parent_id}
    assert db_client.post("/mandates", json=first).status_code == 201

    second = {**first, "reference": "TEST-M-0003"}
    assert db_client.post("/mandates", json=second).status_code == 409


# --- review_media ------------------------------------------------------------


def review_payload(db_client: TestClient) -> dict[str, Any]:
    """Une note d'avis sur un bien neuf, pour la demande 1 posée par 02."""
    estate = db_client.post("/estates", json=ESTATE)
    assert estate.status_code == 201, estate.text
    return {
        "review_hunter": "Bien conforme à la demande.",
        "id_estate": estate.json()["id"],
        "id_search_request": 1,
        "id_hunter": 1,
    }


def test_review_accepts_several_media(db_client: TestClient):
    # Scénario 06 : « des commentaires audio et des vidéos » — plusieurs médias.
    review = db_client.post("/estate-search-requests", json=review_payload(db_client))
    assert review.status_code == 201, review.text
    review_id = review.json()["id"]

    for media_type, url in (("audio", "https://exemple.test/a.mp3"),
                            ("video", "https://exemple.test/v.mp4"),
                            ("audio", "https://exemple.test/b.mp3")):
        media = {"media_url": url, "media_type": media_type, "id_estate_searchrequest": review_id}
        response = db_client.post("/review-media", json=media)
        assert response.status_code == 201, response.text


def test_review_media_unknown_type_returns_409(db_client: TestClient):
    review = db_client.post("/estate-search-requests", json=review_payload(db_client))
    media = {"media_url": "https://exemple.test/x.gif", "media_type": "image",
             "id_estate_searchrequest": review.json()["id"]}
    assert db_client.post("/review-media", json=media).status_code == 409


def test_review_media_without_review_returns_409(db_client: TestClient):
    media = {"media_url": "https://exemple.test/a.mp3", "media_type": "audio",
             "id_estate_searchrequest": 999999}
    assert db_client.post("/review-media", json=media).status_code == 409


# --- estate_proposed ---------------------------------------------------------


def proposition_payload(db_client: TestClient, status: str) -> dict[str, Any]:
    """Une offre sur un bien neuf, pour le mandat 1 posé par 02."""
    estate = db_client.post("/estates", json=ESTATE)
    assert estate.status_code == 201, estate.text
    return {
        "proposition_status": status,
        "amount_proposition": 350000,
        "id_hunter": 1,
        "id_estate": estate.json()["id"],
        "id_mandate": 1,
    }


def test_estate_proposed_signed_status_is_accepted(db_client: TestClient):
    # Q-SCH-04 : l'offre signée (ferme D5).
    response = db_client.post("/estate-proposed", json=proposition_payload(db_client, "signed"))
    assert response.status_code == 201, response.text


def test_estate_proposed_unknown_status_returns_409(db_client: TestClient):
    response = db_client.post("/estate-proposed", json=proposition_payload(db_client, "sent"))
    assert response.status_code == 409


# D6 : la priorité du client sur un bien proposé, de 1 à 5 (Q-SCH-05, Q-JEF-18).
@pytest.mark.parametrize("priority", [1, 5])
def test_estate_proposed_priority_at_bounds_is_accepted(db_client: TestClient, priority: int):
    payload = {**proposition_payload(db_client, "offer_pending"), "client_priority": priority}
    response = db_client.post("/estate-proposed", json=payload)
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("priority", [0, 6])
def test_estate_proposed_priority_out_of_range_returns_409(db_client: TestClient, priority: int):
    payload = {**proposition_payload(db_client, "offer_pending"), "client_priority": priority}
    assert db_client.post("/estate-proposed", json=payload).status_code == 409


# --- payment -----------------------------------------------------------------

# Un détail de calcul bien formé (P32, ADR-033 ; modèle CalculationDetails).
DETAILS: dict[str, Any] = {
    "notes": {"delay": 80, "exclusivity": 100, "sales": 50, "mandates": 40, "visits": 30},
    "visit_count": 12,
    "seniority_years": 2,
    "sales_12_months": 3,
    "mandates_12_months": 5,
}


# Un refus (ADR-024) : un motif, un montant nul, et ni taux, ni score, ni
# barème, ni date d'étape.
REFUSED: dict[str, Any] = {
    "status": "refused",
    "refusal_reason": "mandate_expired",
    "amount": "0",
    "announced_at": None,
    "base_rate": None,
    "seniority_rate": None,
    "performance_rate": None,
    "final_rate": None,
    "performance_score": None,
    "calculation_details": None,
    "id_commission_scale": None,
    "id_hunter_rate_parameters": None,
}


def fees_grid(db_client: TestClient, effective_from: str = "2025-01-01") -> int:
    """Une grille d'honoraires : 3 000 € + 2,5 % du prix (D1 du sujet)."""
    grid = db_client.post(
        "/parameters-fees",
        json={"effective_from": effective_from, "fixed_amount": 3000, "rate": "0.0250"},
    )
    assert grid.status_code == 201, grid.text
    return grid.json()["id"]


def rate_parameters(db_client: TestClient) -> int:
    """Une version des réglages du taux (valeurs : HUNTER_RATE_PARAMETERS, plus bas)."""
    version = db_client.post("/hunter-rate-parameters", json=HUNTER_RATE_PARAMETERS)
    assert version.status_code == 201, version.text
    return version.json()["id"]


def sale_payload(db_client: TestClient, **overrides: Any) -> dict[str, Any]:
    """Une vente sur un bien neuf, pour le mandat 1 posé par 02."""
    estate = db_client.post("/estates", json=ESTATE)
    assert estate.status_code == 201, estate.text
    payload: dict[str, Any] = {
        "signature_date": "2026-03-01",
        "purchase_amount": 354712,
        "fees_amount": "11867.80",  # 3 000 € + 2,5 % du prix
        "sale_origin": "hunter",
        "id_mandate": 1,
        "id_estate": estate.json()["id"],
    }
    payload.update(overrides)
    if "id_parameters_fees" not in payload:
        payload["id_parameters_fees"] = fees_grid(db_client)
    return payload


def payment_payload(db_client: TestClient, **overrides: Any) -> dict[str, Any]:
    """Un paiement annoncé, sur une vente neuve du mandat 1 posé par 02."""
    sale = db_client.post("/sales", json=sale_payload(db_client))
    assert sale.status_code == 201, sale.text
    scale = db_client.post(
        "/commission-scales",
        json={"amount_min": 0, "rate": "0.3000", "valid_from": "2025-01-01"},
    )
    assert scale.status_code == 201, scale.text
    payload: dict[str, Any] = {
        "amount": "3560.34",
        "status": "announced",
        "announced_at": "2026-03-02T09:00:00Z",
        "base_rate": "0.3000",
        "seniority_rate": "0.0000",
        "performance_rate": "0.0000",
        "final_rate": "0.3000",
        "performance_score": "50.0",
        "calculation_details": DETAILS,
        "id_sale": sale.json()["id"],
        "id_hunter": 1,
        "id_commission_scale": scale.json()["id"],
        "id_hunter_rate_parameters": rate_parameters(db_client),
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("rate", ["0.20", "0.60"])
def test_payment_final_rate_at_bounds_is_accepted(db_client: TestClient, rate: str):
    # Q-REM-19 (R21) : 20 % et 60 % sont permis, bornes comprises. Le taux de
    # base suit, sinon P33 (taux recalculé, fiche API5) refuserait l'écart.
    response = db_client.post("/payments", json=payment_payload(db_client, base_rate=rate, final_rate=rate))
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("rate", ["0.19", "0.61"])
def test_payment_final_rate_out_of_bounds_returns_409(db_client: TestClient, rate: str):
    # Q-REM-19 : 0,19 et 0,61 passaient avec le CHECK v2 (de 0 à 1).
    response = db_client.post("/payments", json=payment_payload(db_client, final_rate=rate))
    assert response.status_code == 409


def test_payment_without_final_rate_returns_409(db_client: TestClient):
    # Q-REM-10 : hors refus, le taux final est exigé (chk_refused).
    response = db_client.post("/payments", json=payment_payload(db_client, final_rate=None))
    assert response.status_code == 409


def test_refused_payment_is_accepted(db_client: TestClient):
    response = db_client.post("/payments", json=payment_payload(db_client, **REFUSED))
    assert response.status_code == 201, response.text


def test_refused_payment_with_final_rate_returns_409(db_client: TestClient):
    # chk_refused, dans l'autre sens : un refus ne porte aucun taux.
    payload = payment_payload(db_client, **{**REFUSED, "final_rate": "0.3000"})
    assert db_client.post("/payments", json=payload).status_code == 409


def test_refused_payment_with_performance_score_returns_409(db_client: TestClient):
    # Q-REM-03 : pas de score figé sur un refus.
    payload = payment_payload(db_client, **{**REFUSED, "performance_score": "50.0"})
    assert db_client.post("/payments", json=payload).status_code == 409


def test_payment_without_performance_score_returns_409(db_client: TestClient):
    # ADR-033, Décision 3 (D2, 2026-10-09) : hors refus, la note est exigée.
    payload = payment_payload(db_client, performance_score=None)
    assert db_client.post("/payments", json=payload).status_code == 409


def test_payment_without_calculation_details_returns_409(db_client: TestClient):
    # ADR-033, Décision 3 : hors refus, le détail du calcul est exigé.
    payload = payment_payload(db_client, calculation_details=None)
    assert db_client.post("/payments", json=payload).status_code == 409


def test_refused_payment_with_calculation_details_returns_409(db_client: TestClient):
    # ADR-033, Décision 3, dans l'autre sens : un refus ne porte aucun détail.
    payload = payment_payload(db_client, **{**REFUSED, "calculation_details": DETAILS})
    assert db_client.post("/payments", json=payload).status_code == 409


def test_payment_without_rate_parameters_returns_409(db_client: TestClient):
    # G1 : hors refus, la version des réglages du taux est exigée (chk_refused).
    payload = payment_payload(db_client, id_hunter_rate_parameters=None)
    assert db_client.post("/payments", json=payload).status_code == 409


def test_refused_payment_with_rate_parameters_returns_409(db_client: TestClient):
    # G1, dans l'autre sens : un refus ne désigne aucune version de réglages.
    # Le refus garde la version que payment_payload a créée.
    refused = {k: v for k, v in REFUSED.items() if k != "id_hunter_rate_parameters"}
    payload = payment_payload(db_client, **refused)
    assert db_client.post("/payments", json=payload).status_code == 409


def test_payment_unknown_rate_parameters_returns_409(db_client: TestClient):
    # G1 : la clé étrangère refuse une version qui n'existe pas.
    payload = payment_payload(db_client, id_hunter_rate_parameters=999999)
    assert db_client.post("/payments", json=payload).status_code == 409


def test_payment_announced_without_date_returns_409(db_client: TestClient):
    # Q-REM-17 : chk_announced — annoncé, donc daté.
    response = db_client.post("/payments", json=payment_payload(db_client, announced_at=None))
    assert response.status_code == 409


def test_payment_scheduled_without_date_returns_409(db_client: TestClient):
    # Q-REM-17 : chk_scheduled — programmé, donc prévu pour un jour.
    response = db_client.post("/payments", json=payment_payload(db_client, status="scheduled"))
    assert response.status_code == 409


def test_payment_paid_keeps_its_dates_and_details(db_client: TestClient):
    # Q-REM-17 : un paiement fait garde ses trois dates. Q-REM-04 : les
    # termes du calcul se relisent tels quels (clés de CalculationDetails).
    details = {**DETAILS, "mandate_signature_date": "2026-01-05", "is_exclusive": True}
    payload = payment_payload(
        db_client,
        status="paid",
        scheduled_for="2026-03-15",
        paid_at="2026-03-15T10:00:00Z",
        calculation_details=details,
    )
    created = db_client.post("/payments", json=payload)
    assert created.status_code == 201, created.text

    read = db_client.get(f"/payments/{created.json()['id']}")
    assert read.json()["calculation_details"] == details


def test_payment_paid_in_the_future_returns_409(db_client: TestClient):
    # Audit P34 : un paiement payé a eu lieu (chk_paid_not_in_future).
    payload = payment_payload(
        db_client, status="paid", scheduled_for="2099-03-15", paid_at="2099-03-15T10:00:00Z"
    )
    assert db_client.post("/payments", json=payload).status_code == 409


@pytest.mark.parametrize(
    ("field", "value", "final"),
    [("seniority_rate", "0.1200", "0.3360"), ("performance_rate", "-0.2500", "0.2250")],
)
def test_payment_rate_beyond_v2_bounds_is_accepted(db_client: TestClient, field: str, value: str, final: str):
    # Q-REM-05 : +10 % et ±20 % sont des paramètres (REGLES-CALCUL l. 59),
    # plus des CHECK. 0,12 et -0,25 étaient refusés en v2. Le taux final est
    # celui que P33 recalcule : 0,30 × (1 + 0,12) et 0,30 × (1 - 0,25).
    response = db_client.post("/payments", json=payment_payload(db_client, **{field: value, "final_rate": final}))
    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seniority_rate", "-0.0100"),  # a = min(taux × années ; plafond) >= 0
        ("seniority_rate", "1.5000"),
        ("performance_rate", "-1.5000"),  # 1 + a + p doit rester positif
        ("performance_rate", "1.5000"),
    ],
)
def test_payment_rate_out_of_domain_returns_409(db_client: TestClient, field: str, value: str):
    # Q-REM-05 : restent les bornes du domaine, justifiées dans init-v3/01.
    response = db_client.post("/payments", json=payment_payload(db_client, **{field: value}))
    assert response.status_code == 409


# --- commission_scale --------------------------------------------------------


def test_commission_scale_zero_rate_returns_409(db_client: TestClient):
    # Q-SCH-15 : une tranche à 0 % passait avec le CHECK v2 (>= 0).
    response = db_client.post(
        "/commission-scales",
        json={"amount_min": 0, "rate": "0", "valid_from": "2025-01-01"},
    )
    assert response.status_code == 409


# --- parameters_fees ---------------------------------------------------------


def test_parameters_fees_same_effective_from_returns_409(db_client: TestClient):
    # Q-SCH-17 : deux grilles ne démarrent pas le même jour.
    fees_grid(db_client, "2025-01-01")
    response = db_client.post(
        "/parameters-fees",
        json={"effective_from": "2025-01-01", "fixed_amount": 3500, "rate": "0.0300"},
    )
    assert response.status_code == 409


def test_parameters_fees_next_grid_is_accepted(db_client: TestClient):
    # Q-SCH-17 : la grille suivante clôt la précédente, sans date de fin à
    # écrire. Avec l'EXCLUDE de v2, deux grilles ouvertes se chevauchaient.
    fees_grid(db_client, "2025-01-01")
    response = db_client.post(
        "/parameters-fees",
        json={"effective_from": "2026-01-01", "fixed_amount": 3500, "rate": "0.0300"},
    )
    assert response.status_code == 201, response.text


# --- sale --------------------------------------------------------------------


def test_sale_unknown_fees_grid_returns_409(db_client: TestClient):
    # Q-REM-13 : une vente pointe une grille d'honoraires qui existe.
    payload = sale_payload(db_client, id_parameters_fees=999999)
    assert db_client.post("/sales", json=payload).status_code == 409


def test_sale_second_sale_of_same_estate_returns_409(db_client: TestClient):
    # P37 (ADR-053) : un bien n'est vendu qu'une fois, même sur un autre mandat.
    payload = sale_payload(db_client)
    first = db_client.post("/sales", json=payload)
    assert first.status_code == 201, first.text
    # Même bien, même grille ; seul le mandat change (sale_payload créerait un autre bien).
    assert db_client.post("/sales", json={**payload, "id_mandate": 2}).status_code == 409


# --- hunter_performance ------------------------------------------------------
#
# POST /hunter-performances est fermé à tous (ADR-035, fiche API2) : ces tests
# écrivent par le service, qui traduit la contrainte violée en ConflictError
# (le 409 de la route, prouvé par test_crud_router.py).


def score_payload(**overrides: Any) -> dict[str, Any]:
    """Une note du chasseur 1, posé par 02."""
    payload: dict[str, Any] = {
        "score": "62.5",
        "scored_at": "2026-03-02T10:00:00Z",
        "trigger_type": "initial",
        "id_hunter": 1,
    }
    payload.update(overrides)
    return payload


def add_score(db_session: SQLModelSession, payload: dict[str, Any]) -> HunterPerformance:
    """Écrit une note comme le fera le service de rémunération (API12)."""
    service = HunterPerformanceService(HunterPerformanceRepository())
    return service.create(db_session, HunterPerformance.model_validate(payload))


def test_hunter_performance_same_payment_twice_conflicts(db_client: TestClient, db_session: SQLModelSession):
    # Q-SCH-06 : un paiement donne une note, une seule (uq_perf_payment).
    payment = db_client.post("/payments", json=payment_payload(db_client))
    assert payment.status_code == 201, payment.text
    first = score_payload(trigger_type="payment", id_payment=payment.json()["id"])
    add_score(db_session, first)
    second = {**first, "scored_at": "2026-03-02T11:00:00Z"}
    with pytest.raises(ConflictError):
        add_score(db_session, second)


def test_hunter_performance_of_another_hunters_payment_conflicts(db_client: TestClient, db_session: SQLModelSession):
    # Audit P35 : la note du paiement du chasseur 1 ne va pas au chasseur 2
    # (fk_perf_payment_same_hunter).
    payment = db_client.post("/payments", json=payment_payload(db_client))
    assert payment.status_code == 201, payment.text
    score = score_payload(trigger_type="payment", id_payment=payment.json()["id"], id_hunter=2)
    with pytest.raises(ConflictError):
        add_score(db_session, score)


def test_hunter_performance_same_mandate_twice_conflicts(db_session: SQLModelSession):
    # Q-SCH-06 : un mandat échu donne une note, une seule (uq_perf_mandate).
    first = score_payload(trigger_type="mandate_expired", id_mandate=1)
    add_score(db_session, first)
    second = {**first, "scored_at": "2026-03-02T11:00:00Z"}
    with pytest.raises(ConflictError):
        add_score(db_session, second)


def test_hunter_performance_two_scores_same_day_are_accepted(db_session: SQLModelSession):
    # Q-SCH-06 (ferme D9) : la note se recalcule à chaque événement, donc deux
    # notes le même jour passent. En v2, excl_perf_no_overlap ('[]') les
    # refusait : il fallait un jour d'écart.
    morning = score_payload(scored_at="2026-03-02T09:00:00Z")
    evening = score_payload(scored_at="2026-03-02T17:00:00Z", trigger_type="mandate_expired", id_mandate=1)
    add_score(db_session, morning)
    assert add_score(db_session, evening).id is not None


# --- hunter_rate_parameters -------------------------------------------------

# Les valeurs par défaut du sujet (rem.py:310-337), en exemple.
HUNTER_RATE_PARAMETERS: dict[str, Any] = {
    "effective_from": "2025-01-01",
    "weight_delay": "0.25",
    "weight_exclusivity": "0.10",
    "weight_sales": "0.25",
    "weight_mandates": "0.15",
    "weight_visits": "0.25",
    "delay_tiers": [
        {"maximum": 12, "note": 100},
        {"maximum": 20, "note": 80},
        {"maximum": 28, "note": 60},
        {"maximum": 36, "note": 40},
        {"maximum": 48, "note": 20},
        {"maximum": None, "note": 0},
    ],
    "visit_tiers": [
        {"maximum": 3, "note": 100},
        {"maximum": 6, "note": 80},
        {"maximum": 9, "note": 60},
        {"maximum": 12, "note": 40},
        {"maximum": 15, "note": 20},
        {"maximum": None, "note": 0},
    ],
    "score_exclusive": "100",
    "score_non_exclusive": "60",
    "points_per_sale": "20",
    "points_per_mandate": "10",
    "window_months": 12,
    "seniority_rate_per_year": "0.02",
    "seniority_cap": "0.10",
    "score_pivot": "50",
    "score_half_range": "50",
    "performance_amplitude": "0.20",
    "rate_floor": "0.20",
    "rate_ceiling": "0.60",
}


def test_hunter_rate_parameters_keep_their_tiers(db_client: TestClient):
    # Q-REM-05 : la table est exposée comme les 18 autres ; les paliers se
    # relisent tels qu'écrits.
    created = db_client.post("/hunter-rate-parameters", json=HUNTER_RATE_PARAMETERS)
    assert created.status_code == 201, created.text

    read = db_client.get(f"/hunter-rate-parameters/{created.json()['id']}")
    assert read.json()["delay_tiers"] == HUNTER_RATE_PARAMETERS["delay_tiers"]
    assert read.json()["visit_tiers"] == HUNTER_RATE_PARAMETERS["visit_tiers"]


def test_hunter_rate_parameters_same_effective_from_returns_409(db_client: TestClient):
    # Q-REM-05, versions comme Q-SCH-17 : deux versions ne démarrent pas le
    # même jour (uq_hunter_rate_effective_from).
    first = db_client.post("/hunter-rate-parameters", json=HUNTER_RATE_PARAMETERS)
    assert first.status_code == 201, first.text
    second = {**HUNTER_RATE_PARAMETERS, "rate_ceiling": "0.65"}
    assert db_client.post("/hunter-rate-parameters", json=second).status_code == 409


# --- rôle en lecture seule (Q14, LOT12) --------------------------------------
# SET LOCAL ROLE : la session prend les droits de fil_rouge_reader jusqu'à la
# fin de sa transaction, annulée par la fixture ; pas besoin de son mot de passe.


def test_reader_role_can_select(db_session: Session):
    connection = db_session.connection()
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    # 'Reader' : le pendant applicatif du rôle (02_migration.sql).
    wording = connection.execute(text("SELECT wording FROM role WHERE id = 5")).scalar_one()
    assert wording == "Reader"


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO role (wording) VALUES ('Reader')",
        "UPDATE role SET wording = wording WHERE id = 5",
        "DELETE FROM role WHERE id = 5",
    ],
    ids=["insert", "update", "delete"],
)
def test_reader_role_cannot_write(db_session: Session, statement: str):
    connection = db_session.connection()
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        connection.execute(text(statement))


def test_reader_role_cannot_read_password(db_session: Session):
    # Rapport « Rôle lecteur et mots de passe » (2026-10-08) : le mot de passe
    # reste fermé au rôle, même si la table est ouverte pour le reste.
    connection = db_session.connection()
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        connection.execute(text('SELECT password FROM "user"'))


def test_reader_role_reads_every_other_user_column(db_session: Session):
    # La liste vient de la base, pas du test : une colonne ajoutée à "user"
    # sans décision (ouverte au rôle, ou fermée ici) fait échouer ce test.
    connection = db_session.connection()
    columns = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'user' "
            "AND column_name <> 'password'"
        )
    ).scalars().all()
    assert columns, "aucune colonne lue dans information_schema"
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    quoted = ", ".join(f'"{name}"' for name in columns)
    connection.execute(text(f'SELECT {quoted} FROM "user"')).all()


@pytest.mark.parametrize("table", ["criteria", "estate"])
def test_needs_renovation_has_two_states(db_session: Session, table: str):
    # S7 (ADR-032) : BOOLEAN NOT NULL DEFAULT FALSE, jamais NULL.
    row = db_session.connection().execute(
        text(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t "
            "AND column_name = 'needs_renovation'"
        ),
        {"t": table},
    ).one()
    assert row.is_nullable == "NO"
    assert row.column_default == "false"


def test_criteria_has_no_renovation_budget(db_session: Session):
    # S7 (ADR-032) : les deux budgets travaux sont retirés du schéma.
    names = db_session.connection().execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'criteria' "
            "AND column_name LIKE 'renovation_budget%'"
        )
    ).scalars().all()
    assert names == []
