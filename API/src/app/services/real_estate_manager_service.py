from ..models import RealEstateManager
from ..repositories.real_estate_manager_repository import RealEstateManagerRepository
from .base_service import BaseService


class RealEstateManagerService(BaseService[RealEstateManager]):
    def __init__(self, repository: RealEstateManagerRepository):
        super().__init__(repository, not_found_detail="Gestionnaire immobilier introuvable")
