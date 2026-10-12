from datetime import date
from typing import Optional

from sqlmodel import Session, col, select

from ..models import ParametersFees
from .base_repository import BaseRepository


class ParametersFeesRepository(BaseRepository[ParametersFees]):
    def __init__(self):
        super().__init__(ParametersFees)

    def in_force_at(self, session: Session, day: date) -> Optional[ParametersFees]:
        """La grille en vigueur ce jour-là : la dernière dont `effective_from` <= `day` (ADR-030)."""
        statement = (
            select(ParametersFees)
            .where(col(ParametersFees.effective_from) <= day)
            .order_by(col(ParametersFees.effective_from).desc())
            .limit(1)
        )
        return session.exec(statement).first()
