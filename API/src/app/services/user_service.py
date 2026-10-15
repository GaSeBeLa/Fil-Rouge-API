from typing import TYPE_CHECKING, Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import User, UserCreate, UserUpdate
from ..repositories.user_repository import UserRepository
from ..utils.exceptions import ForbiddenError
from ..utils.security import hash_password, needs_rehash, spend_password_check, verify_password
from .base_service import BaseService

if TYPE_CHECKING:
    # Pour le typage seulement : utils/roles.py importe current_user.py, qui importe ce module.
    from ..utils.roles import Principal

# ADR-027, annexe § 1 : « R U le sien, sauf rôle et activation ».
ADMIN_ONLY_FIELDS = ("id_role", "system_role", "is_activated")  # system_role : PRF6


class UserService(BaseService[User]):
    """
    Seul endroit du projet qui transforme un mot de passe en clair en
    empreinte. Si un mot de passe en clair atteint la base, c'est qu'un
    chemin d'écriture contourne cette classe.

    « Le sien » (ADR-027, annexe § 1 ; fiches DRO5, DRO6, DRO7) : un Client,
    un Hunter ou un Manager voit son compte et le modifie, sauf
    ADMIN_ONLY_FIELDS (403).

    Compte désactivé (fiche DRO8) : il n'est plus lu que par l'Admin
    (account_column, base_service.py).
    """

    # ADR-027, point 7 : désactivé, ce compte n'est plus lu que par l'Admin (DRO8).
    account_column = User.id

    def __init__(self, repository: UserRepository):
        super().__init__(repository, not_found_detail="Utilisateur introuvable")
        # Même objet que self.repository, typé UserRepository pour get_by_email.
        self.users = repository

    def authenticate(self, session: Session, email: str, password: str) -> Optional[User]:
        """
        Le compte si l'email et le mot de passe concordent ET que le compte
        est activé ; sinon None, sans dire lequel des trois a échoué : la
        route renvoie le même 401 dans tous les cas (ADR-052).

        Après un succès, et seulement là, l'empreinte est refaite si ses
        paramètres sont plus faibles que les courants (ADR-016, needs_rehash).
        """
        user = self.users.get_by_email(session, email)
        if user is None:
            spend_password_check(password)  # même durée qu'un email connu
            return None
        if not verify_password(user.password, password):
            return None
        if not user.is_activated:
            return None
        if needs_rehash(user.password):
            user.password = hash_password(password)
            user = self.repository.save(session, user)
        return user

    def create(self, session: Session, item: UserCreate, actor: Optional[User] = None) -> User:
        user = User(
            email=item.email,
            password=hash_password(item.password),
            is_activated=item.is_activated,
            id_role=item.id_role,
            system_role=item.system_role,
        )
        return self.repository.create(session, user)

    def replace(self, session: Session, item_id: int, data: UserUpdate) -> User:
        """
        Mise à jour PARTIELLE : seuls les champs réellement fournis dans la
        requête (`exclude_unset=True`) sont modifiés. Contourne
        `BaseRepository.replace()` (remplacement complet, écraserait les
        champs omis avec NULL) au profit de `save()` (voir
        base_repository.py), après avoir haché un `password` s'il est
        fourni.
        """
        existing = self.get_by_id(session, item_id)
        changes = data.model_dump(exclude_unset=True)

        if "password" in changes:
            changes["password"] = hash_password(changes["password"])

        for field, value in changes.items():
            setattr(existing, field, value)

        return self.repository.save(session, existing)

    def visible_rows(self, viewer: "Principal") -> Optional[ColumnElement[bool]]:
        from ..utils.roles import CLIENT, HUNTER, MANAGER  # à l'appel : même cycle d'import que Principal

        if viewer.role in (CLIENT, HUNTER, MANAGER):
            return col(User.id) == viewer.user.id
        return None

    # Le PUT de /users reçoit un UserUpdate partiel, pas un User : même écart que replace().
    def replace_visible(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, session: Session, item_id: int, data: UserUpdate, viewer: "Principal"
    ) -> User:
        """
        Le PUT : le compte d'un autre lève NotFoundError (404) ; hors Admin,
        changer son rôle ou son activation lève ForbiddenError (403). Un
        compte n'a pas de ligne parente : rien à demander au crochet `owns`.
        """
        existing = self.get_by_id(session, item_id, viewer)
        if not viewer.is_admin:
            changes = data.model_dump(exclude_unset=True)
            changed = [
                field for field in ADMIN_ONLY_FIELDS if field in changes and changes[field] != getattr(existing, field)
            ]
            if changed:
                raise ForbiddenError(f"Seul l'Admin change {', '.join(changed)} (ADR-027, annexe § 1).")
        return self.replace(session, item_id, data)