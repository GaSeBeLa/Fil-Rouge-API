from ..models import Mandate
from ..repositories.mandate_repository import MandateRepository
from ..services.mandate_service import MandateService
from .crud_router import build_crud_router

router = build_crud_router(
    service=MandateService(MandateRepository()),
    prefix="/mandates",
    tag="mandate",
    response_model=Mandate,
)
