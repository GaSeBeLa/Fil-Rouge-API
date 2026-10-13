from ..models import SearchRequest
from ..repositories.search_request_repository import SearchRequestRepository
from ..services.search_request_service import SearchRequestService
from ..utils.roles import ALL_ROLES, CLIENT, HUNTER, MANAGER
from .crud_router import build_crud_router

router = build_crud_router(
    service=SearchRequestService(SearchRequestRepository()),
    prefix="/search-requests",
    tag="search_request",
    response_model=SearchRequest,
    # ADR-027, annexe § 2 : créée par le client (P1) ou par le chasseur
    # pour un client qui a un compte (Q-ACC-15) ; modifiée par le
    # chasseur (accepter, refuser : H1, H2) et le manager (affecter un
    # chasseur : Q-ACC-10). L'Admin la lit seulement.
    read_roles=ALL_ROLES,
    write_roles=(HUNTER, MANAGER),
    create_roles=(CLIENT, HUNTER),
)
