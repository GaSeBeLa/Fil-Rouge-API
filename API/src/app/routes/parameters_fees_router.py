from ..models import ParametersFees
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.sale_repository import SaleRepository
from ..services.parameters_fees_service import ParametersFeesService
from ..utils.roles import ADMIN, HUNTER, MANAGER, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=ParametersFeesService(ParametersFeesRepository(), SaleRepository()),
    prefix="/parameters-fees",
    tag="parameters_fees",
    response_model=ParametersFees,
    # ADR-027, annexe § 4 : lu par le chasseur (F10:11, « vérifier son
    # montant »), le manager, l'Admin et Reader ; créé et modifié par
    # l'Admin seul (Q-ACC-07). Le client n'y a pas accès.
    read_roles=(ADMIN, HUNTER, MANAGER, READER),
    write_roles=(ADMIN,),
)
