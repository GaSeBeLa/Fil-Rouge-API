"""
manager_rows.py — Les lignes de l'équipe d'un manager, suivies par les clés du schéma.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
« Le sien » du Manager (ADR-027, annexe, colonne Manager et « L'équipe d'un
manager » ; fiche DRO7). Son équipe : ses chasseurs
(`hunter.id_realestatemanager`) et les demandes qui lui sont confiées
(`search_request.id_realestatemanager`) ; les deux clés pointent sur
`real_estate_manager.id_user`, donc sur l'id de son compte
(`docker/init-v3/01_create_fil_rouge_immobilier.sql`).

- les demandes de l'équipe : celles de ses chasseurs, et celles qui lui sont
  confiées ; leurs critères ;
- les mandats de l'équipe : ceux de ses chasseurs, et ceux des demandes qui
  lui sont confiées ; leurs visites, leur vente ;
- ce qui suit un chasseur (paiement, note, barème) : ses chasseurs.

Il lit le travail de son équipe, pas l'identité des clients : client,
sélection et avis lui restent fermés au niveau du rôle (fiche DRO1).

Les chemins d'un chasseur viennent de hunter_rows.py, appelés avec la
sous-requête de ses chasseurs. Les fonctions `team_requests` et
`team_mandates` rendent deux sous-requêtes : `in_team` les réunit en une
condition SQL, pour le crochet `visible_rows` d'un service.
============================================================================
"""

from typing import Any, Optional

from sqlalchemy import ColumnElement, or_
from sqlmodel import Session, col, select

from ..models import Hunter, Mandate, SearchRequest
from .client_rows import IdQuery
from .hunter_rows import mandates_handled_by, requests_handled_by


def hunters_of_team(manager_id: Optional[int]) -> IdQuery:
    """Les comptes de ses chasseurs (Q-ACC-02)."""
    return select(Hunter.id_user).where(Hunter.id_realestatemanager == manager_id)


def requests_entrusted_to(manager_id: Optional[int]) -> IdQuery:
    """Les ids des demandes qui lui sont confiées."""
    return select(SearchRequest.id).where(SearchRequest.id_realestatemanager == manager_id)


def team_requests(manager_id: Optional[int]) -> tuple[IdQuery, IdQuery]:
    """Les demandes de l'équipe : celles de ses chasseurs, celles qui lui sont confiées."""
    return requests_handled_by(hunters_of_team(manager_id)), requests_entrusted_to(manager_id)


def team_mandates(manager_id: Optional[int]) -> tuple[IdQuery, IdQuery]:
    """Les mandats de l'équipe : ceux de ses chasseurs, ceux des demandes qui lui sont confiées."""
    on_entrusted = select(Mandate.id).where(col(Mandate.id_search_request).in_(requests_entrusted_to(manager_id)))
    return mandates_handled_by(hunters_of_team(manager_id)), on_entrusted


def in_team(column: Any, queries: tuple[IdQuery, ...]) -> ColumnElement[bool]:
    """La condition « `column` est dans l'une de ces sous-requêtes »."""
    return or_(*(col(column).in_(query) for query in queries))


def leads_hunter(session: Session, manager_id: Optional[int], hunter_id: Optional[int]) -> bool:
    """Vrai si le chasseur `hunter_id` est de son équipe."""
    return session.exec(hunters_of_team(manager_id).where(Hunter.id_user == hunter_id)).first() is not None


def team_has_mandate(session: Session, manager_id: Optional[int], mandate_id: Optional[int]) -> bool:
    """Vrai si le mandat `mandate_id` est de son équipe."""
    query = select(Mandate.id).where(Mandate.id == mandate_id, in_team(Mandate.id, team_mandates(manager_id)))
    return session.exec(query).first() is not None
