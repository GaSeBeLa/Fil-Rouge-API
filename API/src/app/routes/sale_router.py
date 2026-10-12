from ..models import Sale
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.sale_repository import SaleRepository
from ..services.sale_service import SaleService
from .crud_router import build_crud_router

router = build_crud_router(
    service=SaleService(SaleRepository(), MandateRepository(), EstateProposedRepository(), ParametersFeesRepository()),
    prefix="/sales",
    tag="sale",
    response_model=Sale,
)
