from ..models import HunterPerformance
from .base_repository import BaseRepository


class HunterPerformanceRepository(BaseRepository[HunterPerformance]):
    def __init__(self):
        super().__init__(HunterPerformance)
