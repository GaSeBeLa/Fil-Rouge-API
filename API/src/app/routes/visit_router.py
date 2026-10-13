from ..models import Visit
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.visit_repository import VisitRepository
from ..services.visit_service import VisitService
from ..utils.roles import ADMIN, ALL_ROLES, HUNTER
from .crud_router import build_crud_router

router = build_crud_router(
    service=VisitService(VisitRepository(), MandateRepository(), EstateProposedRepository()),
    prefix="/visits",
    tag="visit",
    response_model=Visit,
    # ADR-027, annexe § 3 : créée par le chasseur (Q-ACC-13, à confirmer
    # par Jeff : Q-JEF-25) ; modifiée par l'Admin.
    read_roles=ALL_ROLES,
    write_roles=(ADMIN,),
    create_roles=(HUNTER,),
)
