from typing import Optional

from sqlmodel import Session

from ..models import User, UserCreate, UserUpdate
from ..repositories.user_repository import UserRepository
from ..utils.security import hash_password, needs_rehash, verify_password
from .base_service import BaseService


class UserService(BaseService[User]):
    """
    Seul endroit du projet qui transforme un mot de passe en clair en
    empreinte. Si un mot de passe en clair atteint la base, c'est qu'un
    chemin d'écriture contourne cette classe.
    """

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
        if user is None or not verify_password(user.password, password):
            return None
        if not user.is_activated:
            return None
        if needs_rehash(user.password):
            user.password = hash_password(password)
            user = self.repository.save(session, user)
        return user

    def create(self, session: Session, item: UserCreate) -> User:
        user = User(
            email=item.email,
            password=hash_password(item.password),
            is_activated=item.is_activated,
            id_role=item.id_role,
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