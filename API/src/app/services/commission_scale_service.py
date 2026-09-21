from ..models import CommissionScale
from ..repositories.commission_scale_repository import CommissionScaleRepository
from .base_service import BaseService


class CommissionScaleService(BaseService[CommissionScale]):
    def __init__(self, repository: CommissionScaleRepository):
        super().__init__(repository, not_found_detail="Tranche de barème introuvable")
