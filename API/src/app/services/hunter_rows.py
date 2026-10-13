"""
hunter_rows.py — Les lignes d'un chasseur, suivies par les clés du schéma.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
« Le sien » du Hunter (ADR-027, annexe, colonne Hunter ; fiche DRO6). Tout
part de son compte : les `id_hunter` du schéma pointent sur `hunter.id_user`,
donc sur l'id du compte (`docker/init-v3/01_create_fil_rouge_immobilier.sql`).

- ses demandes (search_request.id_hunter) : leurs critères ;
- ses mandats (mandate.id_hunter) : leurs visites, leur vente ;
- ses notes (estate_searchrequest.id_hunter) : leurs médias ;
- ses clients (H3) : ceux d'une de ses demandes ou d'un de ses mandats ;
- son manager : hunter.id_realestatemanager.

Les fonctions en `_by` et `_of` rendent une sous-requête, placée dans un `IN`
par le crochet `visible_rows` d'un service : le filtre se fait dans la base.
`handles_request` et `handles_mandate` servent aux écritures (crochet `owns`,
base_service.py). Le pendant du Client : client_rows.py.
============================================================================
"""

from typing import Optional

from sqlmodel import Session, select

from ..models import EstateSearchRequest, Hunter, Mandate, SearchRequest
from .client_rows import IdQuery


def requests_handled_by(user_id: Optional[int]) -> IdQuery:
    """Les ids des demandes du chasseur (H1, H2)."""
    return select(SearchRequest.id).where(SearchRequest.id_hunter == user_id)


def mandates_handled_by(user_id: Optional[int]) -> IdQuery:
    """Les ids des mandats du chasseur."""
    return select(Mandate.id).where(Mandate.id_hunter == user_id)


def reviews_by(user_id: Optional[int]) -> IdQuery:
    """Les ids des notes (estate_searchrequest) écrites par le chasseur (H7)."""
    return select(EstateSearchRequest.id).where(EstateSearchRequest.id_hunter == user_id)


def clients_of(user_id: Optional[int]) -> tuple[IdQuery, IdQuery]:
    """Les comptes de ses clients : ceux de ses demandes, ceux de ses mandats (H3)."""
    return (
        select(SearchRequest.id_client).where(SearchRequest.id_hunter == user_id),
        select(Mandate.id_client).where(Mandate.id_hunter == user_id),
    )


def manager_of(user_id: Optional[int]) -> IdQuery:
    """Le compte de son manager."""
    return select(Hunter.id_realestatemanager).where(Hunter.id_user == user_id)


def handles_request(session: Session, user_id: Optional[int], request_id: Optional[int]) -> bool:
    """Vrai si la demande `request_id` est au chasseur."""
    return session.exec(requests_handled_by(user_id).where(SearchRequest.id == request_id)).first() is not None


def handles_mandate(session: Session, user_id: Optional[int], mandate_id: Optional[int]) -> bool:
    """Vrai si le mandat `mandate_id` est au chasseur."""
    return session.exec(mandates_handled_by(user_id).where(Mandate.id == mandate_id)).first() is not None
