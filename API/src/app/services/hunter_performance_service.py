"""
hunter_performance_service.py — La note de performance des chasseurs.

« Le sien » (ADR-027, annexe § 4 ; fiche DRO6) : un Hunter voit sa note
(H12) ; celle d'un autre chasseur rend 404. Le Manager (fiche DRO7) voit
celle de ses chasseurs.

La note d'un mandat expiré (ADR-048, point 8 ; choix PERF-EXP du
2026-11-23) : `score_expired_mandates` écrit la note 'mandate_expired' de
chaque mandat 'expired' qui n'en a pas encore, calculée par
`PaymentCalculationService.expiry_note`. Le DAG Airflow `mandate_expiry`
passe les mandats en 'expired' ; `POST /hunter-performances/expired-mandates`
(Admin) les note.
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, SQLModel, col

from ..models import HunterPerformance
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..utils.roles import HUNTER, MANAGER, Principal
from .base_service import BaseService
from .manager_rows import hunters_of_team
from .payment_calculation_service import PaymentCalculationService

EXPIRED = "expired"
MANDATE_EXPIRED = "mandate_expired"


class ExpiredMandatesReport(SQLModel):
    # Les mandats notés par ce passage ; 0 et [] si tous l'étaient déjà.
    scored: int
    references: list[str]


class HunterPerformanceService(BaseService[HunterPerformance]):
    def __init__(self, repository: HunterPerformanceRepository):
        super().__init__(repository, not_found_detail="Score de performance introuvable")
        self.performances = repository  # typé : ses méthodes propres, pour pyright

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == HUNTER:
            return col(HunterPerformance.id_hunter) == viewer.profile_id
        if viewer.role == MANAGER:
            return col(HunterPerformance.id_hunter).in_(hunters_of_team(viewer.profile_id))
        return None

    def score_expired_mandates(self, session: Session, journal: PaymentCalculationService) -> ExpiredMandatesReport:
        """
        Écrit la note 'mandate_expired' de chaque mandat 'expired' qui n'en a
        pas encore, en une transaction : tout, ou rien.

        Rend le nombre de mandats notés et leurs références. Rappelée, elle
        ne note que les nouveaux (`uq_perf_mandate` : une note par mandat).
        ConflictError (409) : paramétrage incomplet à la fin d'un mandat, ou
        refus de la base ; rien n'est écrit.
        """
        scored = {p.id_mandate for p in self.repository.list_where(session, trigger_type=MANDATE_EXPIRED)}
        expired = [m for m in journal.mandates.list_where(session, status=EXPIRED) if m.id not in scored]
        expired.sort(key=lambda m: m.id or 0)
        for mandate in expired:
            self.repository.stage(session, journal.expiry_note(session, mandate))
        self.performances.commit(session)
        return ExpiredMandatesReport(scored=len(expired), references=[m.reference for m in expired])
