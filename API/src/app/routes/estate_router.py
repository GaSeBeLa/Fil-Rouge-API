from ..models import Estate
from ..repositories.estate_repository import EstateRepository
from ..services.estate_service import EstateService
from .crud_router import build_crud_router

router = build_crud_router(
    service=EstateService(EstateRepository()),
    prefix="/estates",
    tag="estate",
    response_model=Estate,
)
