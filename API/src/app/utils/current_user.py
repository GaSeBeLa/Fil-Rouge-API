"""
current_user.py — Le compte connecté, relu en base à chaque appel (ADR-052).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
get_current_user est la dépendance FastAPI que les routes protégées
déclarent (directement, ou via get_principal dans utils/roles.py). Elle lit
`Authorization: Bearer <jeton>`, puis RELIT l'utilisateur par UserService :
son rôle et son activation du moment font foi, pas ce que disait le jeton à
son émission (ADR-052, décision 3). Un compte désactivé perd donc ses droits
au prochain appel (ADR-049).

Elle vit dans utils/ et non dans routes/auth_router.py : utils/roles.py en
dépend, et utils/ n'importe jamais routes/ (les couches ne se lisent que
vers le bas : routes -> services -> repositories).
============================================================================
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from ..conf.database import get_session
from ..models import User
from ..repositories.user_repository import UserRepository
from ..services.user_service import UserService
from .exceptions import NotFoundError
from .security import InvalidTokenError, decode_access_token

_users = UserService(UserRepository())

# auto_error=False : sans en-tête, HTTPBearer rendrait sa propre erreur ;
# on veut le même 401 que pour un jeton refusé.
_bearer = HTTPBearer(auto_error=False)

BAD_TOKEN = "Jeton absent, invalide ou expiré, ou compte désactivé."


def unauthorized(detail: str) -> HTTPException:
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
        raise unauthorized(BAD_TOKEN)
    try:
        user = _users.get_by_id(session, decode_access_token(credentials.credentials))
    except (InvalidTokenError, NotFoundError):
        raise unauthorized(BAD_TOKEN)
    if not user.is_activated:
        raise unauthorized(BAD_TOKEN)
    return user
