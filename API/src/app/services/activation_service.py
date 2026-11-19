"""
activation_service.py — Le particulier finalise lui-même son compte (user story 01).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le formulaire du site (signup_service.py, P5) crée un compte inactif, au
mot de passe factice PENDING_SIGNUP_PASSWORD. La user story 01
(@creation-compte) veut que le particulier le finalise LUI-MÊME, après
l'affectation de son chasseur. Avant ce fichier, seul un Admin pouvait
l'activer (trou trouvé par Gabriel le 2026-11-19).

Deux gestes :
1. issue_code : l'Admin, ou le Manager qui gère une demande de ce client,
   obtient un code d'activation (security.create_activation_token, 7 jours).
   Faute de serveur d'email, l'API le rend à l'appelant ; dans la vraie vie,
   c'est le lien du mail de notification.
2. activate : le code et le mot de passe choisi -> le mot de passe est haché,
   le compte activé.

Garde-fou commun : seul un compte « en attente » (inactif ET au mot de passe
PENDING_SIGNUP_PASSWORD) s'active ainsi. Un compte déjà activé refuse le code
(il ne sert donc qu'une fois) ; un compte effacé (ADR-049, mot de passe
ANONYMIZED_PASSWORD) ne se réveille pas ; un compte repris du seed non plus.
Toute anomalie de activate rend la même ActivationError : l'appelant ne sait
pas si le code était faux, expiré ou déjà servi.
============================================================================
"""

from typing import Optional

from sqlmodel import Session, col, select

from ..models import Client, SearchRequest, User
from ..utils.exceptions import NotFoundError
from ..utils.roles import ADMIN, Principal
from ..utils.security import (
    PENDING_SIGNUP_PASSWORD,
    InvalidTokenError,
    create_activation_token,
    decode_activation_token,
    hash_password,
)


class ActivationError(Exception):
    """Code d'activation refusé : faux, expiré, ou compte plus en attente."""


def _is_pending(user: Optional[User]) -> bool:
    """Vrai pour un compte créé par le formulaire et jamais activé."""
    return user is not None and not user.is_activated and user.password == PENDING_SIGNUP_PASSWORD


def _manages_a_request_of(session: Session, manager_profile_id: Optional[int], user_id: int) -> bool:
    """Vrai si une demande du client `user_id` a pour manager la fiche `manager_profile_id`."""
    if manager_profile_id is None:
        return False
    client_ids = select(Client.id).where(Client.id_user == user_id)
    query = select(SearchRequest.id).where(
        col(SearchRequest.id_client).in_(client_ids),
        SearchRequest.id_realestatemanager == manager_profile_id,
    )
    return session.exec(query).first() is not None


class ActivationService:
    def issue_code(self, session: Session, principal: Principal, user_id: int) -> str:
        """
        Rend un code d'activation pour le compte `user_id`. NotFoundError
        (404) si le compte n'existe pas, n'est pas en attente, ou si un
        Manager ne gère aucune demande de ce client : la réponse ne dit pas
        lequel.
        """
        user = session.get(User, user_id)
        if not _is_pending(user):
            raise NotFoundError(f"Aucun compte en attente d'activation n'a l'id {user_id}.")
        if principal.role != ADMIN and not _manages_a_request_of(session, principal.profile_id, user_id):
            raise NotFoundError(f"Aucun compte en attente d'activation n'a l'id {user_id}.")
        return create_activation_token(user_id)

    def activate(self, session: Session, code: str, password: str) -> User:
        """
        Pose le mot de passe (haché) et active le compte du code. Rend le
        compte activé ; ActivationError pour un code faux ou expiré, ou un
        compte qui n'est plus en attente.
        """
        try:
            user_id = decode_activation_token(code)
        except InvalidTokenError as exc:
            raise ActivationError() from exc
        user = session.get(User, user_id)
        if user is None or not _is_pending(user):
            raise ActivationError()
        user.password = hash_password(password)
        user.is_activated = True
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
