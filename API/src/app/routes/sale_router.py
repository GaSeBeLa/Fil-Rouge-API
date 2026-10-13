from fastapi import Depends, HTTPException
from sqlmodel import Session

from ..conf.database import get_session
from ..models import Payment, Sale
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.parameters_fees_repository import ParametersFeesRepository
from ..repositories.sale_repository import SaleRepository
from ..services.sale_service import SaleService
from ..utils.exceptions import ConflictError, NotFoundError
from ..utils.roles import WRITER_ROLES, Principal, require_roles
from .crud_router import build_crud_router
from .payment_router import calculation, payment_service

router = build_crud_router(
    service=SaleService(SaleRepository(), MandateRepository(), EstateProposedRepository(), ParametersFeesRepository()),
    prefix="/sales",
    tag="sale",
    response_model=Sale,
)


# Fiche API12. La docstring ci-dessous est affichée telle quelle dans le
# Swagger (/docs) : elle s'adresse à qui appelle la route. Le paiement passe
# ensuite par PaymentService.create, donc ADR-038 et P33 s'appliquent aussi.
@router.post(
    "/{item_id}/payment",
    response_model=Payment,
    status_code=201,
    summary="Calculer le paiement d'une vente",
)
def create_sale_payment(
    item_id: int,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_roles(*WRITER_ROLES)),
) -> Payment:
    """Calcule la commission du chasseur pour cette vente, puis l'enregistre.

    **On n'envoie aucun montant** : l'API le calcule elle-même, depuis la base.

    Ce qu'elle fait, dans l'ordre :

    1. Elle compte les visites, les ventes et les mandats du chasseur (ADR-048).
    2. Elle charge les paramètres en vigueur à la date de l'acte (barème, honoraires, réglages).
    3. Elle appelle `calculer_remuneration`, le calcul donné par le sujet.
    4. Elle crée le paiement au statut `announced`.
       Si le chasseur n'y a pas droit, le paiement est créé `refused`,
       avec son motif dans `refusal_reason` (ADR-024).

    Réponses :

    - `201` : le paiement créé, avec le détail du calcul ;
    - `404` : la vente n'existe pas ;
    - `409` : la vente a déjà un paiement, ou un paramètre manque.

    Une vente n'a qu'un paiement. La suite se fait par `PUT /payments/{id}` :
    `announced` → `scheduled` → `paid` (ADR-038).
    """
    try:
        payment = calculation.build_payment(session, item_id)
        return payment_service.create(session, payment, actor=principal.user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
