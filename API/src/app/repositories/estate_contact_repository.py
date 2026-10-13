from ..models import EstateContact
from .base_repository import BaseRepository


class EstateContactRepository(BaseRepository[EstateContact]):
    def __init__(self):
        super().__init__(EstateContact)
