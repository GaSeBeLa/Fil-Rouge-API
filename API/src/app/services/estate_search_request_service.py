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

« Le sien » (ADR-027, annexe § 3 ; fiche DRO5) : un Client voit l'avis
posé sur ses demandes (P5).

Le Hunter (fiche DRO6) voit ses notes (H7), et n'en écrit que sur une de
ses demandes : ailleurs, ConflictError (409).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import EstateSearchRequest, User
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..utils.roles import CLIENT, HUNTER, Principal
from .base_service import BaseService
from .client_rows import requests_of
from .hunter_rows import handles_request


class EstateSearchRequestService(BaseService[EstateSearchRequest]):
    def __init__(self, repository: EstateSearchRequestRepository):
        super().__init__(repository, not_found_detail="Média introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(EstateSearchRequest.id_search_request).in_(requests_of(viewer.user.id))
        if viewer.role == HUNTER:
            return col(EstateSearchRequest.id_hunter) == viewer.user.id
        return None

    def owns(self, session: Session, item: EstateSearchRequest, viewer: Principal) -> bool:
        # id_hunter n'est pas regardé : create et replace le fixent (ADR-051).
        return viewer.role != HUNTER or handles_request(session, viewer.user.id, item.id_search_request)

    def create(
        self, session: Session, item: EstateSearchRequest, actor: Optional[User] = None
    ) -> EstateSearchRequest:
        if actor is not None and actor.id is not None:
            item.id_hunter = actor.id
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: EstateSearchRequest) -> EstateSearchRequest:
        data.id_hunter = self.get_by_id(session, item_id).id_hunter
        return super().replace(session, item_id, data)
