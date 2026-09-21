from ..models import Sale
from .base_repository import BaseRepository


class SaleRepository(BaseRepository[Sale]):
    def __init__(self):
        super().__init__(Sale)
