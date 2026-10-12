"""
version_service.py — Une version de paramètres, figée dès qu'elle est citée
(ADR-030, ADR-034).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Grille d'honoraires, ligne de barème, réglages du taux : chaque vente et
chaque paiement garde l'id de la version qui a servi au calcul, pour que le
calcul reste explicable plus tard. Modifier cette version après coup
changerait, sans le dire, l'explication d'un montant déjà annoncé.

Donc : tant qu'aucune ligne ne la cite, la version se corrige (`PUT` -> 200) ;
dès qu'une vente ou un paiement la cite, elle est figée (`PUT` -> 409). Une
nouvelle valeur, c'est une nouvelle version (`POST`).

`cited_by` liste où chercher : (repository de la table qui cite, nom de la
clé étrangère). La suppression, elle, est déjà refusée par la clé étrangère.
============================================================================
"""

from collections.abc import Sequence

from sqlmodel import Session

from ..repositories.base_repository import BaseRepository
from ..utils.exceptions import ConflictError
from .base_service import BaseService, ModelType


class FrozenOnceCitedService(BaseService[ModelType]):
    def __init__(
        self,
        repository: BaseRepository[ModelType],
        not_found_detail: str,
        cited_by: Sequence[tuple[BaseRepository, str]],
    ):
        super().__init__(repository, not_found_detail)
        self.cited_by = cited_by

    def replace(self, session: Session, item_id: int, data: ModelType) -> ModelType:
        existing = self.get_by_id(session, item_id)
        for citing, foreign_key in self.cited_by:
            if citing.exists_with(session, foreign_key, item_id):
                raise ConflictError(
                    f"Version déjà citée ({citing.model.__name__}.{foreign_key}) : "
                    "elle ne se modifie plus, crée une nouvelle version (ADR-030, ADR-034)."
                )
        return self.repository.replace(session, existing, data)
