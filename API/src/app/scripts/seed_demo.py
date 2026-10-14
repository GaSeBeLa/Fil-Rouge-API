"""
seed_demo.py — Remplit la base de développement avec un parcours de démo.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le seed est le décor, les tests sont la preuve : aucun test ne dépend de
ce script, et il n'écrit jamais dans la base de test `fil_rouge_test`.
Décisions du chantier DEM (Discord, 2026-10-14 ; Fil-Rouge,
`context AI/15-seed-demo.md`) : un script qui appelle les services (Q2),
Faker `fr_FR` à graine fixe (Q3), un compte neuf par rôle sauf Admin (Q4).

Lancement, depuis `docker/` (le conteneur `api` doit tourner) :

    docker compose exec api python -m src.app.scripts.seed_demo

Le mot de passe des comptes de démo vient de `DEMO_PASSWORD`, dans
`docker/.env` (12 caractères au moins). Il n'est ni affiché, ni écrit
ailleurs qu'en base, haché (`UserService.create`, ADR-016).

Le script s'arrête sans rien écrire si un compte de démo existe déjà : on
ne sème qu'une fois par base. Pour resemer : `docker compose down -v`, puis
`up -d` (efface la base de dev locale).

Une étape = une fonction `seed_<étape>(session, ...)` ; `seed()` les
enchaîne. Les fiches DEM2 et DEM3 y ajoutent les leurs. Un refus de la base
ou d'une règle (ConflictError) arrête le script avec son message : on
corrige les données du seed, jamais la règle.

Domaine des emails : `example.com`, réservé à la documentation (RFC 2606).
Le domaine `.invalid` est refusé par la validation de `UserCreate`
(email-validator rejette les noms à usage spécial).
============================================================================
"""

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import NamedTuple

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
    ReviewMedia,
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
from ..repositories.review_media_repository import ReviewMediaRepository
from ..repositories.role_repository import RoleRepository
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
from ..services.parametrage_service import ParametrageService
from ..services.payment_calculation_service import PaymentCalculationService
from ..services.payment_service import PaymentService
from ..services.real_estate_manager_service import RealEstateManagerService
from ..services.remuneration import BaremeIntrouvable, calculer_honoraires, parametres_honoraires_applicables
from ..services.review_media_service import ReviewMediaService
from ..services.sale_service import SaleService
from ..services.search_request_service import SearchRequestService
from ..services.user_service import UserService
from ..services.visit_service import VisitService
from ..utils.exceptions import ConflictError
from ..utils.roles import CLIENT, HUNTER, MANAGER, READER

# Graine fixe (Q3) : mêmes données à chaque lancement.
SEED = 2026
MIN_PASSWORD_LENGTH = 12
TEST_DB = "fil_rouge_test"

# Un compte par rôle, sauf Admin (Q4).
DEMO_EMAILS: dict[str, str] = {
    CLIENT: "demo-client@example.com",
    HUNTER: "demo-chasseur@example.com",
    MANAGER: "demo-manager@example.com",
    READER: "demo-lecteur@example.com",
}

# Dates fixes : aucune date tirée du jour (Q3).
HIRE_DATE = date(2023, 9, 1)
BIRTH_RANGE = (date(1960, 1, 1), date(2000, 12, 31))
# Mandat de 6 mois exactement (CHECK chk_mandate_six_months, Q-MAN-01). Toutes
# ses dates sont passées : une visite ne peut dépasser le lendemain (CHECK de visit).
MANDATE_SIGNED = date(2026, 3, 2)
MANDATE_ENDS = date(2026, 9, 2)
MANDATE_REFERENCE = "DEMO-M-0001"

# Ce que cherche le client de démo ; les biens retenus sont pris parmi ceux de
# la base qui y répondent (type et prix), dans l'ordre des id.
WANTED_TYPE = "Maison"
BUDGET_MIN, BUDGET_MAX = 100_000, 250_000  # en euros
NB_ESTATES = 3  # sélectionnés, puis tous proposés
NB_CLIENT_VISITS = 2  # sur les biens proposés (P23), plus une visite du chasseur seul
VISITS_UNTIL = date(2026, 6, 30)  # toutes avant l'acte : elles comptent dans le calcul (ADR-048 point 4)

# Vente du premier bien proposé, au prix affiché, puis son paiement pas à pas
# (ADR-038). Les montants sortent du calcul, jamais d'une constante (Q3).
SALE_SIGNED = date(2026, 7, 15)
PAYMENT_SCHEDULED_FOR = date(2026, 8, 1)
PAYMENT_PAID_AT = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
REVIEW_MEDIA_URL = "https://example.com/demo/visite-maison.mp4"


class DemoProfiles(NamedTuple):
    client: Client
    hunter: Hunter
    manager: RealEstateManager


class DemoRequest(NamedTuple):
    request: SearchRequest
    criteria: Criteria
    estates: list[Estate]
    mandate: Mandate
    proposals: list[EstateProposed]
    visits: list[Visit]


def make_faker() -> Faker:
    """Faker français, à graine fixe."""
    fake = Faker("fr_FR")
    fake.seed_instance(SEED)
    return fake


def _phone(fake: Faker) -> str:
    """Un portable français au format du CHECK de la base (`+33 6 12 34 56 78`)."""
    return "+33 6 " + fake.numerify("## ## ## ##")


def already_seeded(session: Session) -> bool:
    """Vrai si l'un des comptes de démo existe déjà, aux majuscules près."""
    users = UserRepository()
    return any(users.find_by_email_ignoring_case(session, email) is not None for email in DEMO_EMAILS.values())


def seed_accounts(session: Session, password: str) -> dict[str, User]:
    """Étape 1 : les 4 comptes de démo, activés, un par rôle."""
    roles = RoleRepository()
    service = UserService(UserRepository())
    accounts: dict[str, User] = {}
    for wording, email in DEMO_EMAILS.items():
        role = roles.get_by_wording(session, wording)
        if role is None or role.id is None:
            raise SystemExit(f"❌ Le rôle '{wording}' manque dans la table role : la base est-elle initialisée ?")
        item = UserCreate(email=email, password=password, is_activated=True, id_role=role.id)
        accounts[wording] = service.create(session, item)
    return accounts


def seed_profiles(session: Session, fake: Faker, accounts: dict[str, User]) -> DemoProfiles:
    """Étape 2 : les profils client, manager, et chasseur rattaché au manager de démo."""
    manager_user, hunter_user, client_user = accounts[MANAGER], accounts[HUNTER], accounts[CLIENT]
    assert manager_user.id is not None and hunter_user.id is not None and client_user.id is not None

    manager = RealEstateManagerService(RealEstateManagerRepository()).create(
        session,
        RealEstateManager(
            id_user=manager_user.id,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            phone_number=_phone(fake),
            country_iso="FR",
            company_name=fake.company(),
        ),
    )
    hunter = HunterService(HunterRepository()).create(
        session,
        Hunter(
            id_user=hunter_user.id,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            phone_number=_phone(fake),
            country_iso="FR",
            hire_date=HIRE_DATE,
            is_carte_t=True,
            id_realestatemanager=manager_user.id,
        ),
    )
    client = ClientService(ClientRepository()).create(
        session,
        Client(
            id_user=client_user.id,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            phone_number=_phone(fake),
            country_iso="FR",
            address=fake.street_address(),
            postal_code=fake.postcode(),
            town=fake.city(),
            birth_date=fake.date_between_dates(*BIRTH_RANGE),
        ),
    )
    return DemoProfiles(client=client, hunter=hunter, manager=manager)


def seed_request(session: Session, profiles: DemoProfiles) -> tuple[SearchRequest, Criteria]:
    """Étape 3 : la demande du client, déjà acceptée par le chasseur de démo, et ses critères."""
    request = SearchRequestService(SearchRequestRepository()).create(
        session,
        SearchRequest(
            id_author=profiles.client.id_user,
            id_client=profiles.client.id_user,
            id_hunter=profiles.hunter.id_user,
            id_realestatemanager=profiles.manager.id_user,
            status="accepted",
        ),
    )
    assert request.id is not None
    criteria = CriteriaService(CriteriaRepository()).create(
        session,
        Criteria(
            id_author=profiles.client.id_user,
            id_search_request=request.id,
            country_iso="FR",
            estate_type=WANTED_TYPE,
            budget_min=BUDGET_MIN,
            budget_max=BUDGET_MAX,
            rooms_min=3,
            has_garden=True,
        ),
    )
    return request, criteria


def seed_selection(session: Session, profiles: DemoProfiles, request: SearchRequest) -> list[Estate]:
    """Étape 4 : le chasseur met dans la sélection de la demande les premiers biens qui y répondent."""
    estates = list(
        session.exec(
            select(Estate)
            .where(Estate.estate_type == WANTED_TYPE)
            .where(col(Estate.price).between(BUDGET_MIN, BUDGET_MAX))
            .order_by(col(Estate.id))
            .limit(NB_ESTATES)
        ).all()
    )
    if len(estates) < NB_ESTATES:
        raise SystemExit(
            f"❌ {len(estates)} bien(s) de type {WANTED_TYPE} entre {BUDGET_MIN} et {BUDGET_MAX} € : "
            f"il en faut {NB_ESTATES}. La base a-t-elle ses biens (init-v3/02) ?"
        )
    selections = EstateSearchRequestService(EstateSearchRequestRepository())
    assert request.id is not None
    for estate in estates:
        assert estate.id is not None
        selections.create(
            session,
            EstateSearchRequest(id_estate=estate.id, id_search_request=request.id, id_hunter=profiles.hunter.id_user),
        )
    return estates


def seed_mandate(session: Session, profiles: DemoProfiles, request: SearchRequest) -> Mandate:
    """Étape 5 : le mandat signé ; MandateService passe la demande à `launched`."""
    assert request.id is not None
    return MandateService(MandateRepository(), SearchRequestRepository()).create(
        session,
        Mandate(
            reference=MANDATE_REFERENCE,
            status="active",
            signature_date=MANDATE_SIGNED,
            signature_type="electronic",
            ends_at=MANDATE_ENDS,
            is_exclusive=True,
            id_hunter=profiles.hunter.id_user,
            id_client=profiles.client.id_user,
            id_search_request=request.id,
        ),
    )


def seed_proposals(
    session: Session, fake: Faker, profiles: DemoProfiles, mandate: Mandate, estates: list[Estate]
) -> list[EstateProposed]:
    """Étape 6 : chaque bien de la sélection est proposé sur le mandat (P19, P20)."""
    service = EstateProposedService(EstateProposedRepository(), MandateRepository(), EstateSearchRequestRepository())
    assert mandate.id is not None
    proposals: list[EstateProposed] = []
    for priority, estate in enumerate(estates, start=1):
        assert estate.id is not None
        proposals.append(
            service.create(
                session,
                EstateProposed(
                    proposition_status="proposed",
                    comment_hunter=fake.sentence(nb_words=10),
                    client_priority=priority,
                    id_hunter=profiles.hunter.id_user,
                    id_estate=estate.id,
                    id_mandate=mandate.id,
                ),
            )
        )
    return proposals


def seed_visits(session: Session, fake: Faker, mandate: Mandate, proposals: list[EstateProposed]) -> list[Visit]:
    """Étape 7 : visites dans les dates du mandat (P25, ADR-044) ; celles du client, sur des biens proposés (P23)."""
    service = VisitService(VisitRepository(), MandateRepository(), EstateProposedRepository())
    assert mandate.id is not None
    planned = [(proposal.id_estate, "client") for proposal in proposals[:NB_CLIENT_VISITS]]
    planned.append((proposals[-1].id_estate, "hunter"))
    return [
        service.create(
            session,
            Visit(
                visit_date=fake.date_between_dates(MANDATE_SIGNED, VISITS_UNTIL),
                visitor_type=visitor_type,
                id_estate=estate_id,
                id_mandate=mandate.id,
            ),
        )
        for estate_id, visitor_type in planned
    ]


def seed_until_visits(session: Session, fake: Faker, profiles: DemoProfiles) -> DemoRequest:
    """Étapes 3 à 7 : de la demande du client jusqu'aux visites."""
    request, criteria = seed_request(session, profiles)
    estates = seed_selection(session, profiles, request)
    mandate = seed_mandate(session, profiles, request)
    proposals = seed_proposals(session, fake, profiles, mandate, estates)
    visits = seed_visits(session, fake, mandate, proposals)
    session.refresh(request)  # le statut `launched` posé par MandateService
    return DemoRequest(request, criteria, estates, mandate, proposals, visits)


def _parametrage() -> ParametrageService:
    return ParametrageService(ParametersFeesRepository(), CommissionScaleRepository(), HunterRateParametersRepository())


def seed_sale(session: Session, demo: DemoRequest) -> Sale:
    """Étape 8 : le client accepte une offre au prix affiché, puis la vente 'hunter' (P27, ADR-030)."""
    offer, estate = demo.proposals[0], demo.estates[0]
    assert offer.id is not None and estate.id is not None and estate.price is not None
    assert demo.mandate.id is not None
    offers = EstateProposedService(EstateProposedRepository(), MandateRepository(), EstateSearchRequestRepository())
    accepted = EstateProposed(**offer.model_dump(exclude={"id"}))
    accepted.proposition_status, accepted.amount_proposition = "accepted", estate.price
    offers.replace(session, offer.id, accepted)

    grid = ParametersFeesRepository().in_force_at(session, SALE_SIGNED)
    try:
        parametrage = _parametrage().charger(session, SALE_SIGNED)
        fees = calculer_honoraires(Decimal(estate.price), parametres_honoraires_applicables(parametrage, SALE_SIGNED))
    except BaremeIntrouvable as exc:
        raise SystemExit(f"❌ Paramétrage manquant ({exc}) : la base a-t-elle init-v3/05_parametres.sql ?") from exc
    assert grid is not None and grid.id is not None  # charger() a trouvé une grille à cette date

    return SaleService(SaleRepository(), MandateRepository(), EstateProposedRepository(), ParametersFeesRepository()).create(
        session,
        Sale(
            signature_date=SALE_SIGNED,
            purchase_amount=estate.price,
            fees_amount=fees,
            sale_origin="hunter",
            id_mandate=demo.mandate.id,
            id_estate=estate.id,
            id_parameters_fees=grid.id,
        ),
    )


def _next_step(payment: Payment, **changes: object) -> Payment:
    """Le même paiement, un pas plus loin (ADR-038 : PaymentService.replace)."""
    data = Payment(**payment.model_dump(exclude={"id"}))
    for field, value in changes.items():
        setattr(data, field, value)
    return data


def seed_payment(session: Session, sale: Sale) -> Payment:
    """
    Étape 9 : le paiement calculé par build_payment, puis 'announced' ->
    'scheduled' -> 'paid' ; au passage à 'paid', PaymentService écrit la note
    du chasseur (hunter_performance, ADR-035). Un refus arrête le script.
    """
    assert sale.id is not None
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
    built = calculation.build_payment(session, sale.id)
    if built.status != "announced":
        raise SystemExit(f"❌ Le calcul refuse le paiement de la vente {sale.id} : {built.refusal_reason}.")
    payments = PaymentService(
        PaymentRepository(), HunterRateParametersRepository(), calculation, HunterPerformanceRepository()
    )
    payment = payments.create(session, built)
    assert payment.id is not None
    payment = payments.replace(
        session, payment.id, _next_step(payment, status="scheduled", scheduled_for=PAYMENT_SCHEDULED_FOR)
    )
    return payments.replace(session, payment.id, _next_step(payment, status="paid", paid_at=PAYMENT_PAID_AT))  # pyright: ignore[reportArgumentType] -- id lu en base juste au-dessus


def seed_review(
    session: Session, fake: Faker, accounts: dict[str, User], demo: DemoRequest
) -> ReviewMedia:
    """
    Étape 10 : l'avis sur le bien vendu. En base, l'avis est la note du
    chasseur sur la sélection (`review_hunter`), et seul ce chasseur y ajoute
    un média (ADR-051) : le client n'a pas d'avis à lui.
    """
    selections = EstateSearchRequestRepository()
    [selection] = selections.list_where(
        session, id_search_request=demo.request.id, id_estate=demo.estates[0].id
    )
    assert selection.id is not None
    reviewed = EstateSearchRequest(**selection.model_dump(exclude={"id"}))
    reviewed.review_hunter = fake.paragraph(nb_sentences=3)
    EstateSearchRequestService(selections).replace(session, selection.id, reviewed)

    return ReviewMediaService(ReviewMediaRepository(), selections).create(
        session,
        ReviewMedia(media_url=REVIEW_MEDIA_URL, media_type="video", id_estate_searchrequest=selection.id),
        actor=accounts[HUNTER],
    )


def seed(session: Session, password: str) -> bool:
    """Enchaîne les étapes ; False, sans rien écrire, si la base est déjà semée."""
    if already_seeded(session):
        return False
    fake = make_faker()
    accounts = seed_accounts(session, password)
    profiles = seed_profiles(session, fake, accounts)
    demo = seed_until_visits(session, fake, profiles)
    sale = seed_sale(session, demo)
    seed_payment(session, sale)
    seed_review(session, fake, accounts, demo)
    return True


def main() -> None:
    """Contrôle l'environnement, puis sème la base de développement."""
    password = os.getenv("DEMO_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"❌ DEMO_PASSWORD absent ou trop court ({MIN_PASSWORD_LENGTH} caractères au moins) : "
            "l'ajouter à docker/.env, puis `docker compose up -d`. Rien n'est écrit."
        )
    if TEST_DB in (os.getenv("POSTGRES_DB"), engine.url.database):
        raise SystemExit(f"❌ Refusé : le seed n'écrit jamais dans la base de test {TEST_DB}. Rien n'est écrit.")

    with Session(engine) as session:
        try:
            done = seed(session, password)
        except ConflictError as exc:
            raise SystemExit(f"❌ La base refuse le seed ({exc}).") from exc

    if not done:
        print("ℹ️ Les comptes de démo existent déjà : rien n'est écrit.")
        return
    print("✅ Comptes de démo créés :", ", ".join(DEMO_EMAILS.values()))
    print("➡️ Mot de passe : celui de DEMO_PASSWORD. Connexion : POST /auth/login, http://localhost:8000/docs")


if __name__ == "__main__":
    main()
