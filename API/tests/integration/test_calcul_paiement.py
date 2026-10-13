"""
test_calcul_paiement.py — Le calcul de rémunération branché sur la base (fiche API12).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
`POST /sales/{id}/payment` compte en base les visites, les ventes et les
mandats du chasseur, charge le paramétrage à la date de l'acte, appelle
`calculer_remuneration` et crée le paiement. Deux parties :

1. Les comptages purs (`payment_calculation_service.py`), sans base : la
   chaîne de renouvellements, la première issue, la fenêtre (ADR-048).
2. La route, sur la base de test : le montant est celui que
   `calculer_remuneration` donne sur les MÊMES nombres, écrits ici à la
   main ; une 2e demande rend 409 ; la note 'payment' du journal n'existe
   qu'une fois le paiement payé (ADR-035).

La base de test (02) donne au chasseur 1, embauché le 2023-03-15, des
mandats racines : n° 3 signé le 2025-04-05, échu le 2025-10-05 sans vente ;
n° 11 signé le 2026-01-05, fin le 2026-07-05 ; n° 15 signé le 2026-03-25.
Ni vente, ni visite, ni paiement.
============================================================================
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.app.models import HunterPerformance, Mandate, Sale, Visit
from src.app.repositories.commission_scale_repository import CommissionScaleRepository
from src.app.repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from src.app.repositories.parameters_fees_repository import ParametersFeesRepository
from src.app.services.parametrage_service import ParametrageService, performance
from src.app.services.payment_calculation_service import (
    count_activity,
    count_client_visits,
    full_years,
    months_before,
)
from src.app.services.remuneration import (
    Exclusivite,
    OrigineVente,
    Vente,
    calculer_remuneration,
    calculer_score,
)

from .test_constraints_db import HUNTER_ID, rate_parameters, sale_payload

ACTE = date(2026, 3, 1)


# --- 1. Les comptages purs ---------------------------------------------------


def mandate(mid: int, signed: Optional[date], ends: Optional[date], status: str = "completed",
            parent: Optional[int] = None) -> Mandate:
    return Mandate(id=mid, reference=f"M-{mid}", status=status, signature_date=signed, ends_at=ends,
                   is_exclusive=False, id_hunter=HUNTER_ID, id_client=7, id_search_request=1,
                   id_mandate_parent=parent)


def sale(sid: int, mandate_id: int, signed: date) -> Sale:
    return Sale(id=sid, signature_date=signed, purchase_amount=300000, fees_amount=Decimal("10500.00"),
                sale_origin="hunter", id_mandate=mandate_id, id_estate=1, id_parameters_fees=1)


def test_months_before_keeps_the_last_day_of_a_short_month():
    assert months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert months_before(ACTE, 12) == date(2025, 3, 1)


def test_full_years_counts_only_completed_years():
    assert full_years(date(2023, 3, 15), ACTE) == 2
    assert full_years(date(2023, 3, 15), date(2026, 3, 15)) == 3


def test_a_renewed_chain_counts_once_and_is_sold_by_its_renewal():
    # ADR-050 et Q-REM-09 : la racine (1) et son renouvellement (2) font une chaîne.
    mandates = [mandate(1, date(2025, 6, 1), date(2025, 12, 1), "renewed"),
                mandate(2, date(2025, 12, 1), date(2026, 6, 1), "completed", parent=1)]
    activity = count_activity(mandates, [sale(10, 2, date(2026, 1, 15))], set(), ACTE, 12)
    assert (activity.sales, activity.mandates, activity.sold_mandates) == (1, 1, 1)


def test_a_lost_mandate_is_an_issue_without_sale():
    # ADR-048, point 7 : une clôture après signature est une première issue.
    mandates = [mandate(1, date(2025, 12, 1), date(2026, 6, 1), "lost")]
    activity = count_activity(mandates, [], set(), ACTE, 12)
    assert (activity.mandates, activity.sold_mandates) == (1, 0)


def test_a_running_chain_is_not_yet_counted():
    # Ni vente, ni clôture, échéance après l'acte : pas encore de première issue.
    mandates = [mandate(1, date(2025, 12, 1), date(2026, 6, 1), "active")]
    assert count_activity(mandates, [], set(), ACTE, 12).mandates == 0


def test_a_refused_sale_closes_the_chain_without_selling_it():
    # Q-REM-08 : une vente au paiement refusé ne compte pas, mais c'est une issue.
    mandates = [mandate(1, date(2025, 6, 1), date(2025, 12, 1))]
    activity = count_activity(mandates, [sale(10, 1, date(2025, 11, 1))], {10}, ACTE, 12)
    assert (activity.sales, activity.mandates, activity.sold_mandates) == (0, 1, 0)


def test_the_current_sale_and_its_chain_are_excluded():
    # RCR:470 et ADR-048, point 7 : la vente en cours est hors des deux termes.
    mandates = [mandate(1, date(2025, 6, 1), date(2025, 12, 1)), mandate(2, date(2026, 1, 10), date(2026, 7, 10))]
    sales = [sale(10, 1, date(2025, 11, 1)), sale(11, 2, ACTE)]
    activity = count_activity(mandates, sales, set(), ACTE, 12, excluded_sale_id=11)
    assert (activity.sales, activity.mandates, activity.sold_mandates) == (1, 1, 1)


def test_chains_signed_out_of_the_window_or_unsigned_are_left_out():
    mandates = [mandate(1, date(2025, 3, 1), date(2025, 9, 1)),   # borne basse exclue
                mandate(2, None, None, "canceled")]                # jamais signé (ADR-048)
    assert count_activity(mandates, [], set(), ACTE, 12).mandates == 0


def test_only_client_visits_of_the_chain_count_until_the_deed():
    # ADR-048 point 4, ADR-053 : les visites 'hunter' (repérage) ne comptent pas.
    visits = [Visit(visit_date=date(2026, 2, 10), visitor_type="client", id_estate=1, id_mandate=1),
              Visit(visit_date=date(2026, 2, 11), visitor_type="hunter", id_estate=1, id_mandate=1),
              Visit(visit_date=date(2026, 2, 12), visitor_type="client", id_estate=1, id_mandate=9),
              Visit(visit_date=date(2026, 3, 2), visitor_type="client", id_estate=1, id_mandate=1)]
    assert count_client_visits(visits, {1}, ACTE) == 1


# --- 2. La route, sur la base ------------------------------------------------


def parametrage_service() -> ParametrageService:
    return ParametrageService(ParametersFeesRepository(), CommissionScaleRepository(), HunterRateParametersRepository())


def ready_sale(db_client: TestClient, **overrides: Any) -> tuple[int, int]:
    """
    Une vente de 354 712 € le 2026-03-01 sur un mandat neuf non exclusif
    signé le 2026-02-01 (sale_payload), son paramétrage, et cinq visites
    sur le bien vendu : 2 du client, 3 de repérage du chasseur.
    """
    payload = sale_payload(db_client, **overrides)
    scale = db_client.post("/commission-scales", json={"amount_min": 0, "rate": "0.3000", "valid_from": "2025-01-01"})
    assert scale.status_code == 201, scale.text
    rate_parameters(db_client)
    created = db_client.post("/sales", json=payload)
    assert created.status_code == 201, created.text
    for day, who in [(10, "client"), (12, "hunter"), (14, "hunter"), (20, "client"), (22, "hunter")]:
        visit = {"visit_date": f"2026-02-{day}", "visitor_type": who,
                 "id_estate": payload["id_estate"], "id_mandate": payload["id_mandate"]}
        response = db_client.post("/visits", json=visit)
        assert response.status_code == 201, response.text
    return created.json()["id"], payload["id_mandate"]


# Les nombres de la vente, écrits à la main depuis la base de test (en-tête).
EXPECTED = Vente(
    chasseur_id=HUNTER_ID,
    prix_acte=Decimal(354712),
    date_acte=ACTE,
    date_signature_mandat=date(2026, 2, 1),
    date_fin_mandat=date(2026, 8, 1),
    exclusivite=Exclusivite.NON_EXCLUSIF,
    origine=OrigineVente.CHASSEUR,
    nb_visites=2,               # les 2 visites 'client', pas les 3 'hunter'
    annees_anciennete=2,        # 2023-03-15 -> 2026-03-01
    ventes_12_mois=0,           # vente en cours exclue
    mandats_12_mois=1,          # n° 3, échu sans vente ; n° 11 court encore
    mandats_vendus_12_mois=0,
)


def test_payment_amount_is_the_calculation_on_the_same_numbers(db_client: TestClient, db_session: Session):
    sale_id, _ = ready_sale(db_client)
    response = db_client.post(f"/sales/{sale_id}/payment")
    assert response.status_code == 201, response.text
    body = response.json()
    expected = calculer_remuneration(EXPECTED, parametrage_service().charger(db_session, ACTE))
    assert body["status"] == "announced"
    assert Decimal(body["amount"]) == expected.montant
    assert Decimal(body["final_rate"]) == expected.taux_final
    assert Decimal(body["performance_score"]) == expected.score_performance
    details = body["calculation_details"]
    assert (details["visit_count"], details["seniority_years"], details["sales_12_months"],
            details["mandates_12_months"], details["sold_mandates_12_months"]) == (2, 2, 0, 1, 0)
    assert details["mandate_signature_date"] == "2026-02-01"


def test_second_payment_for_the_same_sale_returns_409(db_client: TestClient):
    sale_id, _ = ready_sale(db_client)
    assert db_client.post(f"/sales/{sale_id}/payment").status_code == 201
    assert db_client.post(f"/sales/{sale_id}/payment").status_code == 409


def test_unknown_sale_returns_404(db_client: TestClient):
    assert db_client.post("/sales/999999/payment").status_code == 404


def test_sale_out_of_scope_gives_a_refused_payment(db_client: TestClient):
    # ADR-024 : non exclusif et client seul -> un droit fermé, pas un paiement à zéro.
    sale_id, _ = ready_sale(db_client, sale_origin="client_alone")
    response = db_client.post(f"/sales/{sale_id}/payment")
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["refusal_reason"], Decimal(body["amount"])) == ("refused", "out_of_scope", 0)


def notes_of(db_session: Session, payment_id: int) -> list[HunterPerformance]:
    query = select(HunterPerformance).where(HunterPerformance.id_payment == payment_id)
    return list(db_session.exec(query).all())


def test_journal_note_is_written_only_when_paid(db_client: TestClient, db_session: Session):
    # ADR-035 : la note 'payment' s'écrit au passage à 'paid', jamais avant.
    sale_id, _ = ready_sale(db_client)
    payment = db_client.post(f"/sales/{sale_id}/payment").json()
    assert notes_of(db_session, payment["id"]) == []

    payment = {**payment, "status": "scheduled", "scheduled_for": "2026-03-10"}
    assert db_client.put(f"/payments/{payment['id']}", json=payment).status_code == 200
    assert notes_of(db_session, payment["id"]) == []

    payment = {**payment, "status": "paid", "paid_at": "2026-03-15T10:00:00Z"}
    assert db_client.put(f"/payments/{payment['id']}", json=payment).status_code == 200
    [note] = notes_of(db_session, payment["id"])

    # Au 2026-03-15, rien d'exclu : 1 vente (20 points) ; 2 chaînes arrivées
    # à leur issue, n° 3 sans vente et celle de la vente -> 1/2 -> 50 points.
    kept = payment["calculation_details"]["notes"]
    notes = {"delai": Decimal(str(kept["delay"])), "exclusivite": Decimal(str(kept["exclusivity"])),
             "visites": Decimal(str(kept["visits"])), "ventes": Decimal(20), "mandats": Decimal(50)}
    settings = HunterRateParametersRepository().get_by_id(db_session, payment["id_hunter_rate_parameters"])
    assert settings is not None
    assert note.score == calculer_score(notes, performance(settings))
    assert (note.trigger_type, note.id_hunter, note.scored_at.date()) == ("payment", HUNTER_ID, date(2026, 3, 15))
