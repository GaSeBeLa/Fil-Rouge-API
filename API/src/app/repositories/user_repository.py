from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from ..models import User
from .base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, session: Session, email: str) -> Optional[User]:
        """Le compte de cet email, ou None (email UNIQUE en base)."""
        return session.exec(select(User).where(User.email == email)).first()

    def find_by_email_ignoring_case(self, session: Session, email: str) -> Optional[User]:
        """
        Le compte de cet email, sans tenir compte des majuscules (P2 : la base
        refuse deux emails qui ne diffèrent que par la casse, index
        uq_user_email_lower), ou None. Le login garde get_by_email.
        """
        return session.exec(select(User).where(func.lower(User.email) == email.lower())).first()
