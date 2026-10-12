"""
api_keys.py — Une clé d'API par programme appelant (ADR-028, points 4 à 6).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Deux contrôles qui ne se remplacent pas (ADR-028, point 6) :
- la CLÉ dit quel programme appelle (en-tête `X-API-Key`) ;
- le JETON dit quelle personne agit (`Authorization: Bearer`, ADR-052).

Chaque programme a sa variable d'environnement `API_KEY_<NOM>` (par exemple
`API_KEY_APP_BACKEND`). Au démarrage, ce module lit toutes les variables qui
commencent par `API_KEY_` ; sans aucune clé utilisable, l'import échoue et
l'API refuse de démarrer, plutôt que de refuser tous les appels sans dire
pourquoi.

require_api_key, posé sur les routeurs (auth_router, build_crud_router) :
clé absente ou inconnue -> 401. Le nom du programme reconnu est rangé dans
`request.state.api_client`, pour les logs. `GET /` reste ouvert.
============================================================================
"""

import hmac
import logging
import os
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

API_KEY_PREFIX = "API_KEY_"
API_KEY_HEADER = "X-API-Key"
# Même plancher que JWT_SECRET : `openssl rand -hex 32` en donne 64.
_API_KEY_MIN_LENGTH = 32


def _load_api_keys() -> dict[str, str]:
    """{nom du programme: clé}, lu dans les variables `API_KEY_<NOM>`."""
    keys: dict[str, str] = {}
    for variable, value in os.environ.items():
        if not variable.startswith(API_KEY_PREFIX):
            continue
        name = variable[len(API_KEY_PREFIX):]
        if not value:
            # Ligne laissée vide dans docker/.env : on le dit, sans bloquer.
            logger.warning("%s est vide : le programme %s ne pourra pas appeler l'API.", variable, name)
            continue
        if len(value) < _API_KEY_MIN_LENGTH:
            raise RuntimeError(
                f"{variable} trop courte ({len(value)} caractères, {_API_KEY_MIN_LENGTH} au moins) : "
                "génère-la avec `openssl rand -hex 32`."
            )
        keys[name] = value
    if not keys:
        raise RuntimeError(
            "Aucune clé d'API (variables API_KEY_<NOM>) : l'API refuserait tous les appels "
            "(ADR-028). Ajoute-les dans docker/.env (modèle : docker/.env.exemple)."
        )
    return keys


_API_KEYS = _load_api_keys()

_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def _match(candidate: str) -> Optional[str]:
    """Le nom du programme de cette clé, ou None. Temps constant par clé."""
    found: Optional[str] = None
    for name, expected in _API_KEYS.items():
        # Pas de sortie anticipée : chaque clé connue est comparée.
        if hmac.compare_digest(candidate.encode(), expected.encode()):
            found = name
    return found


def require_api_key(request: Request, key: Optional[str] = Security(_header)) -> str:
    """Dépendance FastAPI : 401 sans clé connue ; rend le nom du programme."""
    name = _match(key) if key else None
    if name is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé d'API absente ou inconnue.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    request.state.api_client = name
    return name
