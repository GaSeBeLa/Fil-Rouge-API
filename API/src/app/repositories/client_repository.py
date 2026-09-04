from ..models import Client
from .base_repository import BaseRepository


class ClientRepository(BaseRepository[Client]):
    def __init__(self):
        super().__init__(Client)
