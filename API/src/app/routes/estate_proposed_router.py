from ..models import EstateProposed
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.mandate_repository import MandateRepository
from ..services.estate_proposed_service import EstateProposedService
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateProposedService(EstateProposedRepository(), MandateRepository(), EstateSearchRequestRepository()),
    prefix="/estate-proposed",
    tag="estate_proposed",
    response_model=EstateProposed,
)
