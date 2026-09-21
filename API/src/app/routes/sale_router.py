from ..models import Sale
from ..repositories.sale_repository import SaleRepository
from ..services.sale_service import SaleService
from .crud_router import build_crud_router

router = build_crud_router(
    service=SaleService(SaleRepository()),
    prefix="/sales",
    tag="sale",
    response_model=Sale,
)
