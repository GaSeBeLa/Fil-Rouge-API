from ..models import ParametersFees
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..services.parameters_fees_service import ParametersFeesService
from .crud_router import build_crud_router

router = build_crud_router(
    service=ParametersFeesService(ParametersFeesRepository()),
    prefix="/parameters-fees",
    tag="parameters_fees",
    response_model=ParametersFees,
)
