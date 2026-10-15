"""
estate_search_service.py — Chercher des biens dans l'index Elasticsearch `estates`.

Chantier FLX, fiche FLX9. L'index est rempli chaque nuit par le DAG
estates_index (FLX8, airflow/src/search/) ; l'API ne fait que le lire.

- `build_query` : la requête `bool` du TP1 du cours ELK — le texte libre dans
  `must` (il compte pour le score), tout le reste dans `filter` (oui ou non,
  sans score). Fonction pure, testée sans Elasticsearch.
- `get_es_client` : le client, lu dans l'environnement (ES_URL, ES_API_USER,
  ES_API_PASSWORD : compte en lecture seule `api_search`, créé par es-setup,
  jamais `elastic`). Non configuré : SearchUnavailable.
- `search_estates` : lance la recherche. Elasticsearch absent ou en panne :
  l'erreur est loggée et SearchUnavailable est levée — la route rend 503,
  jamais une liste vide qui ferait croire qu'aucun bien ne correspond.
"""

import logging
import os
from functools import lru_cache
from typing import Any, Optional

from elasticsearch import ApiError, Elasticsearch, TransportError

logger = logging.getLogger(__name__)

INDEX = "estates"


class SearchUnavailable(Exception):
    """Elasticsearch absent, non configuré ou en panne."""


def build_query(
    q: Optional[str] = None,
    city: Optional[str] = None,
    postal_code: Optional[str] = None,
    estate_type: Optional[str] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    surface_min: Optional[float] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_km: Optional[float] = None,
) -> dict[str, Any]:
    """La requête `bool` : `must` pour le texte, `filter` pour le reste."""
    must: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []
    if q:
        # Champ analysé en `french` (mapping de FLX8).
        must.append({"match": {"information": q}})
    for field, value in (("town", city), ("postal_code", postal_code), ("estate_type", estate_type)):
        if value:
            filters.append({"term": {field: value}})
    price = {k: v for k, v in (("gte", price_min), ("lte", price_max)) if v is not None}
    if price:
        filters.append({"range": {"price": price}})
    if surface_min is not None:
        filters.append({"range": {"surface": {"gte": surface_min}}})
    if lat is not None and lon is not None and radius_km is not None:
        filters.append({"geo_distance": {"distance": f"{radius_km}km", "location": {"lat": lat, "lon": lon}}})
    if not must and not filters:
        return {"match_all": {}}
    return {"bool": {"must": must, "filter": filters}}


@lru_cache(maxsize=1)
def _client(url: str, user: str, password: str) -> Elasticsearch:
    return Elasticsearch(url, basic_auth=(user, password), request_timeout=10)


def get_es_client() -> Elasticsearch:
    """Dépendance FastAPI : le client Elasticsearch, ou SearchUnavailable."""
    url, user, password = (os.getenv(name, "") for name in ("ES_URL", "ES_API_USER", "ES_API_PASSWORD"))
    if not (url and user and password):
        logger.error("Recherche indisponible : ES_URL, ES_API_USER ou ES_API_PASSWORD manque")
        raise SearchUnavailable("Elasticsearch n'est pas configuré")
    return _client(url, user, password)


def search_estates(es: Elasticsearch, query: dict[str, Any], page: int, size: int) -> dict[str, Any]:
    """Une page de résultats : total, et les biens (id + champs de l'index)."""
    try:
        res = es.search(index=INDEX, query=query, from_=(page - 1) * size, size=size,
                        track_total_hits=True)
    except (ApiError, TransportError) as exc:
        logger.error("Recherche Elasticsearch en échec : %r", exc)
        raise SearchUnavailable("Elasticsearch ne répond pas") from exc
    hits = res["hits"]
    return {
        "total": hits["total"]["value"],
        "page": page,
        "size": size,
        "items": [{**hit["_source"], "id": int(hit["_id"])} for hit in hits["hits"]],
    }
