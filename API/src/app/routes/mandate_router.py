from ..models import Mandate
from ..repositories.mandate_repository import MandateRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..services.mandate_service import MandateService
from .crud_router import build_crud_router

router = build_crud_router(
    service=MandateService(MandateRepository(), SearchRequestRepository()),
    prefix="/mandates",
    tag="mandate",
    response_model=Mandate,
)
