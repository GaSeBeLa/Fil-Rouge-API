from ..models import ParametersFees
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.sale_repository import SaleRepository
from ..services.parameters_fees_service import ParametersFeesService
from ..utils.roles import ALL_ROLES, WRITER_ROLES
from .crud_router import build_crud_router

router = build_crud_router(
    service=ParametersFeesService(ParametersFeesRepository(), SaleRepository()),
    prefix="/parameters-fees",
    tag="parameters_fees",
    response_model=ParametersFees,
    # DRO2 : les droits de l'argent se règlent à part ; ouvert comme
    # avant le moindre privilège (DRO1).
    read_roles=ALL_ROLES,
    write_roles=WRITER_ROLES,
)
