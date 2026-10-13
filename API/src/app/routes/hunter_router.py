from ..models import Hunter
from ..repositories.hunter_repository import HunterRepository
from ..services.hunter_service import HunterService
from ..utils.roles import ADMIN, ALL_ROLES
from .crud_router import build_crud_router

router = build_crud_router(
    service=HunterService(HunterRepository()),
    prefix="/hunters",
    tag="hunter",
    response_model=Hunter,
    # ADR-027, annexe § 1 : lu par son client (P2), lui-même, son manager
    # (Q-ACC-02), l'Admin et Reader ; créé par l'Admin. Le chasseur
    # modifiera ses coordonnées en DRO6 : Admin seul d'ici là.
    read_roles=ALL_ROLES,
    write_roles=(ADMIN,),
)
