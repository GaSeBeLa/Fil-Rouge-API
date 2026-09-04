from ..models import EstateSearchRequest
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..services.estate_search_request_service import EstateSearchRequestService
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateSearchRequestService(EstateSearchRequestRepository()),
    prefix="/estate-search-requests",
    tag="estate_searchrequest",
    response_model=EstateSearchRequest,
)
