"""
estate_contact_repository.py — Le contact du vendeur d'un bien (ADR-054).

`ids_inactive_since` cherche les contacts dont le bien n'a plus bougé
depuis une date : la base de l'effacement à 3 ans (question 4).
"""

from datetime import date
from typing import List

from sqlalchemy import text
from sqlmodel import Session

from ..models import EstateContact
from .base_repository import BaseRepository

# La dernière activité d'un bien : la plus récente de ces dates. GREATEST
# ignore les NULL (un bien jamais visité, jamais vendu). Un mandat en cours
# (ends_at futur) garde donc le contact.
_LAST_ACTIVITY = """
    GREATEST(
        c.created_at::date,
        e.created_at::date,
        (SELECT max(es.created_at)::date FROM estate_searchrequest es WHERE es.id_estate = e.id),
        (SELECT max(ep.created_at)::date FROM estate_proposed ep WHERE ep.id_estate = e.id),
        (SELECT max(m.ends_at) FROM estate_proposed ep
            JOIN mandate m ON m.id = ep.id_mandate WHERE ep.id_estate = e.id),
        (SELECT max(v.visit_date) FROM visit v WHERE v.id_estate = e.id),
        (SELECT max(s.signature_date) FROM sale s WHERE s.id_estate = e.id)
    )
"""


class EstateContactRepository(BaseRepository[EstateContact]):
    def __init__(self):
        super().__init__(EstateContact)

    def ids_inactive_since(self, session: Session, cutoff: date) -> List[int]:
        """Les contacts dont le bien n'a eu aucune activité après `cutoff`."""
        query = text(
            f"SELECT c.id FROM estate_contact c JOIN estate e ON e.id = c.id_estate "
            f"WHERE {_LAST_ACTIVITY} <= :cutoff ORDER BY c.id"
        )
        return list(session.connection().execute(query, {"cutoff": cutoff}).scalars())

    def commit(self, session: Session) -> None:
        """
        Écrit d'un coup les contacts préparés par `stage` ; un refus annule
        tout, et son message nomme la contrainte (fiche FIN1).
        """
        self._commit_or_raise(session)
