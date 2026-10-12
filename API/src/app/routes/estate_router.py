from ..models import Estate
from ..repositories.estate_repository import EstateRepository
from ..services.estate_service import EstateService
from ..utils.roles import HUNTER, MANAGER
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateService(EstateRepository()),
    prefix="/estates",
    tag="estate",
    response_model=Estate,
    # ADR-047 : un bien saisi à la main l'est par un chasseur ou un manager.
    create_roles=(HUNTER, MANAGER),
)
