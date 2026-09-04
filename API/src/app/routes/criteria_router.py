from ..models import Criteria
from ..repositories.criteria_repository import CriteriaRepository
from ..services.criteria_service import CriteriaService
from .crud_router import build_crud_router

router = build_crud_router(
    service=CriteriaService(CriteriaRepository()),
    prefix="/criteria",
    tag="criteria",
    response_model=Criteria,
)
