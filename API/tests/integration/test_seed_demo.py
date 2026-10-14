"""
test_seed_demo.py — Le script de démo (chantier DEM, fiches DEM1 et DEM2).

Les étapes du script tournent sur `db_session` (transaction annulée) :
rien n'est écrit pour de vrai. `main()` n'est appelé que pour ses refus,
avant toute connexion.

La base de test n'a aucun bien (`estate`) ni paramétrage : la fixture
`demo_estates` pose quelques biens qui répondent aux critères de démo, et
`seeded` rejoue `init-v3/05_parametres.sql` (celui de la base de dev), tout
dans la transaction.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from sqlmodel import Session, col, select

from src.app.models import (
    Client,
    Estate,
    EstateProposed,
    EstateSearchRequest,
    Hunter,
    HunterPerformance,
    Mandate,
    Payment,
    RealEstateManager,
    ReviewMedia,
    Role,
    Sale,
    SearchRequest,
    User,
    Visit,
)
from src.app.repositories.commission_scale_repository import CommissionScaleRepository
from src.app.repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from src.app.repositories.hunter_repository import HunterRepository
from src.app.repositories.payment_repository import PaymentRepository
from src.app.repositories.sale_repository import SaleRepository
from src.app.repositories.estate_repository import EstateRepository
from src.app.repositories.mandate_repository import MandateRepository
from src.app.repositories.visit_repository import VisitRepository
from src.app.repositories.estate_proposed_repository import EstateProposedRepository
from src.app.scripts import seed_demo
from src.app.services.payment_calculation_service import PaymentCalculationService
from src.app.services.remuneration import calculer_remuneration
from src.app.services.visit_service import VisitService
from src.app.utils.roles import CLIENT, HUNTER, MANAGER, READER, Principal

DEMO_PASSWORD = "mot-de-passe-de-demo"
# Mandat actif posé par 02 (chasseur 1, du 2026-03-25 au 2026-09-25) : une visite d'un autre client.
OTHER_MANDATE = 15


@pytest.fixture
def demo_estates(db_session: Session) -> list[Estate]:
    """Des maisons dans le budget de démo, plus une hors budget que le seed doit laisser."""
    repository = EstateRepository()
    prices = [seed_demo.BUDGET_MIN, 180_000, seed_demo.BUDGET_MAX, seed_demo.BUDGET_MAX + 1]
    return [
        repository.create(
            db_session,
            Estate(
                reference=f"TEST-DEMO-{n}",
                estate_type=seed_demo.WANTED_TYPE,
                surface=Decimal("120.50"),
                town="Toulouse",
                price=price,
            ),
        )
        for n, price in enumerate(prices)
    ]


# Le paramétrage de la base de dev : monté dans le conteneur api (BAN2), ou lu dans le dépôt sur la machine.
PARAMETERS_SQL = [
    Path("/api/sql/init-v3/05_parametres.sql"),
    Path(__file__).resolve().parents[3] / "docker" / "init-v3" / "05_parametres.sql",
]


def apply_parameters(db_session: Session) -> None:
    """Rejoue 05_parametres.sql par le curseur du pilote (ses `%` ne sont pas des paramètres)."""
    found = [path for path in PARAMETERS_SQL if path.exists()]
    if not found:
        pytest.skip(f"05_parametres.sql introuvable ({', '.join(map(str, PARAMETERS_SQL))}).")
    db_session.connection().connection.cursor().execute(found[0].read_text(encoding="utf-8"))


@pytest.fixture
def seeded(db_session: Session, fast_hasher: PasswordHasher, demo_estates: list[Estate]) -> Session:
    apply_parameters(db_session)
    assert seed_demo.seed(db_session, DEMO_PASSWORD) is True
    return db_session


def _demo_users(session: Session) -> list[User]:
    emails = list(seed_demo.DEMO_EMAILS.values())
    return list(session.exec(select(User).where(col(User.email).in_(emails))).all())


def _demo_user(session: Session, role: str) -> User:
    return session.exec(select(User).where(User.email == seed_demo.DEMO_EMAILS[role])).one()


def _demo_mandate(session: Session) -> Mandate:
    return session.exec(select(Mandate).where(Mandate.reference == seed_demo.MANDATE_REFERENCE)).one()


def test_seed_creates_four_activated_accounts_one_per_role(seeded: Session) -> None:
    db_session = seeded

    users = _demo_users(db_session)
    assert len(users) == 4
    assert all(user.is_activated for user in users)
    roles = {db_session.get(Role, user.id_role).wording for user in users}  # pyright: ignore[reportOptionalMemberAccess] -- FK NOT NULL
    assert roles == {CLIENT, HUNTER, MANAGER, READER}


def test_seed_creates_profiles_hunter_under_demo_manager(seeded: Session) -> None:
    db_session = seeded
    by_email = {user.email: user for user in _demo_users(db_session)}
    manager_id = by_email[seed_demo.DEMO_EMAILS[MANAGER]].id

    hunter = db_session.exec(select(Hunter).where(Hunter.id_user == by_email[seed_demo.DEMO_EMAILS[HUNTER]].id)).one()
    assert hunter.id_realestatemanager == manager_id
    assert db_session.exec(select(RealEstateManager).where(RealEstateManager.id_user == manager_id)).one()
    assert db_session.exec(select(Client).where(Client.id_user == by_email[seed_demo.DEMO_EMAILS[CLIENT]].id)).one()


def test_second_seed_writes_nothing(seeded: Session) -> None:
    db_session = seeded
    users_before = len(db_session.exec(select(User)).all())
    visits_before = len(db_session.exec(select(Visit)).all())

    assert seed_demo.seed(db_session, DEMO_PASSWORD) is False
    assert len(db_session.exec(select(User)).all()) == users_before
    assert len(db_session.exec(select(Visit)).all()) == visits_before


# --- DEM2 : de la demande aux visites ---------------------------------------------


def test_demo_request_is_launched_by_the_signed_mandate(seeded: Session) -> None:
    mandate = _demo_mandate(seeded)
    request = seeded.get(SearchRequest, mandate.id_search_request)
    assert request is not None
    assert request.status == "launched"
    assert request.id_client == _demo_user(seeded, CLIENT).id


def test_seed_selects_and_proposes_estates_within_budget(seeded: Session, demo_estates: list[Estate]) -> None:
    mandate = _demo_mandate(seeded)
    selected = seeded.exec(
        select(EstateSearchRequest).where(EstateSearchRequest.id_search_request == mandate.id_search_request)
    ).all()
    proposed = seeded.exec(select(EstateProposed).where(EstateProposed.id_mandate == mandate.id)).all()

    in_budget = {estate.id for estate in demo_estates[: seed_demo.NB_ESTATES]}
    assert {row.id_estate for row in selected} == in_budget
    assert {row.id_estate for row in proposed} == in_budget


def test_seed_creates_visits_within_the_mandate(seeded: Session) -> None:
    mandate = _demo_mandate(seeded)
    visits = seeded.exec(select(Visit).where(Visit.id_mandate == mandate.id)).all()

    assert len(visits) == seed_demo.NB_CLIENT_VISITS + 1
    assert all(seed_demo.MANDATE_SIGNED <= v.visit_date <= seed_demo.MANDATE_ENDS for v in visits)
    assert sorted(v.visitor_type for v in visits) == ["client", "client", "hunter"]


def test_demo_client_sees_only_its_visits(seeded: Session, demo_estates: list[Estate]) -> None:
    # Une visite sur le mandat d'un autre client (visite du chasseur : P23 ne la regarde pas).
    other_estate = demo_estates[-1].id
    assert other_estate is not None
    seeded.add(Visit(visit_date=date(2026, 5, 10), visitor_type="hunter", id_estate=other_estate, id_mandate=OTHER_MANDATE))
    seeded.commit()

    client = _demo_user(seeded, CLIENT)
    visits = VisitService(VisitRepository(), MandateRepository(), EstateProposedRepository())
    seen = visits.list_all(seeded, Principal(user=client, role=CLIENT))

    demo_mandate = _demo_mandate(seeded).id
    assert len(seen) == seed_demo.NB_CLIENT_VISITS + 1
    assert all(v.id_mandate == demo_mandate for v in seen)


def test_main_refuses_the_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSWORD", DEMO_PASSWORD)
    monkeypatch.setenv("POSTGRES_DB", "fil_rouge_test")
    with pytest.raises(SystemExit, match="fil_rouge_test"):
        seed_demo.main()


@pytest.mark.parametrize("password", [None, "trop-court"])
def test_main_refuses_missing_or_short_password(monkeypatch: pytest.MonkeyPatch, password: str | None) -> None:
    if password is None:
        monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("DEMO_PASSWORD", password)
    with pytest.raises(SystemExit, match="DEMO_PASSWORD"):
        seed_demo.main()


# --- DEM3 : vente, paiement, note, avis --------------------------------------------


def _demo_sale(session: Session) -> Sale:
    return session.exec(select(Sale).where(Sale.id_mandate == _demo_mandate(session).id)).one()


def test_demo_payment_is_paid_at_the_calculated_amount(seeded: Session) -> None:
    sale = _demo_sale(seeded)
    payment = seeded.exec(select(Payment).where(Payment.id_sale == sale.id)).one()
    assert payment.status == "paid"

    # Le montant attendu est recalculé ici par le vrai calcul, jamais écrit en dur.
    calculation = PaymentCalculationService(
        SaleRepository(), MandateRepository(), VisitRepository(), HunterRepository(), PaymentRepository(),
        CommissionScaleRepository(), HunterRateParametersRepository(), seed_demo._parametrage(),  # pyright: ignore[reportPrivateUsage] -- le même paramétrage que le script
    )
    vente = calculation.build_vente(seeded, sale)
    expected = calculer_remuneration(vente, seed_demo._parametrage().charger(seeded, vente.date_acte))  # pyright: ignore[reportPrivateUsage] -- idem
    assert expected.montant > 0
    assert payment.amount == expected.montant


def test_demo_payment_writes_the_hunter_note(seeded: Session) -> None:
    payment = seeded.exec(select(Payment).where(Payment.id_sale == _demo_sale(seeded).id)).one()
    [note] = seeded.exec(select(HunterPerformance).where(HunterPerformance.id_payment == payment.id)).all()
    assert (note.trigger_type, note.id_hunter) == ("payment", _demo_user(seeded, HUNTER).id)


def test_demo_review_is_on_the_sold_estate(seeded: Session) -> None:
    sale = _demo_sale(seeded)
    selection = seeded.exec(
        select(EstateSearchRequest)
        .where(EstateSearchRequest.id_estate == sale.id_estate)
        .where(EstateSearchRequest.id_search_request == _demo_mandate(seeded).id_search_request)
    ).one()
    assert selection.review_hunter
    [media] = seeded.exec(select(ReviewMedia).where(ReviewMedia.id_estate_searchrequest == selection.id)).all()
    assert media.media_type == "video"
