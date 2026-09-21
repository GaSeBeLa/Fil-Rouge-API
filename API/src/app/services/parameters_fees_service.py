from ..models import ParametersFees
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from .base_service import BaseService


class ParametersFeesService(BaseService[ParametersFees]):
    def __init__(self, repository: ParametersFeesRepository):
        super().__init__(repository, not_found_detail="Paramètre d'honoraires introuvable")
