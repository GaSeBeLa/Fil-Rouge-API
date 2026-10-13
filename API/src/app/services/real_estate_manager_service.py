"""
real_estate_manager_service.py — Les fiches des managers.

« Le sien » (ADR-027, annexe § 1 ; fiche DRO6) : un Hunter voit son manager
(hunter.id_realestatemanager) ; un autre manager rend 404.

Le Manager (fiche DRO7) voit sa fiche, et n'y modifie que ses coordonnées
(CONTACT_FIELDS de hunter_service.py, le bloc commun aux deux tables) ; le
reste lève ForbiddenError (403).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import RealEstateManager
from ..repositories.real_estate_manager_repository import RealEstateManagerRepository
from ..utils.roles import HUNTER, MANAGER, Principal
from .base_service import BaseService
from .hunter_rows import manager_of
from .hunter_service import check_contact_only


class RealEstateManagerService(BaseService[RealEstateManager]):
    def __init__(self, repository: RealEstateManagerRepository):
        super().__init__(repository, not_found_detail="Gestionnaire immobilier introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == HUNTER:
            return col(RealEstateManager.id_user).in_(manager_of(viewer.user.id))
        if viewer.role == MANAGER:
            return col(RealEstateManager.id_user) == viewer.user.id
        return None

    def replace_visible(
        self, session: Session, item_id: int, data: RealEstateManager, viewer: Principal
    ) -> RealEstateManager:
        """
        Le PUT : la fiche d'un autre lève NotFoundError (404) ; hors Admin,
        changer autre chose que ses coordonnées lève ForbiddenError (403).
        """
        check_contact_only(self.get_by_id(session, item_id, viewer), data, viewer)
        return super().replace_visible(session, item_id, data, viewer)
