from ..models import Sale
from ..repositories.sale_repository import SaleRepository
from .base_service import BaseService


class SaleService(BaseService[Sale]):
    def __init__(self, repository: SaleRepository):
        super().__init__(repository, not_found_detail="Vente introuvable")
