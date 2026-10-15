"""
search_request_model.py — La demande de recherche déposée par un
client, éventuellement affectée à un chasseur ou un gestionnaire.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from .field_descriptions import AUTHOR_ACCOUNT, CLIENT_PROFILE, HUNTER_PROFILE, MANAGER_PROFILE


class SearchRequest(SQLModel, table=True):
    __tablename__ = "search_request"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id_author: int = Field(description=AUTHOR_ACCOUNT, foreign_key="user.id")
    id_client: int = Field(description=CLIENT_PROFILE, foreign_key="client.id")
    id_hunter: Optional[int] = Field(description=HUNTER_PROFILE, default=None, foreign_key="hunter.id")
    # "id_realestatemanager" tout en minuscules côté base, malgré le
    # "camelCase" du diagramme source : PostgreSQL replie en minuscules
    # les identifiants non "quotés".
    id_realestatemanager: Optional[int] = Field(description=MANAGER_PROFILE, 
        default=None, foreign_key="real_estate_manager.id"
    )
    # status : NOT NULL + CHECK côté base — 'confirmed', 'accepted',
    # 'rejected', 'launched'. 'confirmed' = demande reçue, sans chasseur
    # encore (formulaire du site, ADR-041) ; les trois autres ont un chasseur
    # (chk_search_request_hunter_after_confirmed, P6). Les demandes migrées
    # valent 'launched' : insérées en 'confirmed', passées en 'launched' dès
    # qu'un mandat existe (02_migration.sql) — 18 sur 18 en base de dev,
    # compté le 2026-10-14 (fiche FIN2).
    status: str = Field(max_length=20)
