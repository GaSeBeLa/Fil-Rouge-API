"""
estate_proposed_service.py — Proposer un bien au client (fiche API7).

Deux règles qui croisent les tables, donc dans le service (ADR-040) ; un
refus lève ConflictError (409) :

- P20 (audit, ADR-053) : on ne propose que sur un mandat `'active'`. Le
  statut change dans le temps : aucune contrainte de la base ne peut le dire.
- P19 (audit, ADR-053) : le bien est dans la sélection (`estate_searchrequest`)
  de la demande du mandat — le chasseur transmet SA sélection au client
  (`05_…feature`, @transmission-client). Renforcée par la fiche SUG4 : le
  bien y est à l'état `'kept'`, gardé par le chasseur ; un bien `'suggested'`
  (la machine) ou `'dismissed'` (écarté) ne se propose pas.

Un PUT qui change le bien ou le mandat est une nouvelle proposition : il
repasse les deux règles. Un PUT qui garde les deux (statut, montant,
commentaire) ne les rejuge pas.

« Le sien » (ADR-027, annexe § 3 ; fiche DRO5) : un Client voit les biens
proposés sur ses mandats, et ne modifie (commenter, prioriser, offrir ;
H6, H8) que ceux-là : `id_mandate` reste un de ses mandats. Sur un PUT, il
ne change que sa note, son commentaire et sa décision (`CLIENT_FIELDS`,
fiches SUG1 et SUG5) :
tout autre champ changé lève ForbiddenError (403) — le statut, le montant et
le commentaire du chasseur restent au chasseur.

L'offre du client (fiche SUG6) passe par sa propre route, `make_offer` :
sur un bien encore `'proposed'` (sinon ConflictError, 409), elle écrit en
une fois le montant, `'offer_pending'` et sa décision `'interested'`, datée
de maintenant. Le montant ne passe pas par le PUT du client (SUG1).

Le Hunter (fiche DRO6) voit ses propositions, et n'en écrit qu'à son nom
(H5, H9) ; la clé (id_mandate, id_hunter) garde le mandat au même chasseur.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ColumnElement
from sqlmodel import Session, col

from ..models import EstateProposed, User
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.mandate_repository import MandateRepository
from ..utils.exceptions import ConflictError, ForbiddenError
from ..utils.roles import CLIENT, HUNTER, Principal
from .base_service import BaseService, fields_changed_outside
from .client_rows import mandates_of, owns_mandate

ACTIVE = "active"
PROPOSED = "proposed"
OFFER_PENDING = "offer_pending"
INTERESTED = "interested"
# Fiche SUG4 : le seul état de la sélection qu'on propose au client (P19).
KEPT = "kept"

# Fiches SUG1 (H6, H8) et SUG5 (M4) : ce que le client change sur un bien proposé.
CLIENT_FIELDS = ("client_priority", "comment_client", "client_decision", "client_decided_at", "decline_reason")


class EstateProposedService(BaseService[EstateProposed]):
    def __init__(
        self,
        repository: EstateProposedRepository,
        mandates: MandateRepository,
        selections: EstateSearchRequestRepository,
    ):
        super().__init__(repository, not_found_detail="Proposition de bien introuvable")
        self.mandates = mandates
        self.selections = selections

    def visible_rows(self, viewer: Principal) -> Optional[ColumnElement[bool]]:
        if viewer.role == CLIENT:
            return col(EstateProposed.id_mandate).in_(mandates_of(viewer.profile_id))
        if viewer.role == HUNTER:
            return col(EstateProposed.id_hunter) == viewer.profile_id
        return None

    def owns(self, session: Session, item: EstateProposed, viewer: Principal) -> bool:
        if viewer.role == CLIENT:
            return owns_mandate(session, viewer.profile_id, item.id_mandate)
        if viewer.role == HUNTER:
            # La clé (id_mandate, id_hunter) garde le mandat au même chasseur.
            return item.id_hunter == viewer.profile_id
        return True

    def _check_proposal(self, session: Session, item: EstateProposed) -> None:
        mandate = self.mandates.get_by_id(session, item.id_mandate)
        if mandate is None:
            raise ConflictError("Mandat introuvable (id_mandate).")
        if mandate.status != ACTIVE:
            raise ConflictError(f"On ne propose que sur un mandat 'active', pas '{mandate.status}' (P20).")
        in_selection = self.selections.exists_where(
            session, id_search_request=mandate.id_search_request, id_estate=item.id_estate, status=KEPT
        )
        if not in_selection:
            raise ConflictError(
                "Ce bien n'est pas dans la sélection de la demande du mandat, à l'état 'kept' (P19)."
            )

    def create(self, session: Session, item: EstateProposed, actor: Optional[User] = None) -> EstateProposed:
        self._check_proposal(session, item)
        return super().create(session, item, actor)

    def replace_visible(
        self, session: Session, item_id: int, data: EstateProposed, viewer: Principal
    ) -> EstateProposed:
        """
        Le PUT : la proposition d'un autre lève NotFoundError (404), une
        proposition déplacée hors de ses mandats ConflictError (409, « le
        sien », vu d'abord) ; puis le Client ne change que `CLIENT_FIELDS`,
        sinon ForbiddenError (403), la ligne intacte. Les autres rôles gardent
        la règle commune.
        """
        existing = self.get_by_id(session, item_id, viewer)
        if viewer.role == CLIENT:
            self._check_owner(session, data, viewer)
            changed = fields_changed_outside(existing, data, CLIENT_FIELDS)
            if changed:
                raise ForbiddenError(
                    f"Le client ne change que sa note, son commentaire et sa décision, pas {', '.join(changed)} (fiche SUG1)."
                )
        return super().replace_visible(session, item_id, data, viewer)

    def make_offer(self, session: Session, item_id: int, amount: int, viewer: Principal) -> EstateProposed:
        """
        L'offre du client sur un bien proposé (fiche SUG6) : la proposition
        mise à jour. Celle d'un autre lève NotFoundError (404, « le sien ») ;
        une proposition qui n'est plus `'proposed'`, ConflictError (409) —
        une offre ne se refait pas, la ligne reste telle quelle.
        """
        existing = self.get_by_id(session, item_id, viewer)
        if existing.proposition_status != PROPOSED:
            raise ConflictError(
                f"Une offre se fait sur un bien encore 'proposed', pas '{existing.proposition_status}'."
            )
        offer = EstateProposed.model_validate(existing.model_dump())
        offer.amount_proposition = amount
        offer.proposition_status = OFFER_PENDING
        offer.client_decision = INTERESTED
        offer.client_decided_at = datetime.now(timezone.utc)
        # Même bien, même mandat : P19 et P20 ne se rejugent pas (replace()).
        return self.repository.replace(session, existing, offer)

    def replace(self, session: Session, item_id: int, data: EstateProposed) -> EstateProposed:
        existing = self.get_by_id(session, item_id)
        if (data.id_estate, data.id_mandate) != (existing.id_estate, existing.id_mandate):
            self._check_proposal(session, data)
        return self.repository.replace(session, existing, data)
