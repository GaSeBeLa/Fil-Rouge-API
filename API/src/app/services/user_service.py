from ..models import User
from ..repositories.user_repository import UserRepository
from .base_service import BaseService


class UserService(BaseService[User]):
    def __init__(self, repository: UserRepository):
        super().__init__(repository, not_found_detail="Utilisateur introuvable")
