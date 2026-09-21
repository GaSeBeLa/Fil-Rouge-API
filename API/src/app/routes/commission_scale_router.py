from ..models import CommissionScale
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..services.commission_scale_service import CommissionScaleService
from .crud_router import build_crud_router

router = build_crud_router(
    service=CommissionScaleService(CommissionScaleRepository()),
    prefix="/commission-scales",
    tag="commission_scale",
    response_model=CommissionScale,
)
