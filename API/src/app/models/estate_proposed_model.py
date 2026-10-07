"""
estate_proposed_model.py — Un bien proposé par un chasseur pour un
mandat donné, avec le retour du client (montant proposé, acceptation).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class EstateProposed(SQLModel, table=True):
    __tablename__ = "estate_proposed"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    comment_hunter: Optional[str] = None
    comment_client: Optional[str] = None
    # Montant en euros entiers : INTEGER côté base, comme tout prix (Q-REM-01).
    amount_proposition: Optional[int] = None
    # proposition_status remplace l'ancien booleen is_accepted : une
    # proposition passe par plusieurs etats, pas seulement oui/non.
    # CHECK cote base — 'proposed', 'offer_pending', 'accepted', 'signed'
    # (Q-SCH-04), 'rejected'.
    proposition_status: str = Field(max_length=20)
    id_hunter: int = Field(foreign_key="hunter.id_user")
    id_estate: int = Field(foreign_key="estate.id")
    id_mandate: int = Field(foreign_key="mandate.id")
    # Priorite donnee par le client au bien, de 1 a 5 ; vide tant qu'il n'a
    # pas donne son avis. CHECK cote base (D6, Q-SCH-05, Q-JEF-18).
    client_priority: Optional[int] = None
