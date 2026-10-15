"""
estate_search_router.py — GET /estates/search : chercher un bien (FLX9).

Lit l'index Elasticsearch `estates` (services/estate_search_service.py).
Mêmes droits que la lecture des biens (routes/estate_router.py) : tous les
rôles connectés, avec la clé d'API.

⚠️ Inclus dans main.py AVANT estate_router : sinon `GET /estates/{id}`
capte « search » comme un id et rend 422.

La réponse rend l'`id` et les champs de l'index ; le détail d'un bien reste
`GET /estates/{id}`. Elasticsearch absent ou en panne : 503.
"""

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..services import estate_search_service as search
from ..utils.api_keys import require_api_key
from ..utils.roles import ALL_ROLES, Principal, require_roles

router = APIRouter(prefix="/estates", tags=["estate"], dependencies=[Depends(require_api_key)])

# Valeurs du CHECK de estate.estate_type (init-v3/01).
EstateType = Literal["Appartement", "Maison", "Studio", "Loft", "Villa", "Duplex", "Terrain",
                     "Local commercial", "Chalet", "Château"]

UNAVAILABLE = "La recherche de biens est indisponible : Elasticsearch ne répond pas. Réessayer plus tard."


def _es():
    """Le client, ou 503 si Elasticsearch n'est pas configuré."""
    try:
        return search.get_es_client()
    except search.SearchUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE)


@router.get(
    "/search",
    summary="Chercher des biens (Elasticsearch)",
    description=(
        "Recherche dans l'index `estates`, rempli chaque nuit par le DAG `estates_index`. "
        "`q` cherche dans le texte de l'annonce (analyseur français) ; les autres paramètres "
        "filtrent. `lat`, `lon` et `radius_km` vont ensemble. Tous les rôles connectés. "
        "503 si Elasticsearch ne répond pas."
    ),
    responses={503: {"description": "Elasticsearch absent ou en panne"}},
)
def search_estates(
    q: Optional[str] = Query(None, max_length=200, description="Texte libre"),
    city: Optional[str] = Query(None, max_length=100, description="Ville, telle qu'en base"),
    postal_code: Optional[str] = Query(None, max_length=10),
    type: Optional[EstateType] = Query(None, description="Type de bien"),
    price_min: Optional[int] = Query(None, ge=0, description="Euros"),
    price_max: Optional[int] = Query(None, ge=0, description="Euros"),
    surface_min: Optional[float] = Query(None, gt=0, description="m²"),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0, le=500),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    viewer: Principal = Depends(require_roles(*ALL_ROLES)),
    es: Any = Depends(_es),
) -> dict[str, Any]:
    geo = (lat, lon, radius_km)
    if any(v is not None for v in geo) and not all(v is not None for v in geo):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="lat, lon et radius_km vont ensemble : les trois, ou aucun.")
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="price_min dépasse price_max.")
    query = search.build_query(q, city, postal_code, type, price_min, price_max,
                               surface_min, lat, lon, radius_km)
    try:
        return search.search_estates(es, query, page, size)
    except search.SearchUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE)
