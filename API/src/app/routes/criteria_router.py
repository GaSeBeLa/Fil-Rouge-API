from ..models import Criteria
from ..repositories.criteria_repository import CriteriaRepository
from ..services.criteria_service import CriteriaService
from ..utils.roles import ALL_ROLES, CLIENT, HUNTER
from .crud_router import build_crud_router

router = build_crud_router(
    service=CriteriaService(CriteriaRepository()),
    prefix="/criteria",
    tag="criteria",
    response_model=Criteria,
    # ADR-027, annexe § 2 : créés par le client (P1) ou le chasseur (H4).
    # Aucune modification : un critère change par une nouvelle version
    # (ADR-027, point 5).
    read_roles=ALL_ROLES,
    write_roles=(),
    create_roles=(CLIENT, HUNTER),
)
