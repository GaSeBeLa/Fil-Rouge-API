from ..models import RealEstateManager
from ..repositories.real_estate_manager_repository import RealEstateManagerRepository
from ..services.real_estate_manager_service import RealEstateManagerService
from .crud_router import build_crud_router

router = build_crud_router(
    service=RealEstateManagerService(RealEstateManagerRepository()),
    prefix="/real-estate-managers",
    tag="real_estate_manager",
    response_model=RealEstateManager,
)
