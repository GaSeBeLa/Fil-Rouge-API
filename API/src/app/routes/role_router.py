from ..models import Role
from ..repositories.role_repository import RoleRepository
from ..services.role_service import RoleService
from ..utils.roles import ADMIN, READER
from .crud_router import build_crud_router

router = build_crud_router(
    service=RoleService(RoleRepository()),
    prefix="/roles",
    tag="role",
    response_model=Role,
    # ADR-027, annexe § 1 : l'Admin et Reader lisent ; personne n'écrit,
    # les 3 rôles à fiche sont posés par le seed (CHECK en base, chantier PRF).
    # Écrire ici serait dangereux : get_principal croit le libellé lu en
    # base, donc renommer un rôle en « Admin » donnait les droits d'Admin
    # à tous ses comptes (relecture de la série API).
    read_roles=(ADMIN, READER),
    write_roles=(),
)
