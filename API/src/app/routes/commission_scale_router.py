from ..models import CommissionScale
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.payment_repository import PaymentRepository
from ..services.commission_scale_service import CommissionScaleService
from ..utils.roles import ALL_ROLES, WRITER_ROLES
from .crud_router import build_crud_router

router = build_crud_router(
    service=CommissionScaleService(CommissionScaleRepository(), PaymentRepository()),
    prefix="/commission-scales",
    tag="commission_scale",
    response_model=CommissionScale,
    # DRO2 : les droits de l'argent se règlent à part ; ouvert comme
    # avant le moindre privilège (DRO1).
    read_roles=ALL_ROLES,
    write_roles=WRITER_ROLES,
)
