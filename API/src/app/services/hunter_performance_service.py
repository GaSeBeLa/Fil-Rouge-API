"""
hunter_performance_service.py — La note de performance des chasseurs.

« Le sien » (ADR-027, annexe § 4 ; fiche DRO6) : un Hunter voit sa note
(H12) ; celle d'un autre chasseur rend 404.
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import col

from ..models import HunterPerformance
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..utils.roles import HUNTER, Principal
from .base_service import BaseService


class HunterPerformanceService(BaseService[HunterPerformance]):
    def __init__(self, repository: HunterPerformanceRepository):
        super().__init__(repository, not_found_detail="Score de performance introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == HUNTER:
            return col(HunterPerformance.id_hunter) == viewer.user.id
        return None
