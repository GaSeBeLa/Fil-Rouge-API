from ..models import EstateSearchRequest
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from .base_service import BaseService


class EstateSearchRequestService(BaseService[EstateSearchRequest]):
    def __init__(self, repository: EstateSearchRequestRepository):
        super().__init__(repository, not_found_detail="Média introuvable")
