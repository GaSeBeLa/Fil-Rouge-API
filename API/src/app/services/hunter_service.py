"""
hunter_service.py — Les fiches des chasseurs.

« Le sien » (ADR-027, annexe § 1 ; fiche DRO5) : un Client voit son
chasseur (P2), celui d'un de ses mandats ou d'une de ses demandes.
"""

from typing import Optional

from sqlalchemy import ColumnElement, or_
from sqlmodel import col

from ..models import Hunter
from ..repositories.hunter_repository import HunterRepository
from ..utils.roles import CLIENT, Principal
from .base_service import BaseService
from .client_rows import hunters_of


class HunterService(BaseService[Hunter]):
    def __init__(self, repository: HunterRepository):
        super().__init__(repository, not_found_detail="Chasseur introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return or_(*(col(Hunter.id_user).in_(hunters) for hunters in hunters_of(viewer.user.id)))
        return None
