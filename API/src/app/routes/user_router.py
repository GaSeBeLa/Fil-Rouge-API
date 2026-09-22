from ..models import UserCreate, UserPublic, UserUpdate
from ..repositories.user_repository import UserRepository
from ..services.user_service import UserService
from .crud_router import build_crud_router

router = build_crud_router(
    service=UserService(UserRepository()),
    prefix="/users",
    tag="user",
    # ENTRÉE POST : UserCreate — ni id, ni created_at, mot de passe complet
    # en clair, haché par le service (ADR-016).
    response_model=UserCreate,
    # ENTRÉE PUT : UserUpdate — tous les champs optionnels, mise à jour
    # partielle réelle (voir UserService.replace).
    update_model=UserUpdate,
    # SORTIE : UserPublic — `password` ne sort jamais.
    read_model=UserPublic,
)