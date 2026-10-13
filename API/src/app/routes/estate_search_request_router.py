from ..models import EstateSearchRequest
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..services.estate_search_request_service import EstateSearchRequestService
from ..utils.roles import ADMIN, CLIENT, HUNTER, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateSearchRequestService(EstateSearchRequestRepository()),
    prefix="/estate-search-requests",
    tag="estate_searchrequest",
    response_model=EstateSearchRequest,
    # ADR-027, annexe § 3 : le client lit l'avis sur sa demande (P5) ;
    # le chasseur l'écrit (H7). Le manager ne lit pas la sélection :
    # minimisation (REGISTRE-RGPD.md:9).
    read_roles=(ADMIN, CLIENT, HUNTER, READER),
    write_roles=(HUNTER,),
    # ADR-051 : la note est celle du chasseur qui la crée ; le service prend
    # son id dans le jeton (relecture de la série API6 → API10).
    create_roles=(HUNTER,),
)
