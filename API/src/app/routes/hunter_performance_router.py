from ..models import HunterPerformance
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..services.hunter_performance_service import HunterPerformanceService
from .crud_router import build_crud_router

router = build_crud_router(
    service=HunterPerformanceService(HunterPerformanceRepository()),
    prefix="/hunter-performances",
    tag="hunter_performance",
    response_model=HunterPerformance,
    # ADR-035 : la performance d'un chasseur n'est jamais saisie à la main ;
    # POST et PUT fermés à tous ; la note 'payment' s'écrit quand un
    # paiement passe à 'paid' (PaymentService, fiche API12).
    write_roles=(),
)
