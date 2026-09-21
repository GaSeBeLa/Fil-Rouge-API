from ..models import Payment
from ..repositories.payment_repository import PaymentRepository
from ..services.payment_service import PaymentService
from .crud_router import build_crud_router

router = build_crud_router(
    service=PaymentService(PaymentRepository()),
    prefix="/payments",
    tag="payment",
    response_model=Payment,
)
