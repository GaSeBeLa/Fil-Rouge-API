from ..models import CommissionScale
from .base_repository import BaseRepository


class CommissionScaleRepository(BaseRepository[CommissionScale]):
    def __init__(self):
        super().__init__(CommissionScale)
