"""
mandate_service.py — Un mandat, et le lancement de sa recherche (fiche API8).

ADR-044 (déduction S6, confirmée le 09/10/2026) : quand le mandat reçoit sa
`signature_date` — créé signé, ou signé par un PUT —, la demande liée passe
à `'launched'` (ADR-041 : « le mandat est signé : la recherche est
lancée »). Même transaction : la demande est préparée (`stage`), puis écrite
par le commit du mandat ; si la base refuse le mandat, la demande reste
telle quelle.
"""

from typing import Optional

from sqlmodel import Session

from ..models import Mandate, User
from ..repositories.mandate_repository import MandateRepository
from ..repositories.search_request_repository import SearchRequestRepository
from .base_service import BaseService

LAUNCHED = "launched"


class MandateService(BaseService[Mandate]):
    def __init__(self, repository: MandateRepository, requests: SearchRequestRepository):
        super().__init__(repository, not_found_detail="Mandat introuvable")
        self.requests = requests

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
