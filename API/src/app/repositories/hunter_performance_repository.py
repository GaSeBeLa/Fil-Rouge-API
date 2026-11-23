from sqlmodel import Session

from ..models import HunterPerformance
from .base_repository import BaseRepository


class HunterPerformanceRepository(BaseRepository[HunterPerformance]):
    def __init__(self):
        super().__init__(HunterPerformance)

    def commit(self, session: Session) -> None:
        """
        Écrit d'un coup les notes préparées par `stage` ; un refus annule
        tout, et son message nomme la contrainte (fiche FIN1).
        """
        self._commit_or_raise(session)
