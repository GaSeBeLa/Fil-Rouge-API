from ..models import Role
from ..repositories.role_repository import RoleRepository
from ..services.role_service import RoleService
from .crud_router import build_crud_router

router = build_crud_router(
    service=RoleService(RoleRepository()),
    prefix="/roles",
    tag="role",
    response_model=Role,
)
