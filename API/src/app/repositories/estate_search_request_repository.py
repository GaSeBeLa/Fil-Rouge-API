from ..models import EstateSearchRequest
from .base_repository import BaseRepository


class EstateSearchRequestRepository(BaseRepository[EstateSearchRequest]):
    def __init__(self):
        super().__init__(EstateSearchRequest)
