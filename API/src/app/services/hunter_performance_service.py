from ..models import HunterPerformance
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from .base_service import BaseService


class HunterPerformanceService(BaseService[HunterPerformance]):
    def __init__(self, repository: HunterPerformanceRepository):
        super().__init__(repository, not_found_detail="Score de performance introuvable")
