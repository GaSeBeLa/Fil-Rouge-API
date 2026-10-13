from ..models import CommissionScale
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.payment_repository import PaymentRepository
from ..services.commission_scale_service import CommissionScaleService
from ..utils.roles import ADMIN, HUNTER, MANAGER, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=CommissionScaleService(CommissionScaleRepository(), PaymentRepository()),
    prefix="/commission-scales",
    tag="commission_scale",
    response_model=CommissionScale,
    # ADR-027, annexe § 4 : lu par le chasseur (F10:11, « vérifier son
    # montant »), le manager, l'Admin et Reader ; créé et modifié par
    # l'Admin seul (Q-ACC-07). Le client n'y a pas accès.
    read_roles=(ADMIN, HUNTER, MANAGER, READER),
    write_roles=(ADMIN,),
)
