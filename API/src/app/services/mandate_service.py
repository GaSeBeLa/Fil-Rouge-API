"""
mandate_service.py — Un mandat, et le lancement de sa recherche (fiche API8).

ADR-044 (déduction S6, confirmée le 09/10/2026) : quand le mandat reçoit sa
`signature_date` — créé signé, ou signé par un PUT —, la demande liée passe
à `'launched'` (ADR-041 : « le mandat est signé : la recherche est
lancée »). Même transaction : la demande est préparée (`stage`), puis écrite
par le commit du mandat ; si la base refuse le mandat, la demande reste
telle quelle.

« Le sien » (ADR-027, annexe § 2 ; fiche DRO5) : un Client voit ses
mandats, et ne modifie (signer, P3) que les siens : `id_client` reste son
compte. La clé (id_search_request, id_client) garde la demande au même client.

Le Hunter (fiche DRO6) voit ses mandats ; il n'en crée (H4) et n'en
modifie qu'à son nom, sur une de ses demandes : sinon un mandat sur la
demande d'un autre lui ouvrait le client de cet autre (H3). Renouveler le
mandat d'un autre chasseur reste fermé tant que Jeff n'a pas tranché la
réaffectation d'un mandat (Q-JEF-30).
"""

from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import Mandate, User
from ..repositories.mandate_repository import MandateRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..utils.roles import CLIENT, HUNTER, Principal
from .base_service import BaseService
from .hunter_rows import handles_request

LAUNCHED = "launched"


class MandateService(BaseService[Mandate]):
    def __init__(self, repository: MandateRepository, requests: SearchRequestRepository):
        super().__init__(repository, not_found_detail="Mandat introuvable")
        self.requests = requests

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Mandate.id_client) == viewer.user.id
        if viewer.role == HUNTER:
            return col(Mandate.id_hunter) == viewer.user.id
        return None

    def owns(self, session: Session, item: Mandate, viewer: Principal) -> bool:
        if viewer.role == CLIENT:
            return item.id_client == viewer.user.id
        if viewer.role == HUNTER:
            return item.id_hunter == viewer.user.id and handles_request(session, viewer.user.id, item.id_search_request)
        return True

    def _launch_request(self, session: Session, mandate: Mandate) -> None:
        request = self.requests.get_by_id(session, mandate.id_search_request)
        if request is None:
            return  # la clé étrangère du mandat refusera l'écriture (409)
        request.status = LAUNCHED
        self.requests.stage(session, request)

    def create(self, session: Session, item: Mandate, actor: Optional[User] = None) -> Mandate:
        if item.signature_date is not None:
            self._launch_request(session, item)
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: Mandate) -> Mandate:
        existing = self.get_by_id(session, item_id)
        if existing.signature_date is None and data.signature_date is not None:
            self._launch_request(session, data)
        return self.repository.replace(session, existing, data)
