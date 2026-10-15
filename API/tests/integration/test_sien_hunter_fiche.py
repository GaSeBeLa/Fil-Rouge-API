"""
« Le sien » du Hunter et du Manager suit le numéro de leur fiche (fiche PRF4).

Depuis le chantier PRF (2026-10-15), mandate.id_hunter et
hunter.id_realestatemanager citent hunter.id et real_estate_manager.id.
Un manager et un chasseur neufs, dont la fiche a un id différent de
l'id_user :

- le chasseur voit son mandat, pas celui d'un autre chasseur (404) ;
- il écrit une visite sur son mandat (hunter_rows.handles_mandate) ;
- le manager voit son chasseur, pas celui d'un autre manager ;
- build_vente rend ce chasseur, par le numéro de sa fiche.

Une fiche bouche-trou de chaque sorte est créée d'abord : les numéros de
fiche ne peuvent pas tomber sur les numéros de compte.
"""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, update

from src.app.models import Client, Hunter, Mandate, RealEstateManager, Sale, SearchRequest, User
from src.app.repositories.commission_scale_repository import CommissionScaleRepository
from src.app.repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from src.app.repositories.hunter_repository import HunterRepository
from src.app.repositories.mandate_repository import MandateRepository
from src.app.repositories.payment_repository import PaymentRepository
from src.app.repositories.sale_repository import SaleRepository
from src.app.repositories.visit_repository import VisitRepository
from src.app.services.payment_calculation_service import PaymentCalculationService
from src.app.utils.roles import HUNTER, MANAGER

from ..conftest import acting_as
from .test_calcul_paiement import ACTE, parametrage_service
from .test_constraints_db import CLIENT_ADDRESS, ESTATE, MANAGER_ID, rate_parameters

# Chasseur 2 du seed 02, rattaché au manager du seed : « un autre ».
OTHER_HUNTER_ID = 2


def added(db_session: Session, row: Hunter | RealEstateManager | Client | SearchRequest | Mandate) -> int:
    db_session.add(row)
    db_session.flush()
    assert row.id is not None
    return row.id


def new_manager(db_session: Session, create_user: Callable[[str], int], email: str) -> RealEstateManager:
    manager = RealEstateManager(id_user=create_user(email), first_name="Test", last_name="PRF4", phone_number="+33600000010")
    added(db_session, manager)
    return manager


def new_hunter(db_session: Session, create_user: Callable[[str], int], email: str, manager_id: int) -> Hunter:
    hunter = Hunter(
        id_user=create_user(email), first_name="Test", last_name="PRF4", phone_number="+33600000011",
        hire_date=date(2024, 1, 2), id_realestatemanager=manager_id,
    )
    added(db_session, hunter)
    return hunter


def signed_mandate(db_session: Session, client_id: int, client_user: int, hunter_id: int, reference: str) -> int:
    request = added(db_session, SearchRequest(id_author=client_user, id_client=client_id, id_hunter=hunter_id, status="launched"))
    return added(db_session, Mandate(
        reference=reference, status="active", is_exclusive=False,
        signature_date=date(2026, 2, 1), ends_at=date(2026, 8, 1),
        id_hunter=hunter_id, id_client=client_id, id_search_request=request,
    ))


def test_hunter_and_manager_whose_ids_differ_from_accounts(
    db_client: TestClient, db_session: Session, create_user: Callable[[str], int]
):
    new_manager(db_session, create_user, "bouche-trou-manager.prf4@exemple.fr")
    manager = new_manager(db_session, create_user, "manager.prf4@exemple.fr")
    assert manager.id is not None
    new_hunter(db_session, create_user, "bouche-trou-chasseur.prf4@exemple.fr", manager.id)
    hunter = new_hunter(db_session, create_user, "chasseur.prf4@exemple.fr", manager.id)
    assert hunter.id is not None
    assert manager.id != manager.id_user and hunter.id != hunter.id_user  # sinon le test ne prouve rien
    client_user = create_user("client.prf4@exemple.fr")
    client_id = added(db_session, Client(id_user=client_user, first_name="Test", last_name="PRF4",
                                         phone_number="+33600000012", **CLIENT_ADDRESS))
    mine = signed_mandate(db_session, client_id, client_user, hunter.id, "TEST-PRF4-MOI")
    theirs = signed_mandate(db_session, client_id, client_user, OTHER_HUNTER_ID, "TEST-PRF4-AUTRE")
    # Un compte créé par POST /users attend son activation ; désactivé, son
    # profil n'est lu que par l'Admin (ADR-027, point 7).
    db_session.exec(update(User).values(is_activated=True))
    db_session.commit()

    with acting_as(HUNTER, hunter.id_user):
        mandates = {row["id"] for row in db_client.get("/mandates").json()}
        read_theirs = db_client.get(f"/mandates/{theirs}")
        estate = db_client.post("/estates", json={**ESTATE, "reference": "TEST-PRF4"})
        assert estate.status_code == 201, estate.text
        visit = db_client.post("/visits", json={
            "visit_date": "2026-02-10", "visitor_type": "hunter", "id_estate": estate.json()["id"], "id_mandate": mine,
        })
    with acting_as(MANAGER, manager.id_user):
        hunters = {row["id"] for row in db_client.get("/hunters").json()}

    assert mine in mandates and theirs not in mandates
    assert read_theirs.status_code == 404, read_theirs.text
    assert visit.status_code == 201, visit.text
    assert hunter.id in hunters and OTHER_HUNTER_ID not in hunters

    rate_parameters(db_client)
    calculation = PaymentCalculationService(
        SaleRepository(), MandateRepository(), VisitRepository(), HunterRepository(), PaymentRepository(),
        CommissionScaleRepository(), HunterRateParametersRepository(), parametrage_service(),
    )
    sale = Sale(signature_date=ACTE, purchase_amount=354712, fees_amount=Decimal("11867.80"),
                sale_origin="hunter", id_mandate=mine, id_estate=0, id_parameters_fees=0)
    assert calculation.build_vente(db_session, sale).chasseur_id == hunter.id
    assert MANAGER_ID != manager.id  # le manager du seed n'est pas celui du test
