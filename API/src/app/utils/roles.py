"""
roles.py — Le mécanisme des rôles (ADR-028), pas la matrice (ADR-027).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
- get_principal : le compte connecté, le libellé de son rôle ET le numéro
  de sa fiche (profile_id), relus en base à chaque appel (ADR-052,
  décision 3), par les services. C'est la dépendance que les fixtures de
  test remplacent pour se connecter en `Admin` d'office.
- Le rôle (chantier PRF, PRF7) : user.system_role (Admin, Reader) pour un
  compte sans fiche ; sinon role_wording de sa fiche (client, hunter ou
  real_estate_manager) ; ni l'un ni l'autre : 403 (user.id_role, retiré
  par PRF8, n'est plus lu depuis PRF7). Une fiche au plus par compte, et
  aucune avec un system_role : le trigger check_one_profile_per_user (PRF6).
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
from .current_user import get_current_user

# Les 5 libellés de la table role (CHECK en base, ADR-028 point 7).
ADMIN = "Admin"
CLIENT = "Client"
HUNTER = "Hunter"
MANAGER = "Manager"
READER = "Reader"

ALL_ROLES: tuple[str, ...] = (ADMIN, CLIENT, HUNTER, MANAGER, READER)
# ADR-028 : `Reader` consulte sans écrire.
WRITER_ROLES: tuple[str, ...] = (ADMIN, CLIENT, HUNTER, MANAGER)


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
    # PRF7 : system_role d'abord (compte sans fiche), puis la fiche du compte.
    if user.system_role is not None:
        return Principal(user=user, role=user.system_role)
    for model in PROFILE_MODELS.values():
        row = session.exec(select(model.id, model.role_wording).where(model.id_user == user.id)).first()
        if row is not None:
            profile_id, role = row
            return Principal(user=user, role=role, profile_id=profile_id)
    # Ni fiche ni system_role : aucun droit plutôt qu'un droit au hasard.
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte sans rôle : ni fiche, ni system_role.")


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
