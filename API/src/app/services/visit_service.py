"""
visit_service.py — Une visite, dans les règles du mandat (fiche API7).

Règles qui croisent les tables, donc dans le service (ADR-040) ; un refus
lève ConflictError (409). Elles valent au POST comme au PUT :

- ADR-044 (Q-MAN-06 ; TODO du bloc `visit` de init-v3/01) : pas de visite
  avant la signature du mandat ; un mandat non signé n'en a donc aucune.
- P25 (ADR-053) : la visite tombe dans les dates du mandat, donc pas après
  `ends_at`. Le statut du mandat n'est pas regardé.
- P23 (ADR-053, « la règle des visites ») : une visite `'client'` porte sur
  un bien proposé sur ce mandat (`estate_proposed`). Les visites `'hunter'`
  ne sont pas contrôlées.

« Le sien » (ADR-027, annexe § 3 ; fiche DRO5) : un Client voit les
visites de ses mandats. Le Hunter (fiche DRO6) aussi, et n'en crée que sur
un de ses mandats (Q-ACC-13).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import User, Visit
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.visit_repository import VisitRepository
from ..utils.exceptions import ConflictError
from ..utils.roles import CLIENT, HUNTER, Principal
from .base_service import BaseService
from .client_rows import mandates_of
from .hunter_rows import handles_mandate, mandates_handled_by

CLIENT_VISIT = "client"


class VisitService(BaseService[Visit]):
    def __init__(self, repository: VisitRepository, mandates: MandateRepository, proposals: EstateProposedRepository):
        super().__init__(repository, not_found_detail="Visite introuvable")
        self.mandates = mandates
        self.proposals = proposals

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Visit.id_mandate).in_(mandates_of(viewer.user.id))
        if viewer.role == HUNTER:
            return col(Visit.id_mandate).in_(mandates_handled_by(viewer.user.id))
        return None

    def owns(self, session: Session, item: Visit, viewer: Principal) -> bool:
        return viewer.role != HUNTER or handles_mandate(session, viewer.user.id, item.id_mandate)

    def _check_visit(self, session: Session, item: Visit) -> None:
        mandate = self.mandates.get_by_id(session, item.id_mandate)
        if mandate is None:
            raise ConflictError("Mandat introuvable (id_mandate).")
        if mandate.signature_date is None or item.visit_date < mandate.signature_date:
            raise ConflictError("Une visite ne précède pas la signature du mandat (ADR-044).")
        if mandate.ends_at is not None and item.visit_date > mandate.ends_at:
            raise ConflictError(f"Une visite tombe dans les dates du mandat, au plus tard le {mandate.ends_at} (P25).")
        if item.visitor_type == CLIENT_VISIT and not self.proposals.exists_where(
            session, id_mandate=item.id_mandate, id_estate=item.id_estate
        ):
            raise ConflictError("Le client ne visite qu'un bien proposé sur ce mandat (P23).")

    def create(self, session: Session, item: Visit, actor: Optional[User] = None) -> Visit:
        self._check_visit(session, item)
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: Visit) -> Visit:
        existing = self.get_by_id(session, item_id)
        self._check_visit(session, data)
        return self.repository.replace(session, existing, data)
