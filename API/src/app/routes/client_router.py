from ..models import Client
from ..repositories.client_repository import ClientRepository
from ..services.client_service import ClientService
from ..utils.roles import ADMIN, CLIENT, HUNTER, READER
from ..models.field_descriptions import CLIENT_ID
from .crud_router import build_crud_router

router = build_crud_router(
    service=ClientService(ClientRepository()),
    prefix="/clients",
    tag="client",
    response_model=Client,
    # ADR-027, annexe § 1 : lu par le client, son chasseur (H3), l'Admin
    # et Reader ; créé par le client (Q-ACC-12) ; modifié par le client
    # et l'Admin. Le manager n'y a pas accès. « Le sien » : DRO5.
    read_roles=(ADMIN, CLIENT, HUNTER, READER),
    write_roles=(ADMIN, CLIENT),
    create_roles=(CLIENT,),
    item_id_description=CLIENT_ID,
)
