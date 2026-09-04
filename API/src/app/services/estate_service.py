from ..models import Estate
from ..repositories.estate_repository import EstateRepository
from .base_service import BaseService


class EstateService(BaseService[Estate]):
    def __init__(self, repository: EstateRepository):
        super().__init__(repository, not_found_detail="Bien introuvable")
