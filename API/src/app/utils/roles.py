"""
roles.py — Le mécanisme des rôles (ADR-028), pas la matrice (ADR-027).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
- get_principal : le compte connecté, le libellé de son rôle ET le numéro
  de sa fiche (profile_id), relus en base à chaque appel (ADR-052,
  décision 3), par les services. C'est la dépendance que les fixtures de
  test remplacent pour se connecter en `Admin` d'office.
- profile_id : client.id, hunter.id ou real_estate_manager.id du compte,
  selon son rôle ; None sans fiche (Admin, Reader). C'est lui que citent
  les id_client, id_hunter et id_realestatemanager des autres tables
  depuis le chantier PRF (2026-10-15), pas user.id. Jamais dans le jeton.
- require_roles(*roles) : une dépendance qui rend 403 si le rôle du compte
  connecté n'est pas dans la liste. Sans jeton, get_current_user a déjà
  rendu 401 avant.

La matrice d'ADR-027 se déclare table par table, dans chaque routeur
(`read_roles`, `write_roles`, `create_roles` de build_crud_router) : fermé
par défaut (fiche DRO1). `Reader` lit sans écrire (ADR-028).
============================================================================
"""

from collections.abc import Callable
from typing import NamedTuple, Optional

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from ..conf.database import get_session
from ..models import Client, Hunter, RealEstateManager, User
from ..repositories.role_repository import RoleRepository
from ..services.role_service import RoleService
from .current_user import get_current_user
from .exceptions import NotFoundError

# Les 5 libellés de la table role (CHECK en base, ADR-028 point 7).
ADMIN = "Admin"
CLIENT = "Client"
HUNTER = "Hunter"
MANAGER = "Manager"
READER = "Reader"

ALL_ROLES: tuple[str, ...] = (ADMIN, CLIENT, HUNTER, MANAGER, READER)
# ADR-028 : `Reader` consulte sans écrire.
WRITER_ROLES: tuple[str, ...] = (ADMIN, CLIENT, HUNTER, MANAGER)


_roles = RoleService(RoleRepository())


# La table de fiche de chaque rôle qui en a une (chantier PRF).
PROFILE_MODELS = {CLIENT: Client, HUNTER: Hunter, MANAGER: RealEstateManager}


class Principal(NamedTuple):
    """Le compte connecté, le libellé de son rôle du moment et le numéro de sa fiche."""

    user: User
    role: str
    profile_id: Optional[int] = None

    @property
    def is_admin(self) -> bool:
        """L'Admin voit toutes les lignes des tables qu'il lit (ADR-027, fiche DRO4)."""
        return self.role == ADMIN


def get_principal(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Principal:
    # id_role est une clé étrangère NOT NULL : un rôle introuvable serait une
    # base incohérente ; on refuse plutôt que d'accorder un droit au hasard.
    try:
        role = _roles.get_by_id(session, user.id_role)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rôle du compte introuvable.")
    return Principal(user=user, role=role.wording, profile_id=profile_id_of(session, user, role.wording))


def profile_id_of(session: Session, user: User, role: str) -> Optional[int]:
    """Le numéro de la fiche du compte pour son rôle, None sans fiche (chantier PRF)."""
    model = PROFILE_MODELS.get(role)
    if model is None:
        return None
    return session.exec(select(model.id).where(model.id_user == user.id)).first()


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
