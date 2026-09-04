from ..models import Hunter
from .base_repository import BaseRepository


class HunterRepository(BaseRepository[Hunter]):
    def __init__(self):
        super().__init__(Hunter)
