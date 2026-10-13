"""
estate_contact_service.py — Le contact du vendeur d'un bien, et qui l'a
saisi (ADR-054).

Même règle d'auteur que estate_service.py (ADR-047) :
- create : `id_author` est le compte connecté, jamais la valeur reçue ;
  sans compte (un script), il reste vide : contact importé ;
- replace : `id_author` garde la valeur en base.

Un second contact pour le même bien, ou un bien inexistant, est refusé par
la base (UNIQUE, clé étrangère) : 409.

Lecture et écriture sont réservées à Admin, Hunter et Manager par le
routeur (routes/estate_contact_router.py).
"""

from typing import Optional

from sqlmodel import Session

from ..models import EstateContact, User
from ..repositories.estate_contact_repository import EstateContactRepository
from .base_service import BaseService


class EstateContactService(BaseService[EstateContact]):
    def __init__(self, repository: EstateContactRepository):
        super().__init__(repository, not_found_detail="Contact introuvable")

    def create(self, session: Session, item: EstateContact, actor: Optional[User] = None) -> EstateContact:
        item.id_author = actor.id if actor is not None else None
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: EstateContact) -> EstateContact:
        existing = self.get_by_id(session, item_id)
        data.id_author = existing.id_author
        return self.repository.replace(session, existing, data)
