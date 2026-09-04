from ..models import SearchRequest
from ..repositories.search_request_repository import SearchRequestRepository
from .base_service import BaseService


class SearchRequestService(BaseService[SearchRequest]):
    def __init__(self, repository: SearchRequestRepository):
        super().__init__(repository, not_found_detail="Demande de recherche introuvable")
