"""
client_rows.py — Les lignes d'un client, suivies par les clés du schéma.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
« Le sien » du Client (ADR-027, annexe, colonne Client ; fiche DRO5). Tout
part de son compte : `search_request.id_client` et `mandate.id_client`
pointent sur `client.id_user`, donc sur l'id du compte (schéma
`docker/init-v3/01_create_fil_rouge_immobilier.sql`). Le reste descend de
là :

- ses demandes (search_request.id_client) : leurs critères, leurs avis
  (estate_searchrequest) et les médias de ces avis (review_media) ;
- ses mandats (mandate.id_client) : leurs biens proposés (estate_proposed),
  leurs visites, leur vente ;
- les biens proposés pour lui (Q-ACC-05) : estate, et leurs photos ;
- son chasseur (P2) : celui d'un de ses mandats ou d'une de ses demandes.

Les fonctions en `_of` rendent une sous-requête : le crochet `visible_rows`
d'un service la place dans un `IN`, et le filtre se fait dans la base.
`owns_request` et `owns_mandate` servent aux écritures : ce qu'un client
écrit doit rester à lui (crochet `owns`, base_service.py).
============================================================================
"""

from typing import Any, Optional

from sqlmodel import Session, col, select
from sqlmodel.sql.expression import SelectOfScalar

from ..models import EstateProposed, EstateSearchRequest, Mandate, SearchRequest

# Une sous-requête qui rend des ids ; sqlmodel la type selon la colonne.
IdQuery = SelectOfScalar[Any]


def requests_of(user_id: Optional[int]) -> IdQuery:
    """Les ids des demandes du client."""
    return select(SearchRequest.id).where(SearchRequest.id_client == user_id)


def mandates_of(user_id: Optional[int]) -> IdQuery:
    """Les ids des mandats du client."""
    return select(Mandate.id).where(Mandate.id_client == user_id)


def reviews_of(user_id: Optional[int]) -> IdQuery:
    """Les ids des avis (estate_searchrequest) posés sur ses demandes (P5)."""
    return select(EstateSearchRequest.id).where(col(EstateSearchRequest.id_search_request).in_(requests_of(user_id)))


def estates_proposed_to(user_id: Optional[int]) -> IdQuery:
    """Les ids des biens proposés sur un de ses mandats (Q-ACC-05)."""
    return select(EstateProposed.id_estate).where(col(EstateProposed.id_mandate).in_(mandates_of(user_id)))


def hunters_of(user_id: Optional[int]) -> tuple[IdQuery, IdQuery]:
    """Les comptes de ses chasseurs : ceux de ses mandats, ceux de ses demandes (P2)."""
    return (
        select(Mandate.id_hunter).where(Mandate.id_client == user_id),
        select(SearchRequest.id_hunter).where(SearchRequest.id_client == user_id),
    )


def owns_request(session: Session, user_id: Optional[int], request_id: Optional[int]) -> bool:
    """Vrai si la demande `request_id` est au client."""
    return session.exec(requests_of(user_id).where(SearchRequest.id == request_id)).first() is not None


def owns_mandate(session: Session, user_id: Optional[int], mandate_id: Optional[int]) -> bool:
    """Vrai si le mandat `mandate_id` est au client."""
    return session.exec(mandates_of(user_id).where(Mandate.id == mandate_id)).first() is not None
