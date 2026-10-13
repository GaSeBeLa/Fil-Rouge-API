from ..models import Picture
from ..repositories.picture_repository import PictureRepository
from ..services.picture_service import PictureService
from ..utils.roles import ADMIN, ALL_ROLES, HUNTER, MANAGER
from .crud_router import build_crud_router

router = build_crud_router(
    service=PictureService(PictureRepository()),
    prefix="/pictures",
    tag="picture",
    response_model=Picture,
    # ADR-027, annexe § 3, comme estate : saisie à la main par un
    # chasseur ou un manager (Q8, ADR-047) ; modifiée par l'Admin.
    read_roles=ALL_ROLES,
    write_roles=(ADMIN,),
    create_roles=(HUNTER, MANAGER),
)
