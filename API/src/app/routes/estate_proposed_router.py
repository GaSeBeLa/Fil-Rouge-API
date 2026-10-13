from ..models import EstateProposed
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.mandate_repository import MandateRepository
from ..services.estate_proposed_service import EstateProposedService
from ..utils.roles import ADMIN, CLIENT, HUNTER, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateProposedService(EstateProposedRepository(), MandateRepository(), EstateSearchRequestRepository()),
    prefix="/estate-proposed",
    tag="estate_proposed",
    response_model=EstateProposed,
    # ADR-027, annexe § 3 : proposé par le chasseur (H5, H9) ; le client
    # commente, priorise, fait une offre (H6, H8). Le manager ne lit pas
    # la sélection : minimisation (REGISTRE-RGPD.md:9).
    read_roles=(ADMIN, CLIENT, HUNTER, READER),
    write_roles=(CLIENT, HUNTER),
    create_roles=(HUNTER,),
)
