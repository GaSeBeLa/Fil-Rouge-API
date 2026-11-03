"""
estate_proposed_router.py — Les biens proposés au client : le CRUD commun, et
la route de l'offre du client (fiche SUG6).
"""

from fastapi import Depends, HTTPException
from sqlmodel import Field, Session, SQLModel

from ..conf.database import get_session
from ..models import EstateProposed
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.estate_search_request_repository import EstateSearchRequestRepository
from ..repositories.mandate_repository import MandateRepository
from ..services.estate_proposed_service import EstateProposedService
from ..utils.exceptions import ConflictError, NotFoundError
from ..utils.roles import ADMIN, CLIENT, HUNTER, READER, Principal, require_roles
from .crud_router import build_crud_router

_service = EstateProposedService(EstateProposedRepository(), MandateRepository(), EstateSearchRequestRepository())

router = build_crud_router(
    service=_service,
    prefix="/estate-proposed",
    tag="estate_proposed",
    response_model=EstateProposed,
    # ADR-027, annexe § 3 : proposé par le chasseur (H5, H9) ; le client
    # commente, priorise, fait une offre (H6, H8). Le manager ne lit pas
    # la sélection : minimisation (REGISTRE-RGPD.md:9).
    read_roles=(ADMIN, CLIENT, HUNTER, READER),
    write_roles=(CLIENT, HUNTER),
    create_roles=(HUNTER,),
)


class OfferRequest(SQLModel):
    """Le corps de l'offre : le seul montant, en euros entiers (Q-REM-01)."""

    amount_proposition: int = Field(gt=0, description="Montant de l'offre, en euros")


# Fiche SUG6, sur le modèle de POST /sales/{item_id}/payment. La docstring
# ci-dessous est affichée telle quelle dans le Swagger (/docs).
@router.post(
    "/{item_id}/offer",
    response_model=EstateProposed,
    summary="Faire une offre sur un bien proposé",
)
def make_offer(
    item_id: int,
    body: OfferRequest,
    session: Session = Depends(get_session),
    # ADR-027, annexe § 3 : le client fait une offre (H6, H8).
    principal: Principal = Depends(require_roles(CLIENT)),
) -> EstateProposed:
    """Le client fait une offre d'achat sur un bien que son chasseur lui a proposé.

    Elle écrit **en une fois** :

    - le montant de l'offre, en euros ;
    - le statut `offer_pending` (l'offre attend la réponse du vendeur) ;
    - sa décision `interested`, datée de maintenant.

    **Qui peut** : le `Client` du mandat, seul.

    Réponses :

    - `200` : la proposition, avec son offre ;
    - `403` : vous n'êtes pas `Client` ;
    - `404` : la proposition n'existe pas, ou n'est pas sur un de vos mandats ;
    - `409` : la proposition n'est plus `proposed` (une offre est déjà faite) ;
    - `422` : le montant manque, ou n'est pas plus grand que 0.
    """
    try:
        return _service.make_offer(session, item_id, body.amount_proposition, principal)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
