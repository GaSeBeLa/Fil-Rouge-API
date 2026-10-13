from ..models import HunterRateParameters
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.payment_repository import PaymentRepository
from ..services.hunter_rate_parameters_service import HunterRateParametersService
from ..utils.roles import ALL_ROLES, WRITER_ROLES
from .crud_router import build_crud_router

router = build_crud_router(
    service=HunterRateParametersService(HunterRateParametersRepository(), PaymentRepository()),
    prefix="/hunter-rate-parameters",
    tag="hunter_rate_parameters",
    response_model=HunterRateParameters,
    # DRO2 : les droits de l'argent se règlent à part ; ouvert comme
    # avant le moindre privilège (DRO1).
    read_roles=ALL_ROLES,
    write_roles=WRITER_ROLES,
)
