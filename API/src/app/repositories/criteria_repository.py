from ..models import Criteria
from .base_repository import BaseRepository


class CriteriaRepository(BaseRepository[Criteria]):
    def __init__(self):
        super().__init__(Criteria)
