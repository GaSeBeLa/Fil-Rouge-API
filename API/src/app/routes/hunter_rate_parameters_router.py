from ..models import HunterRateParameters
from ..repositories.hunter_rate_parameters_repository import HunterRateParametersRepository
from ..repositories.payment_repository import PaymentRepository
from ..services.hunter_rate_parameters_service import HunterRateParametersService
from ..utils.roles import ADMIN, HUNTER, MANAGER, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=HunterRateParametersService(HunterRateParametersRepository(), PaymentRepository()),
    prefix="/hunter-rate-parameters",
    tag="hunter_rate_parameters",
    response_model=HunterRateParameters,
    # ADR-027, annexe § 4 : lu par le chasseur (F10:11, « vérifier son
    # montant »), le manager, l'Admin et Reader ; créé et modifié par
    # l'Admin seul (par analogie avec
    # Q-ACC-07, comme ADR-034). Le client n'y a pas accès.
    read_roles=(ADMIN, HUNTER, MANAGER, READER),
    write_roles=(ADMIN,),
)
