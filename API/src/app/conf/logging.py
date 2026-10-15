"""
logging.py — Le log d'accès de l'API : une ligne JSON par requête (FLX10).

Chaque requête donne une ligne aux noms ECS (Elastic Common Schema), que
Logstash relit telle quelle (codec json, docker/logstash/pipeline/api.conf)
et range dans le data stream logs-api-default :

    {"@timestamp": "...", "http": {"request": {"method": "GET"},
     "response": {"status_code": 200}}, "url": {"path": "/estates/search"},
     "event": {"duration": 1234567}, "user": {"roles": ["Client"]}}

- event.duration : en nanosecondes, comme le veut ECS.
- Jamais le jeton, le mot de passe, un e-mail, ni la chaîne de requête ou le
  corps : seuls la méthode, le chemin, le code, la durée et le rôle sortent.
- Le rôle n'est connu qu'après get_principal (utils/roles.py) : il le dépose
  par note_role() dans une case ouverte par le middleware pour la requête.
- Console toujours ; fichier en plus si ACCESS_LOG_FILE est posée
  (docker-compose.yml : volume api_logs, lu par Logstash). Les handlers sont
  posés au démarrage d'uvicorn : les tests, qui n'en déclenchent pas, ne
  remplissent pas le fichier.
"""

import json
import logging
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import WatchedFileHandler
from typing import Optional

from fastapi import Request

access_logger = logging.getLogger("api.access")
access_logger.setLevel(logging.INFO)
# Pas de remontée vers le logger racine : la console a son propre handler.
access_logger.propagate = False

# Une case par requête ; dict partagé, car les dépendances synchrones
# tournent dans une copie du contexte (threadpool).
_request_slot: ContextVar[Optional[dict[str, str]]] = ContextVar("api_access_slot", default=None)


def note_role(role: str) -> None:
    """Appelée par get_principal : le rôle de la requête en cours, pour le log."""
    slot = _request_slot.get()
    if slot is not None:
        slot["role"] = role


def access_record(method: str, path: str, status_code: int, duration_ns: int,
                  role: Optional[str]) -> dict[str, object]:
    """La ligne d'un appel, aux noms ECS. Rien d'autre n'y entre."""
    record: dict[str, object] = {
        "@timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "http": {"request": {"method": method}, "response": {"status_code": status_code}},
        "url": {"path": path},
        "event": {"duration": duration_ns},
    }
    if role is not None:
        record["user"] = {"roles": [role]}
    return record


async def access_log_middleware(request: Request, call_next):
    """Middleware HTTP : mesure la requête et écrit sa ligne."""
    slot: dict[str, str] = {}
    token = _request_slot.set(slot)
    start = time.perf_counter_ns()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        _request_slot.reset(token)
        record = access_record(request.method, request.url.path, status_code,
                               time.perf_counter_ns() - start, slot.get("role"))
        access_logger.info(json.dumps(record, ensure_ascii=False))


def setup_access_log() -> None:
    """Pose les handlers : console, et fichier si ACCESS_LOG_FILE est posée."""
    if access_logger.handlers:
        return
    plain = logging.Formatter("%(message)s")
    console = logging.StreamHandler()
    console.setFormatter(plain)
    access_logger.addHandler(console)
    path = os.getenv("ACCESS_LOG_FILE")
    if path:
        try:
            handler = WatchedFileHandler(path, encoding="utf-8")
        except OSError as exc:
            logging.getLogger(__name__).error("Log d'accès : fichier %s impossible à ouvrir (%s)", path, exc)
            return
        handler.setFormatter(plain)
        access_logger.addHandler(handler)
