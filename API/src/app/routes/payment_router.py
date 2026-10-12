from ..models import Payment
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.payment_repository import PaymentRepository
from ..services.payment_service import PaymentService
from .crud_router import build_crud_router

router = build_crud_router(
    service=PaymentService(PaymentRepository(), HunterRateParametersRepository()),
    prefix="/payments",
    tag="payment",
    response_model=Payment,
)
