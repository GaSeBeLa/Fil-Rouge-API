from ..models import CommissionScale
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.payment_repository import PaymentRepository
from .version_service import FrozenOnceCitedService


class CommissionScaleService(FrozenOnceCitedService[CommissionScale]):
    """Une ligne de barème citée par un paiement ne se modifie plus (ADR-034)."""

    def __init__(self, repository: CommissionScaleRepository, payments: PaymentRepository):
        super().__init__(
            repository,
            not_found_detail="Tranche de barème introuvable",
            cited_by=[(payments, "id_commission_scale")],
        )
