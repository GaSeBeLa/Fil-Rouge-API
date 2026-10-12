"""
signup_router.py — Dépôt d'une demande par le formulaire du site (P5).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
- POST /search-requests/submit : le formulaire (email, nom, téléphone,
  adresse) -> la search_request créée, 201. Le compte et la fiche client
  sont créés avec elle, dans la même transaction, si l'email est nouveau
  (services/signup_service.py).
- Le visiteur n'a pas encore de compte : la route exige la clé d'API du
  site (`X-API-Key`, fiche API3), pas de jeton.
- Refus de la base en chemin (format du code postal, du téléphone…) : 409,
  et rien n'est écrit.
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..conf.database import get_session
from ..models import SearchRequest
from ..repositories.client_repository import ClientRepository
from ..repositories.role_repository import RoleRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..repositories.user_repository import UserRepository
from ..services.signup_service import SearchRequestSubmission, SignupService
from ..utils.api_keys import require_api_key
from ..utils.exceptions import ConflictError

router = APIRouter(
    prefix="/search-requests",
    tags=["search-requests"],
    dependencies=[Depends(require_api_key)],
)

_service = SignupService(UserRepository(), ClientRepository(), RoleRepository(), SearchRequestRepository())


@router.post("/submit", response_model=SearchRequest, status_code=201)
def submit(form: SearchRequestSubmission, session: Session = Depends(get_session)) -> SearchRequest:
    try:
        return _service.submit(session, form)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
