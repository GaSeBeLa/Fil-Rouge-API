from ..models import Estate
from ..repositories.estate_repository import EstateRepository
from ..services.estate_service import EstateService
from ..utils.roles import ADMIN, ALL_ROLES, HUNTER, MANAGER
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateService(EstateRepository()),
    prefix="/estates",
    tag="estate",
    response_model=Estate,
    # ADR-027, annexe § 3 : lu par tous ; modifié par l'Admin.
    read_roles=ALL_ROLES,
    write_roles=(ADMIN,),
    # ADR-047 : un bien saisi à la main l'est par un chasseur ou un manager.
    create_roles=(HUNTER, MANAGER),
)
