from ..models import SearchRequest
from ..repositories.search_request_repository import SearchRequestRepository
from ..services.search_request_service import SearchRequestService
from .crud_router import build_crud_router

router = build_crud_router(
    service=SearchRequestService(SearchRequestRepository()),
    prefix="/search-requests",
    tag="search_request",
    response_model=SearchRequest,
)
