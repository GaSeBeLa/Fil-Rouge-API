"""
estate_search_request_service.py — Un bien mis dans la sélection d'une
demande, et la note du chasseur qui l'y a mis (ADR-051).

- create : `id_hunter`, l'auteur de la note, est le compte connecté, jamais
  la valeur reçue. Sans compte (un script qui appelle le service), la valeur
  reçue reste.
- replace : `id_hunter` garde la valeur en base. Sinon un autre chasseur
  prenait la note par un PUT, puis y ajoutait ses médias (relecture de la
  série API6 → API10).

Le POST est réservé à Hunter par le routeur (`create_roles`,
routes/estate_search_request_router.py).
"""

from typing import Optional

from sqlmodel import Session

from ..models import EstateSearchRequest, User
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from .base_service import BaseService


class EstateSearchRequestService(BaseService[EstateSearchRequest]):
    def __init__(self, repository: EstateSearchRequestRepository):
        super().__init__(repository, not_found_detail="Média introuvable")

    def create(
        self, session: Session, item: EstateSearchRequest, actor: Optional[User] = None
    ) -> EstateSearchRequest:
        if actor is not None and actor.id is not None:
            item.id_hunter = actor.id
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: EstateSearchRequest) -> EstateSearchRequest:
        data.id_hunter = self.get_by_id(session, item_id).id_hunter
        return super().replace(session, item_id, data)
