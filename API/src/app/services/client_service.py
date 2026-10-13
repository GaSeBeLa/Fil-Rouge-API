"""
client_service.py — Les fiches client.

« Le sien » (ADR-027, annexe § 1 ; fiche DRO5) : un Client voit sa fiche,
et ne crée ou ne modifie que la sienne (Q-ACC-12) : `id_user` reste son
compte.

Le Hunter (fiche DRO6) voit ses clients (H3) : ceux d'une de ses demandes
ou d'un de ses mandats.

Compte désactivé (fiche DRO8) : sa fiche n'est plus lue que par l'Admin
(account_column, base_service.py).
"""

from typing import Optional

from sqlalchemy import ColumnElement, or_
from sqlmodel import Session, col

from ..models import Client
from ..repositories.client_repository import ClientRepository
from ..utils.roles import CLIENT, HUNTER, Principal
from .base_service import BaseService
from .hunter_rows import clients_of


class ClientService(BaseService[Client]):
    # ADR-027, point 7 : désactivé, ce compte n'est plus lu que par l'Admin (DRO8).
    account_column = Client.id_user

    def __init__(self, repository: ClientRepository):
        super().__init__(repository, not_found_detail="Client introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Client.id_user) == viewer.user.id
        if viewer.role == HUNTER:
            return or_(*(col(Client.id_user).in_(clients) for clients in clients_of(viewer.user.id)))
        return None

    def owns(self, session: Session, item: Client, viewer: Principal) -> bool:
        return viewer.role != CLIENT or item.id_user == viewer.user.id
