from ..models import Hunter
from ..repositories.hunter_repository import HunterRepository
from ..services.hunter_service import HunterService
from .crud_router import build_crud_router

router = build_crud_router(
    service=HunterService(HunterRepository()),
    prefix="/hunters",
    tag="hunter",
    response_model=Hunter,
)
