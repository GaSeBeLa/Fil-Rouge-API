from ..models import Hunter
from ..repositories.hunter_repository import HunterRepository
from .base_service import BaseService


class HunterService(BaseService[Hunter]):
    def __init__(self, repository: HunterRepository):
        super().__init__(repository, not_found_detail="Chasseur introuvable")
