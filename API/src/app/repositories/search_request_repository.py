from ..models import SearchRequest
from .base_repository import BaseRepository


class SearchRequestRepository(BaseRepository[SearchRequest]):
    def __init__(self):
        super().__init__(SearchRequest)
