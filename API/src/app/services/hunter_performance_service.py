"""
hunter_performance_service.py — La note de performance des chasseurs.

« Le sien » (ADR-027, annexe § 4 ; fiche DRO6) : un Hunter voit sa note
(H12) ; celle d'un autre chasseur rend 404. Le Manager (fiche DRO7) voit
celle de ses chasseurs.
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import col

from ..models import HunterPerformance
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..utils.roles import HUNTER, MANAGER, Principal
from .base_service import BaseService
from .manager_rows import hunters_of_team


class HunterPerformanceService(BaseService[HunterPerformance]):
    def __init__(self, repository: HunterPerformanceRepository):
        super().__init__(repository, not_found_detail="Score de performance introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == HUNTER:
            return col(HunterPerformance.id_hunter) == viewer.profile_id
        if viewer.role == MANAGER:
            return col(HunterPerformance.id_hunter).in_(hunters_of_team(viewer.profile_id))
        return None
