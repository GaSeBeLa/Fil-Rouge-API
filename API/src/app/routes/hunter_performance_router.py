from fastapi import Depends, HTTPException
from sqlmodel import Session

from ..conf.database import get_session
from ..models import HunterPerformance
from ..repositories.hunter_performance_repository import HunterPerformanceRepository
from ..services.hunter_performance_service import ExpiredMandatesReport, HunterPerformanceService
from ..utils.exceptions import ConflictError
from ..utils.roles import ADMIN, HUNTER, MANAGER, READER, require_roles
from .crud_router import build_crud_router
from .payment_router import calculation

_service = HunterPerformanceService(HunterPerformanceRepository())

router = build_crud_router(
    service=_service,
    prefix="/hunter-performances",
    tag="hunter_performance",
    response_model=HunterPerformance,
    # ADR-027, annexe § 4 : lue par le chasseur (H12), son manager,
    # l'Admin et Reader ; le client n'y a pas accès.
    read_roles=(ADMIN, HUNTER, MANAGER, READER),
    # ADR-035 : la performance d'un chasseur n'est jamais saisie à la main ;
    # POST et PUT fermés à tous ; la note 'payment' s'écrit quand un
    # paiement passe à 'paid' (PaymentService, fiche API12), la note
    # 'mandate_expired' par la route ci-dessous.
    write_roles=(),
)


# Choix PERF-EXP (Sébastien, 2026-11-23) : Admin seul, lancée à la main,
# comme POST /estate-contacts/anonymize-expired ; elle touche les mandats
# de tous les chasseurs.
@router.post(
    "/expired-mandates",
    response_model=ExpiredMandatesReport,
    dependencies=[Depends(require_roles(ADMIN))],
    summary="Noter les mandats expirés qui n'ont pas encore leur note",
)
def score_expired_mandates(session: Session = Depends(get_session)) -> ExpiredMandatesReport:
    """Écrit la note `mandate_expired` de chaque mandat `expired` qui n'en a pas encore.

    Le sujet veut qu'un mandat fini sans vente fasse **baisser** la note du
    chasseur. La note est datée de la fin du mandat (ADR-048, point 8) :

    - les trois notes de vente (délai, exclusivité, visites) viennent du
      dernier paiement payé du chasseur, ou valent **50** s'il n'y en a pas ;
    - les deux critères d'activité (ventes, taux de réussite des mandats)
      sont recomptés ce jour-là : le mandat expiré compte sans vente.

    Les mandats passent en `expired` chaque nuit (tâche Airflow
    `mandate_expiry`). Rappelée, la route ne note que les nouveaux.

    **Qui peut** : `Admin` seul.

    Réponses :

    - `200` : le nombre de mandats notés et leurs références ;
    - `401` : clé d'API ou jeton absent ;
    - `403` : vous n'êtes pas `Admin` ;
    - `409` : paramétrage incomplet à la fin d'un mandat, ou la base refuse
      l'écriture ; rien n'est écrit.
    """
    try:
        return _service.score_expired_mandates(session, calculation)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
