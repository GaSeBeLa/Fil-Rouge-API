"""
client_service.py — Les fiches client.

« Le sien » (ADR-027, annexe § 1 ; fiche DRO5) : un Client voit sa fiche,
et ne crée ou ne modifie que la sienne (Q-ACC-12) : `id_user` reste son
compte.
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import Client
from ..repositories.client_repository import ClientRepository
from ..utils.roles import CLIENT, Principal
from .base_service import BaseService


class ClientService(BaseService[Client]):
    def __init__(self, repository: ClientRepository):
        super().__init__(repository, not_found_detail="Client introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Client.id_user) == viewer.user.id
        return None

    def owns(self, session: Session, item: Client, viewer: Principal) -> bool:
        return viewer.role != CLIENT or item.id_user == viewer.user.id
