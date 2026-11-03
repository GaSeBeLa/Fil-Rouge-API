"""
suggestion_service.py — Le moteur de suggestion de biens (fiche SUG8,
chantier SUG).

`SuggestionService.suggest` : pour une demande, les biens de l'index
Elasticsearch `estates` qui collent à ses derniers critères, écrits dans sa
sélection (`estate_searchrequest`) à l'état `'suggested'` (fiche SUG4). Le
chasseur les garde (`'kept'`) ou les écarte (`'dismissed'`) ensuite.

- Seul le chasseur de la demande la voit : un autre obtient NotFoundError
  (404, « le sien », fiche DRO6).
- Les critères lus sont la dernière version : celle qu'aucune autre ne cite
  dans `id_previous_version`. Aucune version : ConflictError (409).
- Ne sont jamais suggérés : un bien vendu (`sale.id_estate`), un bien déjà
  dans la sélection de la demande, quel que soit son état — un bien écarté
  ne revient pas. Ils partent dans le `must_not` de la requête
  (suggestion_query.py, SUG7), et sont refiltrés après les résultats.
- Un id de l'index absent de la base (l'index est rempli la nuit, il peut
  avoir un temps de retard) est sauté, pas écrit.
- Elasticsearch absent ou en panne : SearchUnavailable, loggée par
  estate_search_service (la route rend 503) ; rien n'est écrit.
"""

from typing import Any, Optional

from sqlmodel import Session, col, select

from ..models import Criteria, Estate, EstateSearchRequest
from ..repositories.criteria_repository import CriteriaRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.sale_repository import SaleRepository
from ..utils.exceptions import ConflictError, NotFoundError
from ..utils.roles import Principal
from .estate_search_service import search_estates
from .hunter_rows import handles_request
from .suggestion_query import query_from_criteria

# Le plafond de la fiche SUG8 : dix biens par appel, au plus.
MAX_SUGGESTIONS = 10
SUGGESTED = "suggested"


def latest_version(versions: list[Criteria]) -> Optional[Criteria]:
    """
    La dernière version de critères : celle qu'aucune autre ne cite comme
    précédente. Rend None si la liste est vide.
    """
    cited = {version.id_previous_version for version in versions}
    return next((version for version in versions if version.id not in cited), None)


class SuggestionService:
    """Propose des biens au chasseur d'une demande, depuis l'index Elasticsearch."""

    def __init__(
        self,
        criteria: CriteriaRepository,
        selection: EstateSearchRequestRepository,
        sales: SaleRepository,
    ):
        self.criteria = criteria
        self.selection = selection
        self.sales = sales

    def _excluded_estates(self, session: Session, request_id: int) -> set[int]:
        """Les biens à ne pas suggérer : les vendus, et ceux déjà dans la sélection de la demande."""
        sold = {sale.id_estate for sale in self.sales.list_all(session)}
        seen = {row.id_estate for row in self.selection.list_where(session, id_search_request=request_id)}
        return sold | seen

    @staticmethod
    def _existing_estates(session: Session, estate_ids: list[int]) -> set[int]:
        """Ceux des `estate_ids` qui existent en base ; vide si la liste l'est."""
        if not estate_ids:
            return set()
        return set(session.exec(select(Estate.id).where(col(Estate.id).in_(estate_ids))).all())

    def suggest(self, session: Session, es: Any, request_id: int, viewer: Principal) -> list[EstateSearchRequest]:
        """
        Les lignes de sélection écrites, dans l'ordre du score d'Elasticsearch,
        `MAX_SUGGESTIONS` au plus. Liste vide si rien de neuf ne colle : rien
        n'est écrit. Lève NotFoundError (demande d'un autre chasseur, ou
        inconnue), ConflictError (aucun critère), SearchUnavailable
        (Elasticsearch absent).
        """
        if not handles_request(session, viewer.profile_id, request_id):
            raise NotFoundError(f"Demande {request_id} introuvable.")
        criteria = latest_version(list(self.criteria.list_where(session, id_search_request=request_id)))
        if criteria is None:
            raise ConflictError("La demande n'a aucun critère : rien à suggérer.")

        excluded = self._excluded_estates(session, request_id)
        query = query_from_criteria(criteria, sorted(excluded))
        found = search_estates(es, query, page=1, size=MAX_SUGGESTIONS)["items"]
        candidates = [item["id"] for item in found if item["id"] not in excluded]
        existing = self._existing_estates(session, candidates)
        estate_ids = [i for i in candidates if i in existing][:MAX_SUGGESTIONS]

        rows = [
            EstateSearchRequest(id_estate=i, id_search_request=request_id, id_hunter=viewer.profile_id, status=SUGGESTED)
            for i in estate_ids
        ]
        if not rows:
            return []
        # Une seule transaction : les premières attendent le commit de la
        # dernière ; un refus de la base les annule toutes.
        for row in rows[:-1]:
            self.selection.insert_pending(session, row)
        self.selection.create(session, rows[-1])
        for row in rows[:-1]:
            session.refresh(row)
        return rows
