"""
search_request_service.py — Les demandes de recherche.

« Le sien » (ADR-027, annexe § 2 ; fiche DRO5) : un Client voit ses
demandes (F01:29) et n'en crée que pour lui (P1).

Le Hunter (fiche DRO6) voit les demandes qu'il suit (H1, H2) ; il n'en
crée (Q-ACC-15) et n'en modifie (accepter, refuser) qu'à son nom :
`id_hunter` reste son compte.

Le Manager (fiche DRO7) voit les demandes de son équipe (manager_rows.py).
Il n'y fait qu'un geste, affecter un chasseur (Q-ACC-10) : changer un autre
champ lève ForbiddenError (403) ; le chasseur affecté est l'un des siens, et
la demande reste à son équipe, sinon ConflictError (409).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import SearchRequest
from ..repositories.search_request_repository import SearchRequestRepository
from ..utils.exceptions import ForbiddenError
from ..utils.roles import CLIENT, HUNTER, MANAGER, Principal
from .base_service import BaseService, fields_changed_outside
from .manager_rows import in_team, leads_hunter, team_requests

# ADR-027, annexe § 2 : « U affecter un chasseur » (Q-ACC-10).
ASSIGN_FIELDS = ("id_hunter",)


class SearchRequestService(BaseService[SearchRequest]):
    def __init__(self, repository: SearchRequestRepository):
        super().__init__(repository, not_found_detail="Demande de recherche introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(SearchRequest.id_client) == viewer.profile_id
        if viewer.role == HUNTER:
            return col(SearchRequest.id_hunter) == viewer.profile_id
        if viewer.role == MANAGER:
            return in_team(SearchRequest.id, team_requests(viewer.profile_id))
        return None

    def owns(self, session: Session, item: SearchRequest, viewer: Principal) -> bool:
        if viewer.role == CLIENT:
            return item.id_client == viewer.profile_id
        if viewer.role == HUNTER:
            return item.id_hunter == viewer.profile_id
        if viewer.role == MANAGER:
            # Un chasseur affecté : l'un des siens. Sans chasseur, la demande
            # ne reste à son équipe que si elle lui est confiée.
            if item.id_hunter is not None:
                return leads_hunter(session, viewer.profile_id, item.id_hunter)
            return item.id_realestatemanager == viewer.profile_id
        return True

    def replace_visible(
        self, session: Session, item_id: int, data: SearchRequest, viewer: Principal
    ) -> SearchRequest:
        """
        Le PUT : la demande d'un autre lève NotFoundError (404) ; le Manager
        ne change que le chasseur affecté (403 sinon).
        """
        existing = self.get_by_id(session, item_id, viewer)
        if viewer.role == MANAGER:
            changed = fields_changed_outside(existing, data, ASSIGN_FIELDS)
            if changed:
                raise ForbiddenError(f"Le Manager ne fait qu'affecter un chasseur, pas {', '.join(changed)} (Q-ACC-10).")
        return super().replace_visible(session, item_id, data, viewer)
