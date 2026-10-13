"""
auth_router.py — Connexion par jeton JWT (ADR-052).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
- POST /auth/login : email + mot de passe -> un jeton valable 60 minutes.
  Mauvais identifiants ou compte non activé : 401, même message, pour ne
  pas dire à un inconnu quels emails existent.
- get_current_user, la dépendance des routes protégées, vit dans
  utils/current_user.py : elle relit le compte en base à chaque appel
  (ADR-052, décision 3).
- Toutes ces routes exigent aussi la clé d'API du programme appelant
  (`X-API-Key`, ADR-028 points 4 à 6, utils/api_keys.py), login compris.
- GET /auth/me : le compte du jeton présenté.
============================================================================
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, SQLModel

from ..conf.database import get_session
from ..models import User, UserPublic
from ..repositories.user_repository import UserRepository
from ..services.user_service import UserService
from ..utils.api_keys import require_api_key
from ..utils.current_user import get_current_user, unauthorized
from ..utils.security import ACCESS_TOKEN_TTL, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(require_api_key)])

_service = UserService(UserRepository())

_BAD_CREDENTIALS = "Email ou mot de passe incorrect, ou compte non activé."


class LoginRequest(SQLModel):
    email: str
    password: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes


# Clé d'API sans jeton, par nature : c'est elle qui délivre le jeton
# (ADR-028, ADR-052). Elle ne rend que le jeton du compte dont on a donné le
# mot de passe, et ce jeton ne porte que son id (`sub`) : ni email, ni rôle.
# Tout échec rend le même 401. Revue en DRO3 : inchangée.
@router.post("/login", response_model=TokenResponse, summary="Se connecter et recevoir un jeton")
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    """Échange un email et un mot de passe contre un **jeton** (JWT), valable 60 minutes.

    C'est la première route à appeler : toutes les autres demandent ce jeton.

    Dans le Swagger :

    1. **Authorize** → champ `APIKeyHeader` : la clé d'API (`X-API-Key`).
    2. Appeler cette route avec votre email et votre mot de passe.
    3. Copier `access_token` de la réponse.
    4. **Authorize** → champ `HTTPBearer` : coller le jeton seul, sans le mot `Bearer`.

    Réponses :

    - `200` : le jeton (`access_token`) et sa durée en secondes (`expires_in`) ;
    - `401` : clé d'API absente, email ou mot de passe faux, ou compte pas encore
      activé. Le message ne dit pas lequel, exprès (ADR-052).
    """
    user = _service.authenticate(session, body.email, body.password)
    if user is None or user.id is None:
        raise unauthorized(_BAD_CREDENTIALS)
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
    )


# Tout compte connecté, et son compte seul : l'id vient du jeton
# (get_current_user), jamais de l'URL ni du corps ; UserPublic retire
# `password`. Revue en DRO3 : inchangée.
@router.get("/me", response_model=UserPublic, summary="Voir le compte connecté")
def me(user: User = Depends(get_current_user)) -> User:
    """Rend le compte à qui appartient le jeton : pratique pour vérifier qui est connecté.

    Le mot de passe n'est jamais renvoyé.

    Réponses :

    - `200` : le compte ;
    - `401` : clé d'API ou jeton absent, inconnu ou expiré.
    """
    return user
