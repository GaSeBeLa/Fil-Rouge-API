from ..models import Client
from ..repositories.client_repository import ClientRepository
from .base_service import BaseService


class ClientService(BaseService[Client]):
    def __init__(self, repository: ClientRepository):
        super().__init__(repository, not_found_detail="Client introuvable")
