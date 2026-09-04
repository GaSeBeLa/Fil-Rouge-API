from ..models import Mandate
from .base_repository import BaseRepository


class MandateRepository(BaseRepository[Mandate]):
    def __init__(self):
        super().__init__(Mandate)
