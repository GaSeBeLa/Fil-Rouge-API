from ..models import Role
from ..repositories.role_repository import RoleRepository
from .base_service import BaseService


class RoleService(BaseService[Role]):
    def __init__(self, repository: RoleRepository):
        super().__init__(repository, not_found_detail="Rôle introuvable")
