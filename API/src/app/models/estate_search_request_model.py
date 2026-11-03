"""
estate_search_request_model.py — Table de jonction N:N entre estate et
search_request, qui stocke aussi l'avis du chasseur sur ce bien pour cette
demande. Ses médias (audio/vidéo) sont dans review_media.

`status` (fiche SUG4) : 'suggested' (proposé par la machine), 'kept' (gardé
par le chasseur), 'dismissed' (écarté) ; le CHECK de la base juge la valeur.
Le chasseur le change par le PUT. Seul un bien 'kept' se propose au client
(P19, services/estate_proposed_service.py).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from .field_descriptions import HUNTER_PROFILE


class EstateSearchRequest(SQLModel, table=True):
    __tablename__ = "estate_searchrequest"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    review_hunter: Optional[str] = None
    id_estate: int = Field(foreign_key="estate.id")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_hunter: int = Field(description=HUNTER_PROFILE, foreign_key="hunter.id")
    status: str = Field(default="suggested", max_length=20)
