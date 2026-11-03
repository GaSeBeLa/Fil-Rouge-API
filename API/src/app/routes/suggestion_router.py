"""
suggestion_router.py — POST /search-requests/{item_id}/suggestions : le
moteur de suggestion de biens (fiche SUG8, chantier SUG).

Le travail est dans services/suggestion_service.py. Le client Elasticsearch
vient de la même dépendance que GET /estates/search (`_es`,
routes/estate_search_router.py) : Elasticsearch non configuré, 503.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..conf.database import get_session
from ..models import EstateSearchRequest
from ..repositories.criteria_repository import CriteriaRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.sale_repository import SaleRepository
from ..services.estate_search_service import SearchUnavailable
from ..services.suggestion_service import SuggestionService
from ..utils.api_keys import require_api_key
from ..utils.exceptions import ConflictError, NotFoundError
from ..utils.roles import HUNTER, Principal, require_roles
from .estate_search_router import UNAVAILABLE, _es

router = APIRouter(prefix="/search-requests", tags=["search_request"], dependencies=[Depends(require_api_key)])

_service = SuggestionService(CriteriaRepository(), EstateSearchRequestRepository(), SaleRepository())


# La docstring ci-dessous est affichée telle quelle dans le Swagger (/docs).
@router.post(
    "/{item_id}/suggestions",
    response_model=list[EstateSearchRequest],
    status_code=status.HTTP_201_CREATED,
    summary="Suggérer des biens pour une demande",
    responses={503: {"description": "Elasticsearch absent ou en panne"}},
)
def suggest_estates(
    item_id: int,
    session: Session = Depends(get_session),
    es: Any = Depends(_es),
    # Le chasseur cherche les biens de ses demandes (H3).
    principal: Principal = Depends(require_roles(HUNTER)),
) -> list[EstateSearchRequest]:
    """Cherche dans l'index des biens ceux qui collent aux derniers critères de la demande.

    Écrit **jusqu'à 10 biens** dans la sélection de la demande, à l'état
    `suggested`. Le chasseur les garde (`kept`) ou les écarte (`dismissed`)
    ensuite, par `PUT /estate-search-requests/{id}`.

    Ne suggère jamais un bien **vendu**, ni un bien **déjà dans la sélection**
    de cette demande, même écarté.

    **Qui peut** : le `Hunter` de la demande, seul.

    Réponses :

    - `201` : les biens écrits (liste vide si rien de neuf ne colle) ;
    - `403` : vous n'êtes pas `Hunter` ;
    - `404` : la demande n'existe pas, ou n'est pas à vous ;
    - `409` : la demande n'a aucun critère ;
    - `503` : Elasticsearch ne répond pas ; rien n'est écrit.
    """
    try:
        return _service.suggest(session, es, item_id, principal)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SearchUnavailable as exc:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from exc
