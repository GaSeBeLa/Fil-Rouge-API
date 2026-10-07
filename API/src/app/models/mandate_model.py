"""
mandate_model.py — Le mandat de recherche confié à un chasseur par un
client, pour une demande de recherche donnée.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class Mandate(SQLModel, table=True):
    __tablename__ = "mandate"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference: str = Field(max_length=20, unique=True)
    # status : NOT NULL + CHECK côté base (voir remarque sur typology
    # dans criteria_model.py, même logique). 'lost' = vente perdue, personne
    # n'est payé sur ce mandat (Q-REM-02, Q-REM-14).
    status: str = Field(max_length=20)
    # Seule trace de la signature du client : is_client_signed est retiré
    # (Q-MAN-05, Q-MAN-09).
    signature_date: Optional[date] = None
    signature_type: Optional[str] = Field(default=None, max_length=20)
    # Vide tant que le mandat n'est pas signé, comme en base (01 : DATE sans
    # NOT NULL) — un mandat 'canceled' jamais signé n'a pas de fin (Q-MAN-07).
    ends_at: Optional[date] = None
    is_exclusive: bool
    id_hunter: int = Field(foreign_key="hunter.id_user")
    id_client: int = Field(foreign_key="client.id_user")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_mandate_parent: Optional[int] = Field(default=None, foreign_key="mandate.id")
