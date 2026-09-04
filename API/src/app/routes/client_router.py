from ..models import Client
from ..repositories.client_repository import ClientRepository
from ..services.client_service import ClientService
from .crud_router import build_crud_router

router = build_crud_router(
    service=ClientService(ClientRepository()),
    prefix="/clients",
    tag="client",
    response_model=Client,
)
