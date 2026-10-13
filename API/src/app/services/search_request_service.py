"""
search_request_service.py — Les demandes de recherche.

« Le sien » (ADR-027, annexe § 2 ; fiche DRO5) : un Client voit ses
demandes (F01:29) et n'en crée que pour lui (P1).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import SearchRequest
from ..repositories.search_request_repository import SearchRequestRepository
from ..utils.roles import CLIENT, Principal
from .base_service import BaseService


class SearchRequestService(BaseService[SearchRequest]):
    def __init__(self, repository: SearchRequestRepository):
        super().__init__(repository, not_found_detail="Demande de recherche introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(SearchRequest.id_client) == viewer.user.id
        return None

    def owns(self, session: Session, item: SearchRequest, viewer: Principal) -> bool:
        return viewer.role != CLIENT or item.id_client == viewer.user.id
