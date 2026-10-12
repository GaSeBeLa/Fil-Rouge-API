"""
auth_router.py — Connexion par jeton JWT (ADR-052).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
- POST /auth/login : email + mot de passe -> un jeton valable 60 minutes.
  Mauvais identifiants ou compte non activé : 401, même message, pour ne
  pas dire à un inconnu quels emails existent.
- get_current_user : la dépendance que les routes protégées déclarent.
  Elle lit `Authorization: Bearer <jeton>`, puis RELIT l'utilisateur en
  base : son rôle et son activation du moment font foi, pas ce que disait
  le jeton à son émission (ADR-052, décision 3). Un compte désactivé perd
  donc ses droits au prochain appel (ADR-049).
- GET /auth/me : le compte du jeton présenté. Seule route protégée pour
  l'instant ; le branchement sur les routes CRUD est la fiche API2.
============================================================================
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, SQLModel

from ..conf.database import get_session
from ..models import User, UserPublic
from ..repositories.user_repository import UserRepository
from ..services.user_service import UserService
from ..utils.security import (
    ACCESS_TOKEN_TTL,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_service = UserService(UserRepository())

# auto_error=False : sans en-tête, HTTPBearer rendrait sa propre erreur ;
# on veut le même 401 que pour un jeton refusé.
_bearer = HTTPBearer(auto_error=False)

_BAD_CREDENTIALS = "Email ou mot de passe incorrect, ou compte non activé."
_BAD_TOKEN = "Jeton absent, invalide ou expiré, ou compte désactivé."


class LoginRequest(SQLModel):
    email: str
    password: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    """Le compte du jeton, relu en base à chaque appel (ADR-052, décision 3)."""
    if credentials is None:
        raise _unauthorized(_BAD_TOKEN)
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _unauthorized(_BAD_TOKEN)

    user = _service.repository.get_by_id(session, user_id)
    if user is None or not user.is_activated:
        raise _unauthorized(_BAD_TOKEN)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = _service.authenticate(session, body.email, body.password)
    if user is None or user.id is None:
        raise _unauthorized(_BAD_CREDENTIALS)
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
    )


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user
