"""
roles.py — Le mécanisme des rôles (ADR-028), pas la matrice (ADR-027).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
- get_principal : le compte connecté ET le libellé de son rôle, relus en
  base à chaque appel (ADR-052, décision 3). C'est la dépendance que les
  fixtures de test remplacent pour se connecter en `Admin` d'office.
- require_roles(*roles) : une dépendance qui rend 403 si le rôle du compte
  connecté n'est pas dans la liste. Sans jeton, get_current_user a déjà
  rendu 401 avant.

Tant que la matrice d'ADR-027 attend le client, seules les règles des ADR
acceptés s'appliquent : `Reader` lit sans écrire (ADR-028) ; tout le reste
est ouvert à tout compte connecté.
============================================================================
"""

from collections.abc import Callable
from typing import NamedTuple

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from ..conf.database import get_session
from ..models import Role, User
from ..routes.auth_router import get_current_user

# Les 5 libellés de la table role (CHECK en base, ADR-028 point 7).
ADMIN = "Admin"
CLIENT = "Client"
HUNTER = "Hunter"
MANAGER = "Manager"
READER = "Reader"

ALL_ROLES: tuple[str, ...] = (ADMIN, CLIENT, HUNTER, MANAGER, READER)
# ADR-028 : `Reader` consulte sans écrire.
WRITER_ROLES: tuple[str, ...] = (ADMIN, CLIENT, HUNTER, MANAGER)


class Principal(NamedTuple):
    """Le compte connecté et le libellé de son rôle du moment."""

    user: User
    role: str


def get_principal(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Principal:
    role = session.get(Role, user.id_role)
    # id_role est une clé étrangère NOT NULL : un rôle introuvable serait une
    # base incohérente ; on refuse plutôt que d'accorder un droit au hasard.
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rôle du compte introuvable.")
    return Principal(user=user, role=role.wording)


def require_roles(*allowed: str) -> Callable[..., Principal]:
    """
    Dépendance FastAPI : 403 si le rôle connecté n'est pas dans `allowed`.
    `require_roles()` sans argument refuse tout le monde (route fermée).
    """

    def _check(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action interdite au rôle {principal.role}.",
            )
        return principal

    return _check
