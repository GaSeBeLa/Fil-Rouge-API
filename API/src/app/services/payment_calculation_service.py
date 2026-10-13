"""
payment_calculation_service.py — Compte en base ce que le calcul de
rémunération attend, l'appelle, et en fait un paiement (fiche API12).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
`remuneration.py` est une fonction pure : il reçoit une `Vente` (des
nombres) et un `Parametrage`. Ce service est le pont avec la base :

    la vente, son mandat, sa chaîne  ->  Vente  ->  calculer_remuneration
                                                 ->  Payment 'announced'
                                                     (ou 'refused')

Ce qui se compte, à la date de l'acte, sur la fenêtre de `window_months`
mois qui la précède (ADR-048) :

- les visites `'client'` de toute la chaîne du mandat, jusqu'à l'acte
  (point 4, ADR-053) ; les visites `'hunter'` ne comptent pas ;
- les ventes du chasseur, sauf celles au paiement refusé, vente en cours
  exclue (point 3) ;
- les deux termes du taux des mandats (point 7) : les chaînes signées sur
  la fenêtre arrivées à leur première issue, et celles finies par une
  vente ; chaîne de la vente en cours exclue.

Une chaîne = un mandat racine et ses renouvellements (`id_mandate_parent`,
ADR-050) ; elle compte une fois (Q-REM-09), datée par la signature de sa
racine. Les comptages sont des fonctions pures sur des listes, pour se
tester sans base.

La note du journal (ADR-035) : `journal_note` l'écrit quand le paiement
passe à 'paid' — `PaymentService` l'appelle. Les trois notes de la vente
(délai, exclusivité, visites) viennent du détail du paiement ; les deux
critères d'activité (ventes, taux) sont recomptés à la date du paiement,
sans rien exclure : la vente payée compte désormais (ADR-048, point 8).

Les lectures passent par `list_all` / `list_where` puis un filtre Python :
les volumes du projet sont petits, et chaque règle se lit en clair.
============================================================================
"""

from calendar import monthrange
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import Session

from ..models import CommissionScale, HunterPerformance, Mandate, Payment, Sale, Visit
from ..models.payment_model import CalculationDetails, CalculationNotes
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.hunter_repository import HunterRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.payment_repository import PaymentRepository
from ..repositories.sale_repository import SaleRepository
from ..repositories.visit_repository import VisitRepository
from ..utils.exceptions import ConflictError, NotFoundError
from .parametrage_service import ParametrageService, performance
from .remuneration import (
    BaremeIntrouvable,
    Exclusivite,
    MotifRefus,
    OrigineVente,
    Vente,
    calculer_remuneration,
    calculer_score,
    noter_criteres,
)

REFUSED = "refused"
ANNOUNCED = "announced"
# ADR-048, point 7 : une clôture après signature est une première issue.
CLOSED_STATUSES = frozenset({"lost", "canceled"})
# ADR-024 : le motif du calcul -> la valeur de payment.refusal_reason.
REFUSAL_REASONS = {
    MotifRefus.MANDAT_EXPIRE: "mandate_expired",
    MotifRefus.HORS_DISPOSITIF: "out_of_scope",
}
ORIGINS = {"hunter": OrigineVente.CHASSEUR, "client_alone": OrigineVente.CLIENT_SEUL}
# Les noms de remuneration.py -> ceux de CalculationNotes (ADR-033).
NOTE_KEYS = {
    "delai": "delay",
    "exclusivite": "exclusivity",
    "ventes": "sales",
    "mandats": "mandates",
    "visites": "visits",
}


# --- Comptages purs ----------------------------------------------------------


def months_before(day: date, months: int) -> date:
    """`day` moins `months` mois ; le jour est ramené au dernier du mois si besoin."""
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def full_years(start: date, end: date) -> int:
    """Années révolues de `start` à `end` (l'ancienneté, RCR §8)."""
    return end.year - start.year - ((end.month, end.day) < (start.month, start.day))


def chain_root(mandate: Mandate, by_id: dict[int, Mandate]) -> Mandate:
    """La racine de la chaîne : on remonte `id_mandate_parent` (ADR-050)."""
    current = mandate
    while current.id_mandate_parent is not None and current.id_mandate_parent in by_id:
        current = by_id[current.id_mandate_parent]
    return current


@dataclass(frozen=True)
class Activity:
    """Les deux critères d'activité d'un chasseur à une date (ADR-048, points 3 et 7)."""

    sales: int
    mandates: int
    sold_mandates: int


def count_activity(
    mandates: Sequence[Mandate],
    sales: Iterable[Sale],
    refused_sale_ids: set[int],
    on: date,
    window_months: int,
    excluded_sale_id: Optional[int] = None,
) -> Activity:
    """
    Compte, pour les mandats d'UN chasseur, sur la fenêtre ]on - window ; on] :

    - les ventes, sauf paiement refusé et sauf `excluded_sale_id` (point 3) ;
    - les chaînes signées sur la fenêtre arrivées à leur première issue —
      vente, clôture ('lost', 'canceled') ou première échéance sans vente —,
      et parmi elles celles finies par une vente au paiement non refusé
      (point 7). La chaîne de `excluded_sale_id` est exclue des deux termes.
    """
    start = months_before(on, window_months)
    by_id = {m.id: m for m in mandates if m.id is not None}
    root_of = {mid: chain_root(m, by_id).id for mid, m in by_id.items()}

    chain_sales: dict[Optional[int], list[Sale]] = {}
    excluded_root: Optional[int] = None
    for sale in sales:
        if sale.id_mandate not in root_of:
            continue
        root = root_of[sale.id_mandate]
        if sale.id == excluded_sale_id:
            excluded_root = root
            continue
        if sale.signature_date <= on:
            chain_sales.setdefault(root, []).append(sale)

    counted_sales = sum(
        1
        for chain in chain_sales.values()
        for sale in chain
        if start < sale.signature_date and sale.id not in refused_sale_ids
    )

    issued = sold = 0
    for root in (m for m in by_id.values() if m.id_mandate_parent is None or m.id_mandate_parent not in by_id):
        if root.id == excluded_root or root.signature_date is None:
            continue
        if not start < root.signature_date <= on:
            continue
        chain = [m for mid, m in by_id.items() if root_of[mid] == root.id]
        sold_here = any(s.id not in refused_sale_ids for s in chain_sales.get(root.id, []))
        closed = any(m.status in CLOSED_STATUSES for m in chain)
        expired = root.ends_at is not None and root.ends_at <= on
        if chain_sales.get(root.id) or closed or expired:
            issued += 1
            sold += sold_here
    return Activity(sales=counted_sales, mandates=issued, sold_mandates=sold)


def count_client_visits(visits: Iterable[Visit], chain_ids: set[int], until: date) -> int:
    """Les visites 'client' de la chaîne, jusqu'au jour de l'acte (ADR-048 point 4, ADR-053)."""
    return sum(
        1
        for v in visits
        if v.visitor_type == "client" and v.id_mandate in chain_ids and v.visit_date <= until
    )


def scale_line_id(lines: Iterable[CommissionScale], hunter_id: int, on: date, price: int) -> int:
    """
    L'id de la ligne de barème que `taux_de_tranche` retient (RCR §7) : la
    nominative prime sur le défaut, puis la plus récente. Même filtre, même
    ordre : le paiement cite la ligne qui a donné son taux.
    """
    candidates = [
        line
        for line in lines
        if line.id_hunter in (hunter_id, None)
        and line.valid_from <= on
        and (line.valid_until is None or on <= line.valid_until)
        and line.amount_min <= price
        and (line.amount_max is None or price <= line.amount_max)
    ]
    if not candidates:
        raise BaremeIntrouvable(f"aucun barème pour le chasseur {hunter_id}, {price} € au {on}")
    candidates.sort(key=lambda l: (l.id_hunter is not None, l.valid_from), reverse=True)
    best = candidates[0].id
    assert best is not None  # une ligne lue en base a toujours son id
    return best


# --- Le service --------------------------------------------------------------


class PaymentCalculationService:
    def __init__(
        self,
        sales: SaleRepository,
        mandates: MandateRepository,
        visits: VisitRepository,
        hunters: HunterRepository,
        payments: PaymentRepository,
        scale: CommissionScaleRepository,
        rate_parameters: HunterRateParametersRepository,
        parametrage: ParametrageService,
    ):
        self.sales = sales
        self.mandates = mandates
        self.visits = visits
        self.hunters = hunters
        self.payments = payments
        self.scale = scale
        self.rate_parameters = rate_parameters
        self.parametrage = parametrage

    def _hunter_context(self, session: Session, hunter_id: int) -> tuple[list[Mandate], list[Sale], set[int]]:
        """Les mandats du chasseur, leurs ventes, et les ventes au paiement refusé."""
        mandates = list(self.mandates.list_where(session, id_hunter=hunter_id))
        mandate_ids = {m.id for m in mandates}
        sales = [s for s in self.sales.list_all(session) if s.id_mandate in mandate_ids]
        refused = {p.id_sale for p in self.payments.list_where(session, status=REFUSED)}
        return mandates, sales, refused

    def build_vente(self, session: Session, sale: Sale) -> Vente:
        """La `Vente` de remuneration.py, comptée en base à la date de l'acte."""
        mandate = self.mandates.get_by_id(session, sale.id_mandate)
        if mandate is None:
            raise NotFoundError(f"Mandat {sale.id_mandate} introuvable")
        hunter = self.hunters.get_by_id(session, mandate.id_hunter)
        if hunter is None:
            raise NotFoundError(f"Chasseur {mandate.id_hunter} introuvable")
        if mandate.ends_at is None:
            raise ConflictError(f"Le mandat {mandate.id} n'a pas de date de fin : le droit ne se juge pas.")

        acte = sale.signature_date
        window = self.parametrage.reglages_applicables(session, acte).window_months
        mandates, sales, refused = self._hunter_context(session, mandate.id_hunter)
        by_id = {m.id: m for m in mandates if m.id is not None}
        root = chain_root(mandate, by_id)
        if root.signature_date is None:
            raise ConflictError(f"Le mandat {root.id} n'est pas signé : pas de délai à noter (ADR-050).")
        chain_ids = {mid for mid, m in by_id.items() if chain_root(m, by_id).id == root.id}
        activity = count_activity(mandates, sales, refused, acte, window, excluded_sale_id=sale.id)
        visits = [v for v in self.visits.list_where(session, visitor_type="client") if v.id_mandate in chain_ids]

        return Vente(
            chasseur_id=mandate.id_hunter,
            prix_acte=Decimal(sale.purchase_amount),
            date_acte=acte,
            date_signature_mandat=root.signature_date,  # ADR-050 : la première signature
            date_fin_mandat=mandate.ends_at,
            exclusivite=Exclusivite.EXCLUSIF if mandate.is_exclusive else Exclusivite.NON_EXCLUSIF,
            origine=ORIGINS[sale.sale_origin],
            nb_visites=count_client_visits(visits, chain_ids, acte),
            annees_anciennete=full_years(hunter.hire_date, acte),
            ventes_12_mois=activity.sales,
            mandats_12_mois=activity.mandates,
            mandats_vendus_12_mois=activity.sold_mandates,
        )

    def build_payment(self, session: Session, sale_id: int) -> Payment:
        """
        Le paiement d'une vente, prêt à créer : 'announced' avec ses taux et
        son détail, ou 'refused' avec son motif (ADR-024). 404 vente
        inconnue ; 409 vente déjà payée, ou paramétrage manquant.
        """
        sale = self.sales.get_by_id(session, sale_id)
        if sale is None:
            raise NotFoundError(f"Vente {sale_id} introuvable")
        if self.payments.exists_with(session, "id_sale", sale_id):
            raise ConflictError(f"La vente {sale_id} a déjà son paiement : il ne se recalcule pas (ADR-033).")
        try:
            vente = self.build_vente(session, sale)
            result = calculer_remuneration(vente, self.parametrage.charger(session, vente.date_acte))
        except BaremeIntrouvable as exc:
            raise ConflictError(f"Paramétrage incomplet : {exc}.") from exc

        if not result.droit_ouvert:
            assert result.motif_refus is not None  # droit fermé = un motif (remuneration.py)
            return Payment(
                amount=Decimal("0.00"),
                status=REFUSED,
                refusal_reason=REFUSAL_REASONS[result.motif_refus],
                id_sale=sale_id,
                id_hunter=vente.chasseur_id,
            )

        settings = self.parametrage.reglages_applicables(session, vente.date_acte)
        details = CalculationDetails(
            notes=CalculationNotes(**{NOTE_KEYS[k]: float(v) for k, v in result.notes.items()}),
            visit_count=vente.nb_visites,
            seniority_years=vente.annees_anciennete,
            sales_12_months=vente.ventes_12_mois,
            mandates_12_months=vente.mandats_12_mois,
            sold_mandates_12_months=vente.mandats_vendus_12_mois,
            mandate_signature_date=vente.date_signature_mandat,
            mandate_ends_at=vente.date_fin_mandat,
            is_exclusive=vente.exclusivite is Exclusivite.EXCLUSIF,
        )
        return Payment(
            amount=result.montant,
            status=ANNOUNCED,
            announced_at=datetime.now(timezone.utc),
            base_rate=result.taux_base,
            seniority_rate=result.majoration_anciennete,
            performance_rate=result.modulation_performance,
            final_rate=result.taux_final,
            performance_score=result.score_performance,
            calculation_details=details.model_dump(mode="json", exclude_none=True),
            id_sale=sale_id,
            id_hunter=vente.chasseur_id,
            id_commission_scale=scale_line_id(
                self.scale.list_all(session), vente.chasseur_id, vente.date_acte, sale.purchase_amount
            ),
            id_hunter_rate_parameters=settings.id,
        )

    def journal_note(self, session: Session, payment: Payment, paid_at: datetime) -> HunterPerformance:
        """
        La note 'payment' du journal, quand le paiement passe à 'paid'
        (ADR-035) : les trois notes de la vente reprises du détail, les deux
        critères d'activité recomptés à la date du paiement, rien d'exclu
        (ADR-048, point 8), pesés par la version des réglages du paiement.
        """
        if payment.calculation_details is None or payment.id_hunter_rate_parameters is None:
            raise ConflictError(f"Le paiement {payment.id} n'a pas de détail de calcul : pas de note (ADR-035).")
        settings = self.rate_parameters.get_by_id(session, payment.id_hunter_rate_parameters)
        if settings is None:
            raise ConflictError(f"Réglages {payment.id_hunter_rate_parameters} introuvables.")
        if paid_at.tzinfo is None:
            # La base garde ses TIMESTAMP en UTC (chk_paid_not_in_future).
            paid_at = paid_at.replace(tzinfo=timezone.utc)
        weights = performance(settings)
        kept = payment.calculation_details["notes"]
        on = paid_at.date()
        mandates, sales, refused = self._hunter_context(session, payment.id_hunter)
        activity = count_activity(mandates, sales, refused, on, settings.window_months)

        # Une Vente fictive sert à noter les deux critères d'activité avec
        # les règles mêmes du calcul (noter_criteres) ; seuls ses comptes servent.
        notes = noter_criteres(
            Vente(
                chasseur_id=payment.id_hunter,
                prix_acte=Decimal(0),
                date_acte=on,
                date_signature_mandat=on,
                date_fin_mandat=on,
                exclusivite=Exclusivite.EXCLUSIF,
                origine=OrigineVente.CHASSEUR,
                nb_visites=0,
                annees_anciennete=0,
                ventes_12_mois=activity.sales,
                mandats_12_mois=activity.mandates,
                mandats_vendus_12_mois=activity.sold_mandates,
            ),
            weights,
        )
        for ours, theirs in (("delai", "delay"), ("exclusivite", "exclusivity"), ("visites", "visits")):
            notes[ours] = Decimal(str(kept[theirs]))
        return HunterPerformance(
            score=calculer_score(notes, weights),
            scored_at=paid_at,
            trigger_type="payment",
            id_hunter=payment.id_hunter,
            id_payment=payment.id,
        )

