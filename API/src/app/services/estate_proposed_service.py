from ..models import EstateProposed
from ..repositories.estate_proposed_repository import EstateProposedRepository
from .base_service import BaseService


class EstateProposedService(BaseService[EstateProposed]):
    def __init__(self, repository: EstateProposedRepository):
        super().__init__(repository, not_found_detail="Proposition de bien introuvable")
