from ..models import EstateSearchRequest
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..services.estate_search_request_service import EstateSearchRequestService
from ..utils.roles import HUNTER
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateSearchRequestService(EstateSearchRequestRepository()),
    prefix="/estate-search-requests",
    tag="estate_searchrequest",
    response_model=EstateSearchRequest,
    # ADR-051 : la note est celle du chasseur qui la crée ; le service prend
    # son id dans le jeton (relecture de la série API6 → API10).
    create_roles=(HUNTER,),
)
