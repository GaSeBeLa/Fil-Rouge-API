from ..models import HunterRateParameters
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..services.hunter_rate_parameters_service import HunterRateParametersService
from .crud_router import build_crud_router

router = build_crud_router(
    service=HunterRateParametersService(HunterRateParametersRepository()),
    prefix="/hunter-rate-parameters",
    tag="hunter_rate_parameters",
    response_model=HunterRateParameters,
)
