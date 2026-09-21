from ..models import Visit
from .base_repository import BaseRepository


class VisitRepository(BaseRepository[Visit]):
    def __init__(self):
        super().__init__(Visit)
