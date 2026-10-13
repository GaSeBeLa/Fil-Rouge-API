"""
payment_service.py — Les règles d'écriture d'un paiement.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Deux contrôles qu'aucun CHECK de la base ne peut tenir, car ils comparent
la ligne à autre chose qu'elle-même :

- ADR-038 — l'ordre du statut. Un paiement avance pas à pas, sans saut :
  'announced' -> 'scheduled' -> 'paid'. 'refused' (droit fermé, ADR-024)
  n'est possible que depuis 'announced', et ne se rouvre pas. Un paiement
  'paid' est figé : plus aucun PUT, et il ne s'efface plus (trace d'un
  versement). Le PUT est comparé au statut EN BASE : un retour en arrière,
  un saut ou un paiement payé modifié -> 409. Un POST ne crée qu'un
  paiement 'announced' ou 'refused' : les étapes suivantes passent par PUT.
- P33 — le taux final. Il est recalculé depuis les taux stockés (base,
  ancienneté, performance) et les bornes de la version des réglages citée
  (`taux_final` de remuneration.py) ; s'il diffère -> 409. Complète
  ADR-033, Décision 6.

Un refus ne porte aucun taux (chk_refused) : rien à recalculer. Un terme
manquant, ou une version des réglages inconnue, est laissé à la base
(chk_refused, clé étrangère), qui répond déjà 409.

ADR-035 — la note du journal. Quand un PUT fait passer le paiement à
'paid', la note 'payment' du chasseur s'écrit avec lui, dans la même
transaction (`PaymentCalculationService.journal_note`, fiche API12) : un
refus de la base annule les deux. Jamais avant : un paiement annoncé ou
planifié n'a pas de note.
============================================================================
"""

from typing import Optional

from sqlmodel import Session

from ..models import Payment, User
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.payment_repository import PaymentRepository
from ..utils.exceptions import ConflictError
from .base_service import BaseService
from .parametrage_service import modulation
from .payment_calculation_service import PaymentCalculationService
from .remuneration import taux_final

REFUSED = "refused"
PAID = "paid"
# ADR-038 : un paiement naît annoncé, ou refusé d'emblée.
CREATE_STATUSES = frozenset({"announced", REFUSED})
# ADR-038 : les statuts qu'un PUT peut donner, selon le statut en base.
# 'paid' n'en a aucun : un paiement payé ne se modifie plus.
NEXT_STATUSES: dict[str, frozenset[str]] = {
    "announced": frozenset({"announced", "scheduled", REFUSED}),
    "scheduled": frozenset({"scheduled", "paid"}),
    "paid": frozenset(),
    REFUSED: frozenset({REFUSED}),
}


class PaymentService(BaseService[Payment]):
    def __init__(
        self,
        repository: PaymentRepository,
        rate_parameters: HunterRateParametersRepository,
        journal: Optional[PaymentCalculationService] = None,
        performances: Optional[HunterPerformanceRepository] = None,
    ):
        super().__init__(repository, not_found_detail="Versement introuvable")
        self.rate_parameters = rate_parameters
        # ADR-035 : sans eux, le passage à 'paid' n'écrit pas de note (tests unitaires).
        self.journal = journal
        self.performances = performances

    def create(self, session: Session, item: Payment, actor: Optional[User] = None) -> Payment:
        if item.status not in CREATE_STATUSES:
            raise ConflictError(
                f"Un paiement se crée 'announced' ou 'refused', pas '{item.status}' : "
                "les étapes suivantes passent par PUT (ADR-038)."
            )
        self._check_final_rate(session, item)
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: Payment) -> Payment:
        existing = self.get_by_id(session, item_id)
        if data.status not in NEXT_STATUSES.get(existing.status, frozenset()):
            raise ConflictError(
                f"Statut '{existing.status}' -> '{data.status}' refusé : un paiement va pas à pas de "
                "'announced' à 'scheduled' puis 'paid', ou de 'announced' à 'refused' ; "
                "payé, il ne se modifie plus (ADR-038)."
            )
        self._check_final_rate(session, data)
        if data.status == PAID and existing.status != PAID:
            self._stage_journal_note(session, item_id, data)
        return self.repository.replace(session, existing, data)

    def delete(self, session: Session, item_id: int) -> Payment:
        existing = self.get_by_id(session, item_id)
        if existing.status == PAID:
            raise ConflictError("Un paiement payé ne s'efface pas : c'est la trace d'un versement (ADR-038).")
        return self.repository.delete(session, existing)

    def _stage_journal_note(self, session: Session, item_id: int, data: Payment) -> None:
        """ADR-035 : la note 'payment', préparée pour le commit du paiement."""
        if self.journal is None or self.performances is None or data.paid_at is None:
            return  # paid_at absent : chk_paid refuse déjà la ligne (409)
        data.id = item_id
        self.performances.stage(session, self.journal.journal_note(session, data, data.paid_at))

    def _check_final_rate(self, session: Session, payment: Payment) -> None:
        """P33 : le taux final stocké doit être celui que les taux stockés donnent."""
        if payment.status == REFUSED or payment.id_hunter_rate_parameters is None:
            return
        base, seniority, final = payment.base_rate, payment.seniority_rate, payment.final_rate
        performance = payment.performance_rate
        if base is None or seniority is None or performance is None or final is None:
            return
        settings = self.rate_parameters.get_by_id(session, payment.id_hunter_rate_parameters)
        if settings is None:
            return
        expected = taux_final(base, seniority, performance, modulation(settings))
        if final != expected:
            raise ConflictError(
                f"Taux final {final} incohérent : les taux stockés et les réglages "
                f"{payment.id_hunter_rate_parameters} donnent {expected} (P33)."
            )
