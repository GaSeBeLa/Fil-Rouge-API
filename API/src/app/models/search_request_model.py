"""
search_request_model.py — La demande de recherche déposée par un
client, éventuellement affectée à un chasseur ou un gestionnaire.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class SearchRequest(SQLModel, table=True):
    __tablename__ = "search_request"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id_author: int = Field(foreign_key="user.id")
    id_client: int = Field(foreign_key="client.id_user")
    id_hunter: Optional[int] = Field(default=None, foreign_key="hunter.id_user")
    # Même remarque que pour is_cartet (voir hunter_model.py) :
    # "id_realestatemanager" tout en minuscules côté base, malgré le
    # "camelCase" du diagramme source.
    id_realestatemanager: Optional[int] = Field(
        default=None, foreign_key="real_estate_manager.id_user"
    )
    # status : NOT NULL + CHECK cote base — 'confirmed', 'accepted',
    # 'rejected', 'launched'. Les demandes migrees valent 'confirmed',
    # hypothese a confirmer (docker/init-v2/README.md §3.5).
    status: str = Field(max_length=20)
