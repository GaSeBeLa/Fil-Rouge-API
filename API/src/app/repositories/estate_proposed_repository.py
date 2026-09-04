from ..models import EstateProposed
from .base_repository import BaseRepository


class EstateProposedRepository(BaseRepository[EstateProposed]):
    def __init__(self):
        super().__init__(EstateProposed)
