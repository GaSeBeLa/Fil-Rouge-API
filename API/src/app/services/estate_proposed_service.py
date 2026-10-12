"""
estate_proposed_service.py — Proposer un bien au client (fiche API7).

Deux règles qui croisent les tables, donc dans le service (ADR-040) ; un
refus lève ConflictError (409) :

- P20 (audit, ADR-053) : on ne propose que sur un mandat `'active'`. Le
  statut change dans le temps : aucune contrainte de la base ne peut le dire.
- P19 (audit, ADR-053) : le bien est dans la sélection (`estate_searchrequest`)
  de la demande du mandat — le chasseur transmet SA sélection au client
  (`05_…feature`, @transmission-client).

Un PUT qui change le bien ou le mandat est une nouvelle proposition : il
repasse les deux règles. Un PUT qui garde les deux (statut, montant,
commentaire) ne les rejuge pas.
"""

from typing import Optional

from sqlmodel import Session

from ..models import EstateProposed, User
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.mandate_repository import MandateRepository
from ..utils.exceptions import ConflictError
from .base_service import BaseService

ACTIVE = "active"


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

    def _check_proposal(self, session: Session, item: EstateProposed) -> None:
        mandate = self.mandates.get_by_id(session, item.id_mandate)
        if mandate is None:
            raise ConflictError("Mandat introuvable (id_mandate).")
        if mandate.status != ACTIVE:
            raise ConflictError(f"On ne propose que sur un mandat 'active', pas '{mandate.status}' (P20).")
        in_selection = self.selections.exists_where(
            session, id_search_request=mandate.id_search_request, id_estate=item.id_estate
        )
        if not in_selection:
            raise ConflictError("Ce bien n'est pas dans la sélection de la demande du mandat (P19).")

    def create(self, session: Session, item: EstateProposed, actor: Optional[User] = None) -> EstateProposed:
        self._check_proposal(session, item)
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: EstateProposed) -> EstateProposed:
        existing = self.get_by_id(session, item_id)
        if (data.id_estate, data.id_mandate) != (existing.id_estate, existing.id_mandate):
            self._check_proposal(session, data)
        return self.repository.replace(session, existing, data)
