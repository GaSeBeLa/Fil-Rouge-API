"""
crud_router.py — Fabrique d'APIRouter générique, partagée par les 21
routers de table.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Les 4 routes (GET liste, GET/{id}, POST, PUT/{id}) sont
strictement identiques d'une table à l'autre — seuls le service appelé, le
préfixe d'URL, le tag Swagger et le modèle de réponse changent. Plutôt que
de dupliquer ces 4 fonctions dans les 21 fichiers routers/<table>_router.py
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

Droits (ADR-028, fiche API2 ; moindre privilège, fiche DRO1) : toutes les
routes exigent un jeton (401 sans). Fermé par défaut : sans `read_roles`
ni `write_roles`, personne ne lit ni n'écrit (403). Chaque routeur déclare
donc ses rôles, lus dans l'annexe d'ADR-027
(`md/adr/adr-027-annexe-matrice-detaillee.md`) au niveau du rôle.
`read_roles` ouvre les deux GET ; `write_roles` ouvre le PUT, et le POST
quand `create_roles` est absent ; `create_roles` ouvre le seul POST. `()`
ferme le geste à tous.

« Le sien » (ADR-027, point 2 ; fiche DRO4) : les deux GET et le PUT passent
le compte connecté au service (`list_all`, `get_by_id`, `replace_visible`),
qui ne rend que les lignes de son crochet `visible_rows` (base_service.py).
Une ligne hors du crochet rend 404, comme une ligne absente. Tables qui
filtrent : payment pour le Hunter (DRO4) ; les tables du Client (DRO5,
services/client_rows.py), du Hunter (DRO6, services/hunter_rows.py) et
du Manager (DRO7, services/manager_rows.py).

Le compte connecté (fiches API6, DRO5) : le POST le passe au service,
`service.create_as(..., <compte>)`. Le service vérifie que la ligne reste à
ce compte (crochet `owns`, sinon 409), puis la crée en le nommant `actor` :
il remplit l'auteur d'une ligne ou juge un droit qui dépend de la ligne
(ForbiddenError -> 403). Le PUT rend aussi 403 sur un champ que le rôle ne
change pas (le rôle d'un compte, user_service.py).

Pas de DELETE (ADR-049, Décision 10, fiche API10) : aucune ligne ne se
supprime par l'API ; un compte s'efface par POST /users/{id}/anonymize
(user_router.py). Un DELETE reçu rend 405.

Clé d'API (ADR-028, points 4 à 6, fiche API3) : posée sur le routeur
entier, elle est vérifiée avant le jeton ; absente ou inconnue -> 401.

Doc Swagger : chaque route reçoit un `summary` (son titre dans /docs) et une
`description` écrite pour un débutant. Les rôles cités sont lus dans
`read_roles` / `write_roles` / `create_roles` : la doc suit le code, sans copie à tenir.
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
from ..utils.roles import ALL_ROLES, Principal, require_roles
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


_AUTH_ERRORS = "- `401` : clé d'API (`X-API-Key`) ou jeton absent, inconnu ou expiré."


def _who(roles: Sequence[str]) -> str:
    """Les rôles autorisés, en clair pour la doc Swagger."""
    if not roles:
        return "personne (geste fermé)"
    if tuple(roles) == ALL_ROLES:
        return "tout compte connecté"
    return ", ".join(f"`{role}`" for role in roles)


def _describe(text: str, roles: Sequence[str], responses: str) -> str:
    """Assemble la description d'une route : ce qu'elle fait, qui peut, ses réponses."""
    return f"{text}\n\n**Qui peut** : {_who(roles)}.\n\n**Réponses** :\n\n{responses}\n{_AUTH_ERRORS}"


def build_crud_router(
    *,
    service: BaseService,
    prefix: str,
    tag: str,
    response_model: Type[SQLModel],
    read_model: Optional[Type[SQLModel]] = None,
    update_model: Optional[Type[SQLModel]] = None,
    # Fermé par défaut (DRO1) : chaque routeur déclare qui lit, crée, modifie.
    read_roles: Sequence[str] = (),
    write_roles: Sequence[str] = (),
    create_roles: Optional[Sequence[str]] = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag], dependencies=[Depends(require_api_key)])

    can_read = require_roles(*read_roles)
    can_write = require_roles(*write_roles)
    can_create = require_roles(*(write_roles if create_roles is None else create_roles))

    out_model = read_model or response_model
    in_update_model = update_model or response_model
    creators = write_roles if create_roles is None else create_roles
    # PUT partiel seulement quand un modèle de mise à jour est donné (/users).
    put_rule = (
        "Un champ absent du corps **garde** sa valeur actuelle."
        if update_model is not None
        else "Envoyer **toute** la ligne : un champ absent reprend sa valeur par défaut, "
        "souvent vide. L'ancienne valeur est alors perdue."
    )

    @router.get(
        "",
        response_model=List[out_model],
        summary="Lister toutes les lignes",
        description=_describe(
            "Rend les lignes de la table, en une fois (pas de pagination). Sur une table qui "
            "réserve chaque ligne à son titulaire (« le sien »), seulement les vôtres.",
            read_roles,
            "- `200` : la liste, vide s'il n'y a rien ;\n- `403` : votre rôle ne peut pas lire cette table.",
        ),
    )
    def list_items(session: Session = Depends(get_session), viewer: Principal = Depends(can_read)):
        return service.list_all(session, viewer)

    @router.get(
        "/{item_id}",
        response_model=out_model,
        summary="Lire une ligne par son id",
        description=_describe(
            "Rend la ligne dont l'`id` est donné dans l'URL.",
            read_roles,
            "- `200` : la ligne ;\n- `403` : votre rôle ne peut pas lire cette table ;\n"
            "- `404` : aucune ligne que vous pouvez voir n'a cet `id` ;\n"
            "- `422` : l'`id` n'est pas un nombre entier.",
        ),
    )
    def get_item(item_id: int, session: Session = Depends(get_session), viewer: Principal = Depends(can_read)):
        try:
            return service.get_by_id(session, item_id, viewer)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "",
        response_model=out_model,
        status_code=201,
        summary="Créer une ligne",
        description=_describe(
            "Crée une ligne avec le corps envoyé. L'`id` envoyé est ignoré : la base le choisit.",
            creators,
            "- `201` : la ligne créée, avec son `id` ;\n"
            "- `403` : votre rôle ne peut pas créer dans cette table ;\n"
            "- `409` : la base ou une règle métier refuse la ligne (valeur en double, "
            "référence inexistante, règle d'un ADR) ; le message nomme la contrainte "
            "de la base, ou cite la règle ;\n"
            "- `422` : le corps est mal formé (champ obligatoire absent, type faux).",
        ),
    )
    def create_item(
        item: response_model,
        session: Session = Depends(get_session),
        principal: Principal = Depends(can_create),
    ):
        try:
            return service.create_as(session, _validated(response_model, item), principal)
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.put(
        "/{item_id}",
        response_model=out_model,
        summary="Modifier une ligne",
        description=_describe(
            f"Remplace la ligne dont l'`id` est donné dans l'URL. {put_rule}",
            write_roles,
            "- `200` : la ligne modifiée ;\n"
            "- `403` : votre rôle ne peut pas modifier cette table, ou ce champ ;\n"
            "- `404` : aucune ligne que vous pouvez voir n'a cet `id` ;\n"
            "- `409` : la base ou une règle métier refuse la modification ; le message dit laquelle ;\n"
            "- `422` : le corps est mal formé.",
        ),
    )
    def update_item(
        item_id: int,
        data: in_update_model,
        session: Session = Depends(get_session),
        viewer: Principal = Depends(can_write),
    ):
        try:
            return service.replace_visible(session, item_id, _validated(in_update_model, data), viewer)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    return router