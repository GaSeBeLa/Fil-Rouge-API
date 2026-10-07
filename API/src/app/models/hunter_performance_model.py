"""
hunter_performance_model.py — Le score de performance d'un chasseur, daté,
et ce qui l'a déclenché.

La table est un **journal des notes** (Q-SCH-06) : une note = une ligne
datée à la seconde (`scored_at`), sans période ; la note actuelle est la
dernière ligne du chasseur. Rien n'est écrasé. Deux ventes le même jour
donnent deux lignes, puisque la note est recalculée à chaque vente
(Q-REM-06).

`trigger_type` dit d'où vient la ligne :

    initial           le score de départ, à l'embauche
    payment           recalculé à la suite d'un versement
    mandate_expired   recalculé parce qu'un mandat s'est éteint sans vente

`id_payment` et `id_mandate` sont donc `NULL` selon le déclencheur ; un
même paiement, ou un même mandat, ne donne qu'une note (UNIQUE côté base).
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import SQLModel, Field


class HunterPerformance(SQLModel, table=True):
    __tablename__ = "hunter_performance"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # score : NUMERIC(4,1).
    score: Decimal = Field(max_digits=4, decimal_places=1)
    # TIMESTAMP NOT NULL : le moment de la note, à la seconde (Q-SCH-06).
    scored_at: datetime
    # trigger_type : NOT NULL + CHECK cote base — 'initial', 'payment',
    # 'mandate_expired'.
    trigger_type: str = Field(max_length=20)
    id_hunter: int = Field(foreign_key="hunter.id_user")
    # Renseigne selon le declencheur, NULL sinon ; UNIQUE chacun (Q-SCH-06).
    id_payment: Optional[int] = Field(default=None, foreign_key="payment.id")
    id_mandate: Optional[int] = Field(default=None, foreign_key="mandate.id")
