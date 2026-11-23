"""
search_request_service.py — Les demandes de recherche.

« Le sien » (ADR-027, annexe § 2 ; fiche DRO5) : un Client voit ses
demandes (F01:29) et n'en crée que pour lui (P1).

Le Hunter (fiche DRO6) voit les demandes qu'il suit (H1, H2) ; il n'en
crée (Q-ACC-15) et n'en modifie (accepter, refuser) qu'à son nom :
`id_hunter` est sa fiche chasseur (`hunter.id`).

Le Manager (fiche DRO7) voit les demandes de son équipe (manager_rows.py),
et aussi les demandes « à prendre » : statut 'confirmed', sans chasseur ni
manager, comme celles du formulaire du site (choix B de Sébastien,
2026-11-19 ; trou trouvé par test_parcours_particulier.py).
Il n'y fait que deux gestes (Q-ACC-10) : affecter un chasseur, et prendre une
demande à prendre, pour lui seul (`id_realestatemanager` = sa fiche).
Changer un autre champ, ou confier la demande à un autre manager, lève
ForbiddenError (403) ; le chasseur affecté est l'un des siens, et la demande
reste à son équipe, sinon ConflictError (409).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, and_, col, or_

from ..models import SearchRequest
from ..repositories.search_request_repository import SearchRequestRepository
from ..utils.exceptions import ForbiddenError
from ..utils.roles import CLIENT, HUNTER, MANAGER, Principal
from .base_service import BaseService, fields_changed_outside
from .manager_rows import in_team, leads_hunter, team_requests

# ADR-027, annexe § 2 : « U affecter un chasseur » (Q-ACC-10).
ASSIGN_FIELDS = ("id_hunter", "id_realestatemanager")


def to_take() -> ColumnElement[bool]:
    """La condition SQL d'une demande « à prendre » : reçue, sans chasseur ni manager."""
    return and_(
        col(SearchRequest.status) == "confirmed",
        col(SearchRequest.id_hunter).is_(None),
        col(SearchRequest.id_realestatemanager).is_(None),
    )


def is_to_take(item: SearchRequest) -> bool:
    """Vrai si la demande est « à prendre » (même règle que to_take, en Python)."""
    return item.status == "confirmed" and item.id_hunter is None and item.id_realestatemanager is None


class SearchRequestService(BaseService[SearchRequest]):
    def __init__(self, repository: SearchRequestRepository):
        super().__init__(repository, not_found_detail="Demande de recherche introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(SearchRequest.id_client) == viewer.profile_id
        if viewer.role == HUNTER:
            return col(SearchRequest.id_hunter) == viewer.profile_id
        if viewer.role == MANAGER:
            return or_(in_team(SearchRequest.id, team_requests(viewer.profile_id)), to_take())
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
            return item.id_realestatemanager == viewer.profile_id or is_to_take(item)
        return True

    def replace_visible(
        self, session: Session, item_id: int, data: SearchRequest, viewer: Principal
    ) -> SearchRequest:
        """
        Le PUT : la demande d'un autre lève NotFoundError (404) ; le Manager
        ne change que le chasseur affecté, et ne prend une demande à prendre
        que pour lui (403 sinon). Rend la demande modifiée.
        """
        existing = self.get_by_id(session, item_id, viewer)
        if viewer.role == MANAGER:
            changed = fields_changed_outside(existing, data, ASSIGN_FIELDS)
            if changed:
                raise ForbiddenError(f"Le Manager ne fait qu'affecter un chasseur, pas {', '.join(changed)} (Q-ACC-10).")
            if data.id_realestatemanager not in (existing.id_realestatemanager, viewer.profile_id):
                raise ForbiddenError("Le Manager prend une demande pour lui, pas pour un autre manager.")
        return super().replace_visible(session, item_id, data, viewer)
