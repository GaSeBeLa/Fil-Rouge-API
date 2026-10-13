from ..models import RealEstateManager
from ..repositories.real_estate_manager_repository import RealEstateManagerRepository
from ..services.real_estate_manager_service import RealEstateManagerService
from ..utils.roles import ADMIN, HUNTER, MANAGER, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=RealEstateManagerService(RealEstateManagerRepository()),
    prefix="/real-estate-managers",
    tag="real_estate_manager",
    response_model=RealEstateManager,
    # ADR-027, annexe § 1 : lu par ses chasseurs, lui-même, l'Admin et
    # Reader ; créé par l'Admin. Le manager modifie ses coordonnées
    # seulement (RealEstateManagerService, CONTACT_FIELDS -> 403 ; DRO7).
    read_roles=(ADMIN, HUNTER, MANAGER, READER),
    write_roles=(ADMIN, MANAGER),
    create_roles=(ADMIN,),
)
