"""
test_note_mandat_expire.py — La note 'mandate_expired' d'un mandat expiré (choix PERF-EXP).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le sujet veut qu'un mandat fini sans vente fasse baisser la note du
chasseur (`Readme.md:135` ; F10:295-300). La règle est ADR-048, point 8 :
à l'échéance, les trois notes de vente sont reprises du dernier paiement
payé (50, le pivot, s'il n'y en a pas) ; les deux critères d'activité sont
recomptés au jour de la fin du mandat.

`POST /hunter-performances/expired-mandates` (Admin seul) écrit cette note
pour chaque mandat 'expired' qui n'en a pas encore. Le DAG Airflow
`mandate_expiry` passe les mandats en 'expired' ; cette route les note.

La base de test (02) donne au chasseur 1 le mandat n° 11, 'expired', signé
le 2026-01-05, fini le 2026-07-05, sans vente ; aucun paiement.
============================================================================
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.app.models import HunterPerformance
from src.app.repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from src.app.services.parametrage_service import performance
from src.app.services.remuneration import calculer_score
from src.app.utils.roles import CLIENT, HUNTER, MANAGER, READER

from ..conftest import acting_as
from .test_calcul_paiement import ready_sale
from .test_constraints_db import HUNTER_ID, HUNTER_PROFILE, rate_parameters

ROUTE = "/hunter-performances/expired-mandates"
MANDATE_11, MANDATE_11_END = 11, date(2026, 7, 5)
PIVOT = Decimal(50)


def note_of(db_session: Session, mandate_id: int) -> list[HunterPerformance]:
    query = select(HunterPerformance).where(HunterPerformance.id_mandate == mandate_id)
    return list(db_session.exec(query).all())


def expected_score(db_session: Session, version_id: int, notes: dict[str, Decimal]) -> Decimal:
    settings = HunterRateParametersRepository().get_by_id(db_session, version_id)
    assert settings is not None
    return calculer_score(notes, performance(settings))


def test_an_expired_mandate_without_any_paid_sale_gets_the_pivot_and_its_activity(
    db_client: TestClient, db_session: Session
):
    version = rate_parameters(db_client)

    response = db_client.post(ROUTE)

    assert response.status_code == 200, response.text
    assert "MAND-0011" in response.json()["references"]
    [note] = note_of(db_session, MANDATE_11)
    # Au 2026-07-05, fenêtre de 12 mois : 0 vente -> 0 ; une chaîne arrivée
    # à son issue (n° 11, sans vente) -> taux 0/1 -> 0. Notes de vente : 50.
    notes = {"delai": PIVOT, "exclusivite": PIVOT, "visites": PIVOT, "ventes": Decimal(0), "mandats": Decimal(0)}
    assert note.score == expected_score(db_session, version, notes)
    assert (note.trigger_type, note.id_hunter, note.id_payment) == ("mandate_expired", HUNTER_PROFILE, None)
    assert note.scored_at == datetime(2026, 7, 5, tzinfo=timezone.utc)


def test_the_sale_notes_come_from_the_last_paid_payment(db_client: TestClient, db_session: Session):
    sale_id, _ = ready_sale(db_client)
    payment = db_client.post(f"/sales/{sale_id}/payment").json()
    payment = {**payment, "status": "scheduled", "scheduled_for": "2026-03-10"}
    assert db_client.put(f"/payments/{payment['id']}", json=payment).status_code == 200
    payment = {**payment, "status": "paid", "paid_at": "2026-03-15T10:00:00Z"}
    assert db_client.put(f"/payments/{payment['id']}", json=payment).status_code == 200

    assert db_client.post(ROUTE).status_code == 200

    [note] = note_of(db_session, MANDATE_11)
    # Au 2026-07-05 : la vente du 2026-03-01 -> 1 vente, 20 points ; deux
    # chaînes à leur issue (celle de la vente, vendue ; n° 11, non) -> 1/2 -> 50.
    kept = payment["calculation_details"]["notes"]
    notes = {"delai": Decimal(str(kept["delay"])), "exclusivite": Decimal(str(kept["exclusivity"])),
             "visites": Decimal(str(kept["visits"])), "ventes": Decimal(20), "mandats": Decimal(50)}
    assert note.score == expected_score(db_session, payment["id_hunter_rate_parameters"], notes)


def test_a_second_call_writes_nothing_more(db_client: TestClient, db_session: Session):
    rate_parameters(db_client)
    first = db_client.post(ROUTE).json()

    second = db_client.post(ROUTE).json()

    assert first["scored"] >= 1
    assert (second["scored"], second["references"]) == (0, [])
    assert len(note_of(db_session, MANDATE_11)) == 1


def test_without_rate_parameters_the_route_returns_409(db_client: TestClient):
    # Base de test sans réglages du taux : erreur de paramétrage, pas une note inventée.
    response = db_client.post(ROUTE)

    assert response.status_code == 409
    assert "Paramétrage incomplet" in response.json()["detail"]


@pytest.mark.parametrize("role", [HUNTER, MANAGER, CLIENT, READER])
def test_only_admin_scores_the_expired_mandates(db_client: TestClient, role: str):
    with acting_as(role, HUNTER_ID):
        response = db_client.post(ROUTE)
    assert response.status_code == 403
