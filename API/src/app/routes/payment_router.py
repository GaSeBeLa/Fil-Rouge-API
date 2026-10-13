from ..models import Payment
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.hunter_repository import HunterRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.payment_repository import PaymentRepository
from ..repositories.sale_repository import SaleRepository
from ..repositories.visit_repository import VisitRepository
from ..services.parametrage_service import ParametrageService
from ..services.payment_calculation_service import PaymentCalculationService
from ..services.payment_service import PaymentService
from ..utils.roles import ADMIN, HUNTER, MANAGER
from .crud_router import build_crud_router

# Fiche API12 : le calcul branché sur la base. Partagé avec sale_router.py,
# qui crée le paiement d'une vente (POST /sales/{id}/payment).
calculation = PaymentCalculationService(
    SaleRepository(),
    MandateRepository(),
    VisitRepository(),
    HunterRepository(),
    PaymentRepository(),
    CommissionScaleRepository(),
    HunterRateParametersRepository(),
    ParametrageService(ParametersFeesRepository(), CommissionScaleRepository(), HunterRateParametersRepository()),
)
# ADR-035 : le passage à 'paid' écrit la note du journal (journal, performances).
payment_service = PaymentService(
    PaymentRepository(),
    HunterRateParametersRepository(),
    journal=calculation,
    performances=HunterPerformanceRepository(),
)

router = build_crud_router(
    service=payment_service,
    prefix="/payments",
    tag="payment",
    response_model=Payment,
    # ADR-027, annexe § 4 : lu par le chasseur (H10), son manager
    # (Q-ACC-02) et l'Admin ; ni Client ni Reader (point 8). Jamais saisi
    # à la main (point 10) : POST fermé à tous, le paiement naît du calcul
    # (POST /sales/{id}/payment). L'Admin le fait avancer : programmé, payé.
    read_roles=(ADMIN, HUNTER, MANAGER),
    write_roles=(ADMIN,),
    create_roles=(),
)
