from ..models import RemunerationParameters
from ..repositories.remuneration_parameters_repository import RemunerationParametersRepository
from ..services.remuneration_parameters_service import RemunerationParametersService
from .crud_router import build_crud_router

router = build_crud_router(
    service=RemunerationParametersService(RemunerationParametersRepository()),
    prefix="/remuneration-parameters",
    tag="remuneration_parameters",
    response_model=RemunerationParameters,
)
