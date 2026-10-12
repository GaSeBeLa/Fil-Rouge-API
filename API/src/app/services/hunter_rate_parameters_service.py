from ..models import HunterRateParameters
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.payment_repository import PaymentRepository
from .version_service import FrozenOnceCitedService


class HunterRateParametersService(FrozenOnceCitedService[HunterRateParameters]):
    """Une version des réglages citée par un paiement ne se modifie plus (ADR-034)."""

    def __init__(self, repository: HunterRateParametersRepository, payments: PaymentRepository):
        super().__init__(
            repository,
            not_found_detail="Réglages du taux du chasseur introuvables",
            cited_by=[(payments, "id_hunter_rate_parameters")],
        )
