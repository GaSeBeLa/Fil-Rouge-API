from ..models import EstateProposed
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..services.estate_proposed_service import EstateProposedService
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateProposedService(EstateProposedRepository()),
    prefix="/estate-proposed",
    tag="estate_proposed",
    response_model=EstateProposed,
)
