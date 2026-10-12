from ..models import ParametersFees
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.sale_repository import SaleRepository
from .version_service import FrozenOnceCitedService


class ParametersFeesService(FrozenOnceCitedService[ParametersFees]):
    """Une grille citée par une vente ne se modifie plus (ADR-030)."""

    def __init__(self, repository: ParametersFeesRepository, sales: SaleRepository):
        super().__init__(
            repository,
            not_found_detail="Paramètre d'honoraires introuvable",
            cited_by=[(sales, "id_parameters_fees")],
        )
