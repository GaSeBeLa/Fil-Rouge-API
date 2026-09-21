from ..models import Payment
from ..repositories.payment_repository import PaymentRepository
from .base_service import BaseService


class PaymentService(BaseService[Payment]):
    def __init__(self, repository: PaymentRepository):
        super().__init__(repository, not_found_detail="Versement introuvable")
