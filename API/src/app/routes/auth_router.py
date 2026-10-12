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


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = _service.authenticate(session, body.email, body.password)
    if user is None or user.id is None:
        raise unauthorized(_BAD_CREDENTIALS)
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
    )


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user
