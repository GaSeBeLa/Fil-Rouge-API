from typing import Optional

from sqlmodel import Session, select

from ..models import User
from .base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, session: Session, email: str) -> Optional[User]:
        """Le compte de cet email, ou None (email UNIQUE en base)."""
        return session.exec(select(User).where(User.email == email)).first()
