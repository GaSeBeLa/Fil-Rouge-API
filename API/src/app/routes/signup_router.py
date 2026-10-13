"""
signup_router.py — Dépôt d'une demande par le formulaire du site (P5).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
- POST /search-requests/submit : le formulaire (email, nom, téléphone,
  adresse) -> 202 et {"detail": "Demande reçue."}. Le compte et la fiche
  client sont créés avec la demande, dans la même transaction, si l'email
  est nouveau (services/signup_service.py).
- Même réponse pour tous : ni id, ni refus qui dirait que l'email existe
  (relecture de la série API6 → API10).
- Le visiteur n'a pas encore de compte : la route exige la clé d'API du
  site (`X-API-Key`, fiche API3), pas de jeton.
- Refus de la base en chemin (format du code postal, du téléphone…) : 409,
  et rien n'est écrit.
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..conf.database import get_session
from ..repositories.client_repository import ClientRepository
from ..repositories.role_repository import RoleRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..repositories.user_repository import UserRepository
from ..services.signup_service import SearchRequestSubmission, SignupService, SubmissionReceipt
from ..utils.api_keys import require_api_key
from ..utils.exceptions import ConflictError

router = APIRouter(
    prefix="/search-requests",
    tags=["search-requests"],
    dependencies=[Depends(require_api_key)],
)

_service = SignupService(UserRepository(), ClientRepository(), RoleRepository(), SearchRequestRepository())


@router.post(
    "/submit",
    response_model=SubmissionReceipt,
    status_code=202,
    summary="Déposer une demande depuis le site (sans compte)",
)
def submit(form: SearchRequestSubmission, session: Session = Depends(get_session)) -> SubmissionReceipt:
    """Le formulaire du site : un visiteur demande à être accompagné dans sa recherche.

    Il n'a pas encore de compte : la route demande la **clé d'API**, pas de jeton.

    Si l'email est nouveau, l'API crée **en une fois** le compte, la fiche client
    et la demande de recherche. Si une étape échoue, rien n'est écrit.

    La réponse est **la même pour tous** : elle ne dit pas si l'email existait
    déjà, pour ne pas renseigner un curieux.

    Réponses :

    - `202` : `{"detail": "Demande reçue."}` ;
    - `401` : clé d'API absente ou inconnue ;
    - `409` : la base refuse une valeur (format du téléphone, du code postal…) ;
    - `422` : le formulaire est mal rempli (champ obligatoire absent, email invalide).
    """
    try:
        _service.submit(session, form)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SubmissionReceipt()
