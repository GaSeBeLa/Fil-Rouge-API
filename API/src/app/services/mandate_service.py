from ..models import Mandate
from ..repositories.mandate_repository import MandateRepository
from .base_service import BaseService


class MandateService(BaseService[Mandate]):
    def __init__(self, repository: MandateRepository):
        super().__init__(repository, not_found_detail="Mandat introuvable")
