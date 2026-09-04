from ..models import Criteria
from ..repositories.criteria_repository import CriteriaRepository
from .base_service import BaseService


class CriteriaService(BaseService[Criteria]):
    def __init__(self, repository: CriteriaRepository):
        super().__init__(repository, not_found_detail="Critères introuvables")
