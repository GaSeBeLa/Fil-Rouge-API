"""
real_estate_manager_service.py — Les fiches des managers.

« Le sien » (ADR-027, annexe § 1 ; fiche DRO6) : un Hunter voit son manager
(hunter.id_realestatemanager) ; un autre manager rend 404.
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import col

from ..models import RealEstateManager
from ..repositories.real_estate_manager_repository import RealEstateManagerRepository
from ..utils.roles import HUNTER, Principal
from .base_service import BaseService
from .hunter_rows import manager_of


class RealEstateManagerService(BaseService[RealEstateManager]):
    def __init__(self, repository: RealEstateManagerRepository):
        super().__init__(repository, not_found_detail="Gestionnaire immobilier introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == HUNTER:
            return col(RealEstateManager.id_user).in_(manager_of(viewer.user.id))
        return None
