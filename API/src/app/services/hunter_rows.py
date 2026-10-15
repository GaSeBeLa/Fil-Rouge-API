"""
hunter_rows.py — Les lignes d'un chasseur, suivies par les clés du schéma.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
« Le sien » du Hunter (ADR-027, annexe, colonne Hunter ; fiche DRO6). Tout
part de sa fiche : les `id_hunter` du schéma pointent sur `hunter.id`, le
numéro de fiche (chantier PRF, 2026-10-15 ; sur `hunter.id_user` avant), que
`Principal.profile_id` porte (`docker/init-v3/01_create_fil_rouge_immobilier.sql`).

- ses demandes (search_request.id_hunter) : leurs critères ;
- ses mandats (mandate.id_hunter) : leurs visites, leur vente ;
- ses notes (estate_searchrequest.id_hunter) : leurs médias ;
- ses clients (H3) : ceux d'une de ses demandes ou d'un de ses mandats ;
- son manager : hunter.id_realestatemanager.

Les fonctions en `_by` et `_of` rendent une sous-requête, placée dans un `IN`
par le crochet `visible_rows` d'un service : le filtre se fait dans la base.
`handles_request` et `handles_mandate` servent aux écritures (crochet `owns`,
base_service.py). Le pendant du Client : client_rows.py.

`requests_handled_by` et `mandates_handled_by` prennent un chasseur (son id)
ou plusieurs (une sous-requête d'ids) : l'équipe d'un manager reprend ainsi
les chemins du chasseur (fiche DRO7, manager_rows.py).
============================================================================
"""

from typing import Any, Optional, Union

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, select
from sqlmodel.sql.expression import SelectOfScalar

from ..models import EstateSearchRequest, Hunter, Mandate, SearchRequest
from .client_rows import IdQuery

# Un chasseur (le numéro de sa fiche), ou plusieurs (une sous-requête d'ids).
Hunters = Union[Optional[int], IdQuery]


def is_hunter(column: Any, hunters: Hunters) -> ColumnElement[bool]:
    """La condition « `column` est ce chasseur », ou « l'un de ces chasseurs »."""
    if isinstance(hunters, SelectOfScalar):
        return col(column).in_(hunters)
    return col(column) == hunters


def requests_handled_by(hunters: Hunters) -> IdQuery:
    """Les ids des demandes du chasseur (H1, H2), ou de ces chasseurs."""
    return select(SearchRequest.id).where(is_hunter(SearchRequest.id_hunter, hunters))


def mandates_handled_by(hunters: Hunters) -> IdQuery:
    """Les ids des mandats du chasseur, ou de ces chasseurs."""
    return select(Mandate.id).where(is_hunter(Mandate.id_hunter, hunters))


def reviews_by(hunter_id: Optional[int]) -> IdQuery:
    """Les ids des notes (estate_searchrequest) écrites par le chasseur (H7)."""
    return select(EstateSearchRequest.id).where(EstateSearchRequest.id_hunter == hunter_id)


def clients_of(hunter_id: Optional[int]) -> tuple[IdQuery, IdQuery]:
    """Les fiches (client.id) de ses clients : celles de ses demandes, de ses mandats (H3)."""
    return (
        select(SearchRequest.id_client).where(SearchRequest.id_hunter == hunter_id),
        select(Mandate.id_client).where(Mandate.id_hunter == hunter_id),
    )


def manager_of(hunter_id: Optional[int]) -> IdQuery:
    """La fiche (real_estate_manager.id) de son manager."""
    return select(Hunter.id_realestatemanager).where(Hunter.id == hunter_id)


def handles_request(session: Session, hunter_id: Optional[int], request_id: Optional[int]) -> bool:
    """Vrai si la demande `request_id` est au chasseur."""
    return session.exec(requests_handled_by(hunter_id).where(SearchRequest.id == request_id)).first() is not None


def handles_mandate(session: Session, hunter_id: Optional[int], mandate_id: Optional[int]) -> bool:
    """Vrai si le mandat `mandate_id` est au chasseur."""
    return session.exec(mandates_handled_by(hunter_id).where(Mandate.id == mandate_id)).first() is not None
