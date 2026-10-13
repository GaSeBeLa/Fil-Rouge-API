"""
estate_service.py — Un bien, et qui l'a saisi (ADR-047, fiche API6).

- create : `id_author` est le compte connecté, jamais la valeur reçue. Sans
  compte (un script qui appelle le service), il reste vide : vide veut dire
  « bien importé » (Q-ACC-09, Q-JEF-24).
- replace : `id_author` garde la valeur en base ; un PUT ne change pas
  l'auteur.

Le POST est réservé à Hunter et Manager par le routeur (`create_roles`,
routes/estate_router.py).

« Le sien » (ADR-027, annexe § 3 ; fiche DRO5) : un Client voit les biens
proposés pour lui (Q-ACC-05), pas tout le catalogue.
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import Estate, User
from ..repositories.estate_repository import EstateRepository
from ..utils.roles import CLIENT, Principal
from .base_service import BaseService
from .client_rows import estates_proposed_to


class EstateService(BaseService[Estate]):
    def __init__(self, repository: EstateRepository):
        super().__init__(repository, not_found_detail="Bien introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Estate.id).in_(estates_proposed_to(viewer.user.id))
        return None

    def create(self, session: Session, item: Estate, actor: Optional[User] = None) -> Estate:
        item.id_author = actor.id if actor is not None else None
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: Estate) -> Estate:
        existing = self.get_by_id(session, item_id)
        data.id_author = existing.id_author
        return self.repository.replace(session, existing, data)
