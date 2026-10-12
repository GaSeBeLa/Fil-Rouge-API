from fastapi import Depends, HTTPException
from sqlmodel import Session

from ..conf.database import get_session
from ..models import UserCreate, UserPublic, UserUpdate
from ..repositories.user_repository import UserRepository
from ..services.anonymization_service import AnonymizationReport, AnonymizationService
from ..services.user_service import UserService
from ..utils.exceptions import ConflictError, NotFoundError
from ..utils.roles import ADMIN, require_roles
from .crud_router import build_crud_router

router = build_crud_router(
    service=UserService(UserRepository()),
    prefix="/users",
    tag="user",
    # ENTRÉE POST : UserCreate — ni id, ni created_at, mot de passe complet
    # en clair, haché par le service (ADR-016).
    response_model=UserCreate,
    # ENTRÉE PUT : UserUpdate — tous les champs optionnels, mise à jour
    # partielle réelle (voir UserService.replace).
    update_model=UserUpdate,
    # SORTIE : UserPublic — `password` ne sort jamais.
    read_model=UserPublic,
    # Admin seul écrit (relecture de la série API) : sinon tout compte
    # connecté pouvait changer le mot de passe ou le rôle d'un Admin, et
    # prendre son compte. En attendant la matrice d'ADR-027.
    write_roles=(ADMIN,),
)

_anonymizer = AnonymizationService()


# ADR-049, Décision 3 : effacer un compte = le désactiver et le rendre
# anonyme, jamais le supprimer (plus de DELETE). Admin seul. Rappelée après
# `names_kept_until`, la route finit le travail (Décision 9).
@router.post(
    "/{item_id}/anonymize",
    response_model=AnonymizationReport,
    dependencies=[Depends(require_roles(ADMIN))],
)
def anonymize_user(item_id: int, session: Session = Depends(get_session)) -> AnonymizationReport:
    try:
        return _anonymizer.anonymize(session, item_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
