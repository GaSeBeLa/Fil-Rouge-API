from ..models import Estate
from .base_repository import BaseRepository


class EstateRepository(BaseRepository[Estate]):
    def __init__(self):
        super().__init__(Estate)
