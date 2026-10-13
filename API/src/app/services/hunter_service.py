"""
hunter_service.py — Les fiches des chasseurs.

« Le sien » (ADR-027, annexe § 1 ; fiche DRO5) : un Client voit son
chasseur (P2), celui d'un de ses mandats ou d'une de ses demandes.

Le Hunter (fiche DRO6) voit sa fiche, et n'y modifie que ses coordonnées
(CONTACT_FIELDS, le bloc commun à hunter et real_estate_manager). Le reste —
embauche, carte T, certification, manager, compte — est à l'Admin : le
changer lève ForbiddenError (403).

Le Manager (fiche DRO7) voit ses chasseurs (Q-ACC-02).
"""

from typing import Optional

from sqlalchemy import ColumnElement, or_
from sqlmodel import Session, SQLModel, col

from ..models import Hunter
from ..repositories.hunter_repository import HunterRepository
from ..utils.exceptions import ForbiddenError
from ..utils.roles import CLIENT, HUNTER, MANAGER, Principal
from .base_service import BaseService, fields_changed_outside
from .client_rows import hunters_of

# ADR-027, annexe § 1 : « U ses coordonnées ».
CONTACT_FIELDS = ("first_name", "last_name", "phone_number", "gender", "country_iso", "company_name")


def check_contact_only(existing: SQLModel, data: SQLModel, viewer: Principal) -> None:
    """Hors Admin, changer autre chose que ses coordonnées lève ForbiddenError (403)."""
    if viewer.is_admin:
        return
    changed = fields_changed_outside(existing, data, CONTACT_FIELDS)
    if changed:
        raise ForbiddenError(f"Seul l'Admin change {', '.join(changed)} (ADR-027, annexe § 1).")


class HunterService(BaseService[Hunter]):
    def __init__(self, repository: HunterRepository):
        super().__init__(repository, not_found_detail="Chasseur introuvable")

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return or_(*(col(Hunter.id_user).in_(hunters) for hunters in hunters_of(viewer.user.id)))
        if viewer.role == HUNTER:
            return col(Hunter.id_user) == viewer.user.id
        if viewer.role == MANAGER:
            return col(Hunter.id_realestatemanager) == viewer.user.id
        return None

    def replace_visible(self, session: Session, item_id: int, data: Hunter, viewer: Principal) -> Hunter:
        """
        Le PUT : la fiche d'un autre lève NotFoundError (404) ; hors Admin,
        changer autre chose que ses coordonnées lève ForbiddenError (403).
        """
        check_contact_only(self.get_by_id(session, item_id, viewer), data, viewer)
        return super().replace_visible(session, item_id, data, viewer)
