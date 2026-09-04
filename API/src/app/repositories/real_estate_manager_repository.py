from ..models import RealEstateManager
from .base_repository import BaseRepository


class RealEstateManagerRepository(BaseRepository[RealEstateManager]):
    def __init__(self):
        super().__init__(RealEstateManager)
