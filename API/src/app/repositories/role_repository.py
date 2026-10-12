from typing import Optional

from sqlmodel import Session, select

from ..models import Role
from .base_repository import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self):
        super().__init__(Role)

    def get_by_wording(self, session: Session, wording: str) -> Optional[Role]:
        """Le rôle de ce libellé (UNIQUE en base), ou None."""
        return session.exec(select(Role).where(Role.wording == wording)).first()
