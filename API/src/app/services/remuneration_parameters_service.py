from ..models import RemunerationParameters
from ..repositories.remuneration_parameters_repository import RemunerationParametersRepository
from .base_service import BaseService


class RemunerationParametersService(BaseService[RemunerationParameters]):
    def __init__(self, repository: RemunerationParametersRepository):
        super().__init__(repository, not_found_detail="Paramètres de rémunération introuvables")
