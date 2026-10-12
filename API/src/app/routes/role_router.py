from ..models import Role
from ..repositories.role_repository import RoleRepository
from ..services.role_service import RoleService
from ..utils.roles import ADMIN
from .crud_router import build_crud_router

router = build_crud_router(
    service=RoleService(RoleRepository()),
    prefix="/roles",
    tag="role",
    response_model=Role,
    # Admin seul écrit, comme /users : get_principal croit le libellé lu en
    # base, donc renommer un rôle en « Admin » donnait les droits d'Admin à
    # tous ses comptes (relecture de la série API).
    write_roles=(ADMIN,),
)
