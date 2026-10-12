"""
crud_router.py — Fabrique d'APIRouter générique, partagée par les 18
routers de table.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Les 4 routes (GET liste, GET/{id}, POST, PUT/{id}) sont
strictement identiques d'une table à l'autre — seuls le service appelé, le
préfixe d'URL, le tag Swagger et le modèle de réponse changent. Plutôt que
de dupliquer ces 4 fonctions dans les 18 fichiers routers/<table>_router.py
(comme c'était le cas dans l'ancien main.py), on les construit une fois ici
et chaque fichier de router se contente d'appeler build_crud_router avec
son propre service.

C'est aussi le seul endroit qui traduit les exceptions "métier"
(NotFoundError, ConflictError, ForbiddenError — voir exceptions.py) en
codes HTTP : les services et repositories, eux, ne connaissent pas FastAPI.

`update_model` (optionnel) : modèle d'entrée du PUT, distinct de celui du
POST (`response_model`). Par défaut, si non fourni, le PUT utilise
`response_model` — comportement inchangé pour les tables qui ne le
précisent pas. À utiliser quand une mise à jour partielle a du sens
(champs optionnels) alors que la création exige des champs complets — voir
UserUpdate dans user_router.py.

Validation de l'entrée (POST, PUT) : un modèle de TABLE SQLModel ne valide
pas ce que FastAPI lui passe — mesuré le 2026-10-05 : un prix `199999.5`
était arrondi en silence à 200 000 par PostgreSQL, un champ obligatoire
manquant finissait en 409. `_validated` revalide donc le corps avec
`model_validate`, qui, lui, valide : une entrée invalide rend 422, avant
d'atteindre la base.

Droits (ADR-028, fiche API2) : toutes les routes exigent un jeton (401
sans). Les GET sont ouverts à tout compte connecté ; POST et PUT sont
refusés à `Reader` (403), qui lit sans écrire. `write_roles` restreint
POST et PUT pour une table : `()` les ferme à tous (hunter_performance,
ADR-035) ; users : `Admin` seul. La
matrice complète des droits (ADR-027) n'est pas codée. `create_roles`
restreint le seul POST (estate : Hunter et Manager, ADR-047) ; absent, le
POST suit `write_roles`.

Le compte connecté (fiche API6) : le POST le passe au service,
`service.create(..., actor=<compte>)`, qui s'en sert pour remplir l'auteur
d'une ligne ou juger un droit qui dépend de la ligne (ForbiddenError -> 403).

Pas de DELETE (ADR-049, Décision 10, fiche API10) : aucune ligne ne se
supprime par l'API ; un compte s'efface par POST /users/{id}/anonymize
(user_router.py). Un DELETE reçu rend 405.

Clé d'API (ADR-028, points 4 à 6, fiche API3) : posée sur le routeur
entier, elle est vérifiée avant le jeton ; absente ou inconnue -> 401.
============================================================================
"""

from collections.abc import Sequence
from typing import List, Optional, Type

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlmodel import Session, SQLModel

from ..conf.database import get_session
from ..models.input_check import INPUT_CONTEXT
from ..utils.api_keys import require_api_key
from ..utils.exceptions import ConflictError, ForbiddenError, NotFoundError
from ..utils.roles import ALL_ROLES, WRITER_ROLES, Principal, require_roles
from ..services.base_service import BaseService


def _validated(model: Type[SQLModel], item: SQLModel) -> SQLModel:
    """Revalide le corps reçu ; une erreur devient un 422 standard de FastAPI."""
    try:
        # exclude_unset : un champ absent reste absent (PUT partiel, défauts).
        # warnings=False : l'objet brut porte des valeurs non converties.
        # context : les règles d'entrée (P16, P29, P32) ne jugent que ce passage.
        return model.model_validate(item.model_dump(exclude_unset=True, warnings=False), context=INPUT_CONTEXT)
    except ValidationError as exc:
        # loc préfixé par "body", comme les 422 que FastAPI produit lui-même.
        # include_input=False : le corps reçu n'est pas recopié dans la
        # réponse ; un NaN qu'il contiendrait ne s'écrit pas en JSON (500).
        errors = [
            {**e, "loc": ("body", *e["loc"])}
            for e in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise RequestValidationError(errors) from exc


def build_crud_router(
    *,
    service: BaseService,
    prefix: str,
    tag: str,
    response_model: Type[SQLModel],
    read_model: Optional[Type[SQLModel]] = None,
    update_model: Optional[Type[SQLModel]] = None,
    write_roles: Sequence[str] = WRITER_ROLES,
    create_roles: Optional[Sequence[str]] = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag], dependencies=[Depends(require_api_key)])

    can_read = [Depends(require_roles(*ALL_ROLES))]
    can_write = [Depends(require_roles(*write_roles))]
    can_create = require_roles(*(write_roles if create_roles is None else create_roles))

    out_model = read_model or response_model
    in_update_model = update_model or response_model

    @router.get("", response_model=List[out_model], dependencies=can_read)
    def list_items(session: Session = Depends(get_session)):
        return service.list_all(session)

    @router.get("/{item_id}", response_model=out_model, dependencies=can_read)
    def get_item(item_id: int, session: Session = Depends(get_session)):
        try:
            return service.get_by_id(session, item_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("", response_model=out_model, status_code=201)
    def create_item(
        item: response_model,
        session: Session = Depends(get_session),
        principal: Principal = Depends(can_create),
    ):
        try:
            return service.create(session, _validated(response_model, item), actor=principal.user)
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.put("/{item_id}", response_model=out_model, dependencies=can_write)
    def update_item(item_id: int, data: in_update_model, session: Session = Depends(get_session)):
        try:
            return service.replace(session, item_id, _validated(in_update_model, data))
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router