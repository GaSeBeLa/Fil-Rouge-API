from ..models import Visit
from ..repositories.visit_repository import VisitRepository
from .base_service import BaseService


class VisitService(BaseService[Visit]):
    def __init__(self, repository: VisitRepository):
        super().__init__(repository, not_found_detail="Visite introuvable")
