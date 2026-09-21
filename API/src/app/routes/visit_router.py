from ..models import Visit
from ..repositories.visit_repository import VisitRepository
from ..services.visit_service import VisitService
from .crud_router import build_crud_router

router = build_crud_router(
    service=VisitService(VisitRepository()),
    prefix="/visits",
    tag="visit",
    response_model=Visit,
)
