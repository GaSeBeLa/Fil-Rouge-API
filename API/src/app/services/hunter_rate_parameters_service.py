from ..models import HunterRateParameters
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from .base_service import BaseService


class HunterRateParametersService(BaseService[HunterRateParameters]):
    def __init__(self, repository: HunterRateParametersRepository):
        super().__init__(repository, not_found_detail="Réglages du taux du chasseur introuvables")
