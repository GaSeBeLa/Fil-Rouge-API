"""
crud_router.py — Fabrique d'APIRouter générique, partagée par les 11
routers de table.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Les 5 routes (GET liste, GET/{id}, POST, PUT/{id}, DELETE/{id}) sont
strictement identiques d'une table à l'autre — seuls le service appelé, le
préfixe d'URL, le tag Swagger et le modèle de réponse changent. Plutôt que
de dupliquer ces 5 fonctions dans les 11 fichiers routers/<table>_router.py
(comme c'était le cas dans l'ancien main.py), on les construit une fois ici
et chaque fichier de router se contente d'appeler build_crud_router avec
son propre service.

C'est aussi le seul endroit qui traduit les exceptions "métier"
(NotFoundError, ConflictError — voir exceptions.py) en codes HTTP : les
services et repositories, eux, ne connaissent pas FastAPI.
============================================================================
"""

from typing import List, Type

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel

from ..conf.database import get_session
from ..utils.exceptions import ConflictError, NotFoundError
from ..services.base_service import BaseService


def build_crud_router(
    *,
    service: BaseService,
    prefix: str,
    tag: str,
    response_model: Type[SQLModel],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("", response_model=List[response_model])
    def list_items(session: Session = Depends(get_session)):
        return service.list_all(session)

    @router.get("/{item_id}", response_model=response_model)
    def get_item(item_id: int, session: Session = Depends(get_session)):
        try:
            return service.get_by_id(session, item_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("", response_model=response_model, status_code=201)
    def create_item(item: response_model, session: Session = Depends(get_session)):
        try:
            return service.create(session, item)
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/{item_id}", response_model=response_model)
    def update_item(item_id: int, data: response_model, session: Session = Depends(get_session)):
        try:
            return service.replace(session, item_id, data)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.delete("/{item_id}", response_model=response_model)
    def delete_item(item_id: int, session: Session = Depends(get_session)):
        try:
            return service.delete(session, item_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
