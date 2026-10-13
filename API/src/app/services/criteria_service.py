"""
criteria_service.py — Les critères d'une demande.

« Le sien » (ADR-027, annexe § 2 ; fiche DRO5) : un Client voit les
critères de ses demandes, et n'en crée que sur l'une d'elles (P1). Le
Hunter (fiche DRO6) de même, sur les demandes qu'il suit (H4).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import Criteria
from ..repositories.criteria_repository import CriteriaRepository
from ..utils.roles import CLIENT, HUNTER, Principal
from .base_service import BaseService
from .client_rows import owns_request, requests_of
from .hunter_rows import handles_request, requests_handled_by


class CriteriaService(BaseService[Criteria]):
    def __init__(self, repository: CriteriaRepository):
        super().__init__(repository, not_found_detail="Critères introuvables")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Criteria.id_search_request).in_(requests_of(viewer.user.id))
        if viewer.role == HUNTER:
            return col(Criteria.id_search_request).in_(requests_handled_by(viewer.user.id))
        return None

    def owns(self, session: Session, item: Criteria, viewer: Principal) -> bool:
        if viewer.role == CLIENT:
            return owns_request(session, viewer.user.id, item.id_search_request)
        if viewer.role == HUNTER:
            return handles_request(session, viewer.user.id, item.id_search_request)
        return True
