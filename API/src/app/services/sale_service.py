"""
sale_service.py — Une vente, et ce qu'elle exige du mandat (fiche API8).

Règles qui croisent les tables, donc dans le service (ADR-040) ; un refus
lève ConflictError (409). Elles valent au POST comme au PUT :

- Q-MAN-06 (TODO du bloc `sale` de init-v3/01) : la vente porte sur un
  mandat signé.
- P27 (ADR-053 ; rapport de vérification du 12/10) : une vente `'hunter'`
  suit une offre `'accepted'` sur ce bien et ce mandat — l'offre que le
  vendeur accepte ; `'signed'` est l'offre signée par le client, pas encore
  envoyée (ADR-041). Une vente `'client_alone'` n'est pas contrôlée.
- ADR-030 (TODO du bloc `sale`) : `id_parameters_fees` est la grille en
  vigueur à la date de l'acte.

Au POST seulement, P28 (ADR-053) : la vente passe le mandat à
`'completed'`, dans la même transaction — le mandat est préparé (`stage`),
puis écrit par le commit de la vente ; si la base refuse la vente, le
mandat reste tel quel.

Non codé ici : une vente datée hors de la validité du mandat (même TODO,
avec la réserve D3 : un acte après la fin peut ouvrir droit à
rémunération).
"""

from typing import Optional

from sqlmodel import Session

from ..models import Mandate, Sale, User
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.sale_repository import SaleRepository
from ..utils.exceptions import ConflictError
from .base_service import BaseService

HUNTER_SALE = "hunter"
ACCEPTED_OFFER = "accepted"
COMPLETED = "completed"


class SaleService(BaseService[Sale]):
    def __init__(
        self,
        repository: SaleRepository,
        mandates: MandateRepository,
        offers: EstateProposedRepository,
        grids: ParametersFeesRepository,
    ):
        super().__init__(repository, not_found_detail="Vente introuvable")
        self.mandates = mandates
        self.offers = offers
        self.grids = grids

    def _check_sale(self, session: Session, item: Sale) -> Mandate:
        mandate = self.mandates.get_by_id(session, item.id_mandate)
        if mandate is None:
            raise ConflictError("Mandat introuvable (id_mandate).")
        if mandate.signature_date is None:
            raise ConflictError("Une vente porte sur un mandat signé (Q-MAN-06).")
        if item.sale_origin == HUNTER_SALE and not self.offers.exists_where(
            session, id_estate=item.id_estate, id_mandate=item.id_mandate, proposition_status=ACCEPTED_OFFER
        ):
            raise ConflictError("Une vente 'hunter' suit une offre 'accepted' sur ce bien et ce mandat (P27).")
        grid = self.grids.in_force_at(session, item.signature_date)
        if grid is None or grid.id != item.id_parameters_fees:
            in_force = "aucune" if grid is None else f"la grille {grid.id}"
            raise ConflictError(
                f"La grille d'honoraires est celle en vigueur à la date de l'acte : {in_force} (ADR-030)."
            )
        return mandate

    def create(self, session: Session, item: Sale, actor: Optional[User] = None) -> Sale:
        mandate = self._check_sale(session, item)
        mandate.status = COMPLETED
        self.mandates.stage(session, mandate)
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: Sale) -> Sale:
        existing = self.get_by_id(session, item_id)
        self._check_sale(session, data)
        return self.repository.replace(session, existing, data)
