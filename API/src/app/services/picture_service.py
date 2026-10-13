"""
picture_service.py — Les photos d'un bien.

« Le sien » (ADR-027, annexe § 3 ; fiche DRO5) : un Client voit les photos
des biens proposés pour lui (Q-ACC-05).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import col

from ..models import Picture
from ..repositories.picture_repository import PictureRepository
from ..utils.roles import CLIENT, Principal
from .base_service import BaseService
from .client_rows import estates_proposed_to


class PictureService(BaseService[Picture]):
    def __init__(self, repository: PictureRepository):
        super().__init__(repository, not_found_detail="Photo introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Picture.id_estate).in_(estates_proposed_to(viewer.user.id))
        return None
