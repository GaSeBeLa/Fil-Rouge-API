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


# Fiche API12 : le paiement d'une vente se calcule depuis la base, jamais
# saisi à la main. Compte les visites, ventes et mandats, charge le
# paramétrage à la date de l'acte, appelle calculer_remuneration, puis crée
# le paiement 'announced' (ou 'refused') par PaymentService : ADR-038 et
# P33 s'appliquent. Vente déjà payée -> 409 (un paiement par vente).
@router.post("/{item_id}/payment", response_model=Payment, status_code=201)
def create_sale_payment(
    item_id: int,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_roles(*WRITER_ROLES)),
) -> Payment:
    try:
        payment = calculation.build_payment(session, item_id)
        return payment_service.create(session, payment, actor=principal.user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
