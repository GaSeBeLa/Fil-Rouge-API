from ..models import User, UserPublic
from ..repositories.user_repository import UserRepository
from ..services.user_service import UserService
from .crud_router import build_crud_router

router = build_crud_router(
    service=UserService(UserRepository()),
    prefix="/users",
    tag="user",
    response_model=User,
    # Les réponses passent par UserPublic : `password` ne sort jamais.
    read_model=UserPublic,
)
