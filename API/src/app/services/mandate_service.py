"""
mandate_service.py — Un mandat, et le lancement de sa recherche (fiche API8).

ADR-044 (déduction S6, confirmée le 09/10/2026) : quand le mandat reçoit sa
`signature_date` — créé signé, ou signé par un PUT —, la demande liée passe
à `'launched'` (ADR-041 : « le mandat est signé : la recherche est
lancée »). Même transaction : la demande est préparée (`stage`), puis écrite
par le commit du mandat ; si la base refuse le mandat, la demande reste
telle quelle.

M1 (voté le 2026-11-03, fiche SUG2) : pas de signature sans critères. Si la
demande n'a aucune ligne `criteria`, poser `signature_date` lève
ConflictError (409) et la demande n'est pas lancée. Un mandat non signé
(`pending_signature`) reste possible sans critères.

« Le sien » (ADR-027, annexe § 2 ; fiche DRO5) : un Client voit ses
mandats, et ne modifie (signer, P3) que les siens : `id_client` est sa
fiche client (`client.id`, comparé à `viewer.profile_id`). Il ne fait que signer : `CLIENT_FIELDS`, et le statut seulement de
'pending_signature' à 'active' ; tout autre champ lève 403 (2026-11-20). La clé (id_search_request, id_client) garde la demande au même client.

Le Hunter (fiche DRO6) voit ses mandats ; il n'en crée (H4) et n'en
modifie qu'à son nom, sur une de ses demandes : sinon un mandat sur la
demande d'un autre lui ouvrait le client de cet autre (H3). Renouveler le
mandat d'un autre chasseur reste fermé tant que Jeff n'a pas tranché la
réaffectation d'un mandat (Q-JEF-30).

Le Manager (fiche DRO7) voit les mandats de son équipe (manager_rows.py).
"""

from datetime import date
from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import Mandate, User
from ..repositories.criteria_repository import CriteriaRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..utils.exceptions import ConflictError, ForbiddenError
from ..utils.roles import CLIENT, HUNTER, MANAGER, Principal
from .base_service import BaseService, fields_changed_outside
from .hunter_rows import handles_request
from .manager_rows import in_team, team_mandates

LAUNCHED = "launched"
PENDING_SIGNATURE = "pending_signature"
ACTIVE = "active"
# Les champs que le Client change en signant (ADR-027, annexe, P3) ; le
# statut se garde à part : seulement de 'pending_signature' à 'active'.
CLIENT_FIELDS = ("signature_date", "signature_type", "ends_at")


class MandateService(BaseService[Mandate]):
    def __init__(self, repository: MandateRepository, requests: SearchRequestRepository, criteria: CriteriaRepository):
        super().__init__(repository, not_found_detail="Mandat introuvable")
        self.requests = requests
        self.criteria = criteria

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(Mandate.id_client) == viewer.profile_id
        if viewer.role == HUNTER:
            return col(Mandate.id_hunter) == viewer.profile_id
        if viewer.role == MANAGER:
            return in_team(Mandate.id, team_mandates(viewer.profile_id))
        return None

    def owns(self, session: Session, item: Mandate, viewer: Principal) -> bool:
        if viewer.role == CLIENT:
            return item.id_client == viewer.profile_id
        if viewer.role == HUNTER:
            return item.id_hunter == viewer.profile_id and handles_request(session, viewer.profile_id, item.id_search_request)
        return True

    def _launch_request(self, session: Session, mandate: Mandate) -> None:
        """
        La signature : refuse une demande sans critères (M1, 409), puis passe
        la demande à 'launched'. Une demande introuvable ne lève rien ici : la
        clé étrangère du mandat refusera l'écriture.
        """
        if not self.criteria.exists_where(session, id_search_request=mandate.id_search_request):
            raise ConflictError("La demande n'a aucun critère : le mandat ne peut pas être signé.")
        request = self.requests.get_by_id(session, mandate.id_search_request)
        if request is None:
            return  # la clé étrangère du mandat refusera l'écriture (409)
        request.status = LAUNCHED
        self.requests.stage(session, request)

    def create(self, session: Session, item: Mandate, actor: Optional[User] = None) -> Mandate:
        if item.signature_date is not None:
            self._launch_request(session, item)
        return super().create(session, item, actor)

    def replace_visible(self, session: Session, item_id: int, data: Mandate, viewer: Principal) -> Mandate:
        """
        Le PUT : le mandat d'un autre lève NotFoundError (404), un mandat qui
        cesserait d'être à lui ConflictError (409, « le sien », vu d'abord) ;
        puis le Client ne fait que signer (ADR-027, annexe, P3) : sur un mandat
        'pending_signature' seulement, il change `CLIENT_FIELDS` et passe le
        statut à 'active' ; un mandat déjà signé ne bouge plus pour lui (sa
        date prolongerait la validité). Sinon ForbiddenError (403), la ligne
        intacte. Une date de signature future lève ConflictError (409) :
        elle prolongerait le mandat ; une date passée reste permise (papier). Les autres rôles gardent la règle commune.
        """
        existing = self.get_by_id(session, item_id, viewer)
        if viewer.role == CLIENT:
            self._check_owner(session, data, viewer)
            pending = existing.status == PENDING_SIGNATURE
            allowed = CLIENT_FIELDS if pending else ()
            changed = fields_changed_outside(existing, data, allowed + ("status",))
            signs = pending and data.status == ACTIVE
            if data.status != existing.status and not signs:
                changed.append("status")
            if changed:
                raise ForbiddenError(
                    f"Le client ne fait que signer son mandat, pas changer {', '.join(changed)} (ADR-027, P3)."
                )
            if signs and data.signature_date is not None and data.signature_date > date.today():
                raise ConflictError("Une signature ne se date pas dans le futur : elle prolongerait le mandat.")
        return super().replace_visible(session, item_id, data, viewer)

    def replace(self, session: Session, item_id: int, data: Mandate) -> Mandate:
        existing = self.get_by_id(session, item_id)
        if existing.signature_date is None and data.signature_date is not None:
            self._launch_request(session, data)
        return self.repository.replace(session, existing, data)
