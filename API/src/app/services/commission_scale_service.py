"""
commission_scale_service.py — Les tranches du barème de commission.

« Le sien » (ADR-027, annexe § 4 ; fiche DRO6) : un Hunter voit le barème
par défaut (`id_hunter` vide) et le sien (Q-ACC-06) ; celui d'un autre
chasseur rend 404.

Le Manager (fiche DRO7) voit « ceux de ses chasseurs » : le barème propre à
l'un d'eux, et le barème par défaut, qui vaut pour ceux qui n'en ont pas.
"""

from typing import Optional

from sqlalchemy import ColumnElement, or_
from sqlmodel import col

from ..models import CommissionScale
from ..repositories.commission_scale_repository import CommissionScaleRepository
from ..repositories.payment_repository import PaymentRepository
from ..utils.roles import HUNTER, MANAGER, Principal
from .manager_rows import hunters_of_team
from .version_service import FrozenOnceCitedService


class CommissionScaleService(FrozenOnceCitedService[CommissionScale]):
    """Une ligne de barème citée par un paiement ne se modifie plus (ADR-034)."""

    def __init__(self, repository: CommissionScaleRepository, payments: PaymentRepository):
        super().__init__(
            repository,
            not_found_detail="Tranche de barème introuvable",
            cited_by=[(payments, "id_commission_scale")],
        )

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == HUNTER:
            return or_(col(CommissionScale.id_hunter).is_(None), col(CommissionScale.id_hunter) == viewer.user.id)
        if viewer.role == MANAGER:
            team = hunters_of_team(viewer.user.id)
            return or_(col(CommissionScale.id_hunter).is_(None), col(CommissionScale.id_hunter).in_(team))
        return None
