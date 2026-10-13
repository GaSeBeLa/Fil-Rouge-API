from ..models import Mandate
from ..repositories.mandate_repository import MandateRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..services.mandate_service import MandateService
from ..utils.roles import ADMIN, ALL_ROLES, CLIENT, HUNTER
from .crud_router import build_crud_router

router = build_crud_router(
    service=MandateService(MandateRepository(), SearchRequestRepository()),
    prefix="/mandates",
    tag="mandate",
    response_model=Mandate,
    # ADR-027, annexe § 2 : créé par le chasseur (H4) ; modifié par le
    # client (signer : P3), le chasseur et l'Admin.
    read_roles=ALL_ROLES,
    write_roles=(ADMIN, CLIENT, HUNTER),
    create_roles=(HUNTER,),
)
