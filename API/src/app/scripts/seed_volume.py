"""
seed_volume.py — Remplit la base de développement avec des centaines de ventes fausses.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le faker de volume (chantier FLX, fiche FLX13 ; décision de Seb, Discord,
2026-10-15, bouton faker-volume:A ; volume : question flux-18, tranchée A,
500 ventes). Avec une seule vente en base, l'OLAP (fait_ventes) et Kibana
restent vides : ce script fabrique de quoi les remplir.

Même règles que seed_demo.py (ADR-055, ADR-046) :
  - il passe par les SERVICES de l'API : chaque règle métier s'applique ;
  - Faker fr_FR à graine fixe : mêmes données à chaque base neuve ;
  - e-mails en example.com (RFC 2606), aucune personne réelle ;
  - aucun montant tiré au hasard : le prix est celui du bien, les honoraires
    sortent de calculer_honoraires, le paiement de build_payment ;
  - il refuse d'écrire dans fil_rouge_test, et aucun test ne l'appelle.

Une vente fabriquée = un client neuf, sa demande et ses critères, la
sélection de 1 à 3 biens, un mandat signé de 6 mois, les offres, 1 à 5
visites du client, l'offre acceptée au prix affiché, la vente 'hunter' et
son paiement ('announced', puis 'scheduled' et 'paid' quand ces dates sont
passées). Chasseurs et managers : une poignée, créés une fois, réutilisés.

Dates : les grilles d'honoraires, le barème et les réglages du taux ne
commencent qu'au 2026-01-01 (init-v3/05) ; une vente plus ancienne serait
refusée. Les ventes tombent donc entre SALES_FROM et la veille du
lancement ; les mandats, signés jusqu'à 175 jours avant leur vente,
remontent à l'été 2025. Aucune date dans le futur.

Les ventes s'écrivent dans l'ordre de leurs dates : le calcul d'un paiement
compte les ventes passées du chasseur (ADR-048).

Lancement, depuis docker/ (le conteneur api doit tourner) :

    docker compose exec api python -m src.app.scripts.seed_volume
    docker compose exec api python -m src.app.scripts.seed_volume --sales 100

Le mot de passe des comptes vient de DEMO_PASSWORD (docker/.env), comme le
seed de démo. Le script ne fait rien si ses comptes existent déjà : un
deuxième lancement ne double rien. Pour resemer : docker compose down -v.
Chaque service valide sa ligne : un arrêt en route laisse les ventes déjà
écrites, et le marqueur ; resemer sur une base neuve.

Les fonctions pures (add_months, plan_sales) se testent sans base :
API/tests/test_seed_volume.py.
============================================================================
"""

import argparse
import calendar
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from faker import Faker
from sqlmodel import Session, col, select

from ..conf.database import engine
from ..models import (
    Client,
    Criteria,
    Estate,
    EstateProposed,
    EstateSearchRequest,
    Hunter,
    Mandate,
    Payment,
    RealEstateManager,
    Sale,
    SearchRequest,
    User,
    UserCreate,
    Visit,
)
from ..repositories.client_repository import ClientRepository
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.criteria_repository import CriteriaRepository
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.hunter_repository import HunterRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.payment_repository import PaymentRepository
from ..repositories.real_estate_manager_repository import RealEstateManagerRepository
from ..repositories.sale_repository import SaleRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..repositories.user_repository import UserRepository
from ..repositories.visit_repository import VisitRepository
from ..services.client_service import ClientService
from ..services.criteria_service import CriteriaService
from ..services.estate_proposed_service import EstateProposedService
from ..services.estate_search_request_service import EstateSearchRequestService
from ..services.hunter_service import HunterService
from ..services.mandate_service import MandateService
from ..services.payment_calculation_service import PaymentCalculationService
from ..services.payment_service import PaymentService
from ..services.real_estate_manager_service import RealEstateManagerService
from ..services.remuneration import BaremeIntrouvable, calculer_honoraires, parametres_honoraires_applicables
from ..services.sale_service import SaleService
from ..services.search_request_service import SearchRequestService
from ..services.user_service import UserService
from ..services.visit_service import VisitService
from ..utils.exceptions import ConflictError
from .seed_demo import MIN_PASSWORD_LENGTH, TEST_DB, _next_step, _parametrage, _phone

# Graine fixe, autre que celle du seed de démo : les deux scripts ne tirent
# pas les mêmes noms.
SEED = 2027
DEFAULT_SALES = 500  # question flux-18, tranchée A par Seb le 2026-10-15
NB_MANAGERS = 2
NB_HUNTERS = 8

# Premier jour des grilles (init-v3/05) : aucune vente avant.
SALES_FROM = date(2026, 1, 1)
# Un mandat est signé 2 à 25 semaines avant sa vente : la vente tombe ainsi
# dans ses 6 mois (au moins 181 jours), sinon le paiement serait refusé
# ('mandate_expired', ADR-024).
MANDATE_LEAD_DAYS = (14, 175)
NB_PROPOSED = (1, 3)  # biens proposés par mandat, le vendu compris
NB_CLIENT_VISITS = (1, 5)
SCHEDULED_AFTER_DAYS = 15  # virement prévu 15 jours après l'acte
PAID_AFTER_DAYS = 25  # et fait 10 jours plus tard
# Un bien à moins de 50 000 € peut avoir des honoraires plus grands que son
# prix (part fixe de 3 000 € et plus) : chk_fees_lower_than_price.
MIN_PRICE = 50_000

MARKER_EMAIL = "volume-manager-1@example.com"


@dataclass(frozen=True)
class SalePlan:
    """Une vente à fabriquer : ses biens, ses dates, rien d'écrit encore."""

    number: int  # 1, 2, ... dans l'ordre des dates de vente
    hunter_index: int
    sold_estate_id: int
    other_estate_ids: tuple[int, ...]
    mandate_signed: date
    mandate_ends: date
    is_exclusive: bool
    visit_dates: tuple[date, ...]
    sale_date: date


def add_months(day: date, months: int) -> date:
    """
    day + months mois, ramené au dernier jour du mois s'il n'existe pas —
    comme `date + INTERVAL 'n months'` de PostgreSQL (chk_mandate_six_months) :
    le 31/08 + 6 mois donne le 28 ou 29/02.
    """
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _random_day(rng: random.Random, first: date, last: date) -> date:
    return first + timedelta(days=rng.randint(0, (last - first).days))


def plan_sales(rng: random.Random, n: int, estate_ids: list[int], today: date) -> list[SalePlan]:
    """
    Les n ventes, triées par date. Chaque bien vendu est pris une seule fois
    dans estate_ids (uq_sale_estate) ; les autres biens proposés viennent du
    même stock, sans être retirés. Ventes entre SALES_FROM et la veille de
    today ; mandat, visites et vente toujours dans cet ordre.
    """
    if n > len(estate_ids):
        raise ValueError(f"{n} ventes demandées, {len(estate_ids)} biens à vendre : un bien ne se vend qu'une fois.")
    last_sale = today - timedelta(days=1)
    if last_sale < SALES_FROM:
        raise ValueError(f"Aucune vente possible avant {SALES_FROM} : les grilles commencent ce jour-là.")

    to_sell = rng.sample(estate_ids, n)
    drafts: list[tuple[date, SalePlan]] = []
    for i, sold in enumerate(to_sell):
        sale_date = _random_day(rng, SALES_FROM, last_sale)
        signed = sale_date - timedelta(days=rng.randint(*MANDATE_LEAD_DAYS))
        nb_others = rng.randint(*NB_PROPOSED) - 1
        # Un tirage de plus, au cas où il retomberait sur le bien vendu.
        others = tuple(e for e in rng.sample(estate_ids, nb_others + 1) if e != sold)[:nb_others]
        visits = tuple(sorted(_random_day(rng, signed, sale_date) for _ in range(rng.randint(*NB_CLIENT_VISITS))))
        drafts.append(
            (
                sale_date,
                SalePlan(
                    number=0,
                    hunter_index=i % NB_HUNTERS,
                    sold_estate_id=sold,
                    other_estate_ids=others,
                    mandate_signed=signed,
                    mandate_ends=add_months(signed, 6),
                    is_exclusive=rng.random() < 0.5,
                    visit_dates=visits,
                    sale_date=sale_date,
                ),
            )
        )
    drafts.sort(key=lambda d: (d[0], d[1].sold_estate_id))
    return [
        SalePlan(**{**plan.__dict__, "number": number}) for number, (_, plan) in enumerate(drafts, start=1)
    ]


def make_faker() -> Faker:
    """Faker français, à graine fixe (la sienne)."""
    fake = Faker("fr_FR")
    fake.seed_instance(SEED)
    return fake


def already_seeded(session: Session) -> bool:
    """Vrai si le premier manager du faker existe déjà."""
    return UserRepository().find_by_email_ignoring_case(session, MARKER_EMAIL) is not None


def _account(session: Session, email: str, password: str) -> User:
    return UserService(UserRepository()).create(session, UserCreate(email=email, password=password, is_activated=True))


def seed_staff(session: Session, fake: Faker, password: str) -> list[Hunter]:
    """Les managers et les chasseurs du faker, chaque chasseur rattaché à un manager."""
    managers: list[RealEstateManager] = []
    for i in range(1, NB_MANAGERS + 1):
        user = _account(session, f"volume-manager-{i}@example.com", password)
        assert user.id is not None
        managers.append(
            RealEstateManagerService(RealEstateManagerRepository()).create(
                session,
                RealEstateManager(
                    id_user=user.id,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    phone_number=_phone(fake),
                    country_iso="FR",
                    company_name=fake.company(),
                ),
            )
        )
    hunters: list[Hunter] = []
    for i in range(1, NB_HUNTERS + 1):
        user = _account(session, f"volume-chasseur-{i}@example.com", password)
        manager = managers[i % NB_MANAGERS]
        assert user.id is not None and manager.id is not None
        hunters.append(
            HunterService(HunterRepository()).create(
                session,
                Hunter(
                    id_user=user.id,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    phone_number=_phone(fake),
                    country_iso="FR",
                    # Anciennetés de 0 à 13 ans : la majoration d'ancienneté varie.
                    hire_date=fake.date_between_dates(date(2012, 1, 1), date(2025, 6, 30)),
                    is_carte_t=fake.boolean(chance_of_getting_true=80),
                    is_hunter_ai=i % 4 == 0,  # deux chasseurs IA sur huit
                    id_realestatemanager=manager.id,
                ),
            )
        )
    return hunters


def estates_for_sale(session: Session) -> dict[int, Estate]:
    """Les biens jamais vendus, au prix connu et assez haut ; par id."""
    sold = select(Sale.id_estate)
    rows = session.exec(
        select(Estate)
        .where(col(Estate.price) >= MIN_PRICE)
        .where(col(Estate.id).not_in(sold))
        .order_by(col(Estate.id))
    ).all()
    return {e.id: e for e in rows if e.id is not None}


@dataclass
class Services:
    """Les services, construits une fois."""

    requests: SearchRequestService
    criteria: CriteriaService
    selections: EstateSearchRequestService
    mandates: MandateService
    offers: EstateProposedService
    visits: VisitService
    sales: SaleService
    calculation: PaymentCalculationService
    payments: PaymentService

    @classmethod
    def build(cls) -> "Services":
        calculation = PaymentCalculationService(
            SaleRepository(),
            MandateRepository(),
            VisitRepository(),
            HunterRepository(),
            PaymentRepository(),
            CommissionScaleRepository(),
            HunterRateParametersRepository(),
            _parametrage(),
        )
        return cls(
            requests=SearchRequestService(SearchRequestRepository()),
            criteria=CriteriaService(CriteriaRepository()),
            selections=EstateSearchRequestService(EstateSearchRequestRepository()),
            mandates=MandateService(MandateRepository(), SearchRequestRepository()),
            offers=EstateProposedService(EstateProposedRepository(), MandateRepository(), EstateSearchRequestRepository()),
            visits=VisitService(VisitRepository(), MandateRepository(), EstateProposedRepository()),
            sales=SaleService(SaleRepository(), MandateRepository(), EstateProposedRepository(), ParametersFeesRepository()),
            calculation=calculation,
            payments=PaymentService(
                PaymentRepository(), HunterRateParametersRepository(), calculation, HunterPerformanceRepository()
            ),
        )


def seed_client(session: Session, fake: Faker, number: int, password: str) -> Client:
    """Un client neuf par vente : un mandat exclusif bloque son client 6 mois (U02)."""
    user = _account(session, f"volume-client-{number:04d}@example.com", password)
    assert user.id is not None
    return ClientService(ClientRepository()).create(
        session,
        Client(
            id_user=user.id,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            phone_number=_phone(fake),
            country_iso="FR",
            address=fake.street_address(),
            postal_code=fake.postcode(),
            town=fake.city(),
            birth_date=fake.date_between_dates(date(1960, 1, 1), date(2000, 12, 31)),
        ),
    )


def seed_one_sale(
    session: Session,
    fake: Faker,
    svc: Services,
    plan: SalePlan,
    hunter: Hunter,
    estates: dict[int, Estate],
    password: str,
    now: datetime,
) -> Payment:
    """Une vente du plan, de la demande au paiement, par les services."""
    client = seed_client(session, fake, plan.number, password)
    sold = estates[plan.sold_estate_id]
    assert client.id is not None and hunter.id is not None and sold.price is not None
    request = svc.requests.create(
        session,
        SearchRequest(
            id_author=client.id_user,
            id_client=client.id,
            id_hunter=hunter.id,
            id_realestatemanager=hunter.id_realestatemanager,
            status="accepted",
        ),
    )
    assert request.id is not None
    svc.criteria.create(
        session,
        Criteria(
            id_author=client.id_user,
            id_search_request=request.id,
            country_iso="FR",
            estate_type=sold.estate_type,
            # Le budget encadre le prix du bien vendu : -20 % à +10 %.
            budget_min=sold.price * 8 // 10,
            budget_max=sold.price * 11 // 10,
        ),
    )
    proposed_ids = (plan.sold_estate_id, *plan.other_estate_ids)
    for estate_id in proposed_ids:
        svc.selections.create(
            session, EstateSearchRequest(id_estate=estate_id, id_search_request=request.id, id_hunter=hunter.id)
        )
    mandate = svc.mandates.create(
        session,
        Mandate(
            reference=f"VOL-M-{plan.number:05d}",
            status="active",
            signature_date=plan.mandate_signed,
            signature_type="electronic",
            ends_at=plan.mandate_ends,
            is_exclusive=plan.is_exclusive,
            id_hunter=hunter.id,
            id_client=client.id,
            id_search_request=request.id,
        ),
    )
    assert mandate.id is not None
    offers = [
        svc.offers.create(
            session,
            EstateProposed(
                proposition_status="proposed",
                comment_hunter=fake.sentence(nb_words=8),
                client_priority=priority,
                id_hunter=hunter.id,
                id_estate=estate_id,
                id_mandate=mandate.id,
            ),
        )
        for priority, estate_id in enumerate(proposed_ids, start=1)
    ]
    for k, visit_date in enumerate(plan.visit_dates):
        svc.visits.create(
            session,
            Visit(
                visit_date=visit_date,
                visitor_type="client",
                id_estate=proposed_ids[k % len(proposed_ids)],
                id_mandate=mandate.id,
            ),
        )

    # L'offre sur le bien vendu, acceptée au prix affiché, puis la vente (P27).
    offer = offers[0]
    assert offer.id is not None
    accepted = EstateProposed(**offer.model_dump(exclude={"id"}))
    accepted.proposition_status, accepted.amount_proposition = "accepted", sold.price
    svc.offers.replace(session, offer.id, accepted)

    grid = ParametersFeesRepository().in_force_at(session, plan.sale_date)
    parametrage = _parametrage().charger(session, plan.sale_date)
    fees = calculer_honoraires(Decimal(sold.price), parametres_honoraires_applicables(parametrage, plan.sale_date))
    assert grid is not None and grid.id is not None
    sale = svc.sales.create(
        session,
        Sale(
            signature_date=plan.sale_date,
            purchase_amount=sold.price,
            fees_amount=fees,
            sale_origin="hunter",
            id_mandate=mandate.id,
            id_estate=plan.sold_estate_id,
            id_parameters_fees=grid.id,
        ),
    )
    assert sale.id is not None

    # Le paiement calculé ; un refus ('refused', ADR-024) est gardé tel quel.
    payment = svc.payments.create(session, svc.calculation.build_payment(session, sale.id))
    assert payment.id is not None
    if payment.status != "announced":
        return payment
    scheduled_for = plan.sale_date + timedelta(days=SCHEDULED_AFTER_DAYS)
    paid_at = datetime.combine(plan.sale_date + timedelta(days=PAID_AFTER_DAYS), time(10, 0), tzinfo=timezone.utc)
    if scheduled_for > now.date():
        return payment
    payment = svc.payments.replace(
        session, payment.id, _next_step(payment, status="scheduled", scheduled_for=scheduled_for)
    )
    if paid_at > now:
        return payment
    return svc.payments.replace(session, payment.id, _next_step(payment, status="paid", paid_at=paid_at))  # pyright: ignore[reportArgumentType] -- id lu en base juste au-dessus


def seed(session: Session, password: str, nb_sales: int, today: date) -> dict[str, int] | None:
    """Toutes les ventes du plan ; None, sans rien écrire, si la base est déjà semée."""
    if already_seeded(session):
        return None
    estates = estates_for_sale(session)
    plans = plan_sales(random.Random(SEED), nb_sales, sorted(estates), today)
    fake = make_faker()
    hunters = seed_staff(session, fake, password)
    svc = Services.build()
    now = datetime.now(timezone.utc)
    statuses: dict[str, int] = {}
    for plan in plans:
        payment = seed_one_sale(session, fake, svc, plan, hunters[plan.hunter_index], estates, password, now)
        statuses[payment.status] = statuses.get(payment.status, 0) + 1
        if plan.number % 50 == 0:
            print(f"… {plan.number}/{len(plans)} ventes", flush=True)
    return statuses


def main() -> None:
    """Contrôle l'environnement, puis fabrique les ventes."""
    parser = argparse.ArgumentParser(description="Fabrique des ventes fausses dans la base de développement.")
    parser.add_argument("--sales", type=int, default=DEFAULT_SALES, help=f"nombre de ventes (défaut : {DEFAULT_SALES})")
    args = parser.parse_args()

    password = os.getenv("DEMO_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"❌ DEMO_PASSWORD absent ou trop court ({MIN_PASSWORD_LENGTH} caractères au moins) : "
            "l'ajouter à docker/.env, puis `docker compose up -d`. Rien n'est écrit."
        )
    if TEST_DB in (os.getenv("POSTGRES_DB"), engine.url.database):
        raise SystemExit(f"❌ Refusé : le faker n'écrit jamais dans la base de test {TEST_DB}. Rien n'est écrit.")

    with Session(engine) as session:
        try:
            statuses = seed(session, password, args.sales, date.today())
        except (ConflictError, BaremeIntrouvable, ValueError) as exc:
            raise SystemExit(f"❌ Arrêt du faker ({exc}).") from exc

    if statuses is None:
        print(f"ℹ️ Le faker a déjà tourné sur cette base ({MARKER_EMAIL} existe) : rien n'est écrit.")
        return
    print(f"✅ {sum(statuses.values())} ventes écrites ; paiements par statut : {statuses}")


if __name__ == "__main__":
    main()
