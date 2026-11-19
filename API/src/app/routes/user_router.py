from fastapi import Depends, HTTPException
from sqlmodel import Session, SQLModel

from ..conf.database import get_session
from ..models import UserCreate, UserPublic, UserUpdate
from ..repositories.user_repository import UserRepository
from ..services.activation_service import ActivationService
from ..services.anonymization_service import AnonymizationReport, AnonymizationService
from ..services.user_service import UserService
from ..utils.exceptions import ConflictError, NotFoundError
from ..utils.roles import ADMIN, ALL_ROLES, CLIENT, HUNTER, MANAGER, Principal, require_roles
from ..utils.security import ACTIVATION_TOKEN_TTL
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
    # ADR-027, annexe § 1 : tout compte lit, un Client, un Hunter ou un
    # Manager son seul compte (DRO5, DRO6, DRO7). Le PUT : l'Admin, et le
    # Client, le Hunter ou le Manager sur son compte, sans rôle ni activation (UserService,
    # ADMIN_ONLY_FIELDS -> 403) ; le compte d'un autre rend 404. Le client
    # crée « son compte » (Q-ACC-12) par POST /search-requests/submit, sans
    # jeton (signup_router.py) : ouvrir ce POST au rôle Client lui
    # laisserait choisir system_role, donc créer un Admin (PRF7).
    read_roles=ALL_ROLES,
    write_roles=(ADMIN, CLIENT, HUNTER, MANAGER),
    create_roles=(ADMIN,),
)

_anonymizer = AnonymizationService()


# ADR-049, Décision 3 : effacer un compte = le désactiver et le rendre
# anonyme, jamais le supprimer (plus de DELETE). Admin seul : le geste ne se
# défait pas, et vise le compte de n'importe qui. Rappelée après
# `names_kept_until`, la route finit le travail (Décision 9). Revue en DRO3 :
# inchangée.
@router.post(
    "/{item_id}/anonymize",
    response_model=AnonymizationReport,
    dependencies=[Depends(require_roles(ADMIN))],
    summary="Effacer un compte (le rendre anonyme)",
)
def anonymize_user(item_id: int, session: Session = Depends(get_session)) -> AnonymizationReport:
    """Efface un compte comme le veut le RGPD : il est **désactivé** et rendu **anonyme**.

    Rien n'est supprimé de la base : l'API n'a plus de `DELETE` (ADR-049).

    - **Tout de suite** : email, mot de passe, téléphone, adresse, naissance et
      commentaires deviennent anonymes. Le compte ne peut plus se connecter.
    - **Prénom et nom** : effacés tout de suite si rien n'oblige à les garder.
      Sinon, ils sont gardés **10 ans** après la fin du dernier mandat ou le
      paiement (obligation comptable). La réponse donne cette date dans
      `names_kept_until` : rappeler la route après ce jour finit le travail.

    **Qui peut** : `Admin` seul.

    Réponses :

    - `200` : ce qui a été fait (`names_anonymized`, `names_kept_until`) ;
    - `401` : clé d'API ou jeton absent ;
    - `403` : vous n'êtes pas `Admin` ;
    - `404` : aucun compte n'a cet `id` ;
    - `409` : la base refuse l'écriture.
    """
    try:
        return _anonymizer.anonymize(session, item_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


_activations = ActivationService()


class ActivationCode(SQLModel):
    code: str
    expires_in: int  # secondes


# User story 01 (@creation-compte) : le particulier finalise lui-même son
# compte, avec ce code et POST /auth/activate. Le code ne s'obtient que pour
# un compte créé par le formulaire et jamais activé ; un Manager, seulement
# pour un client dont il gère une demande. Ajouté le 2026-11-19 (trou trouvé
# par Gabriel : seul un Admin pouvait activer).
@router.post(
    "/{item_id}/activation-code",
    response_model=ActivationCode,
    summary="Obtenir le code d'activation d'un compte créé par le formulaire",
)
def activation_code(
    item_id: int,
    principal: Principal = Depends(require_roles(ADMIN, MANAGER)),
    session: Session = Depends(get_session),
) -> ActivationCode:
    """Rend le **code d'activation** d'un compte créé par le formulaire du site, valable 7 jours.

    Le particulier l'envoie à `POST /auth/activate` avec le mot de passe qu'il
    choisit : son compte s'active, sans Admin. Nous n'avons pas de serveur
    d'email : l'API rend le code à l'appelant, qui le transmet (dans la vraie
    vie, c'est le lien du mail de notification).

    **Qui peut** : `Admin`, ou le `Manager` d'une demande de ce client.

    Réponses :

    - `200` : le code (`code`) et sa durée en secondes (`expires_in`) ;
    - `401` : clé d'API ou jeton absent ;
    - `403` : vous n'êtes ni `Admin` ni `Manager` ;
    - `404` : aucun compte en attente d'activation n'a cet `id`, ou vous ne
      gérez aucune demande de ce client (la réponse ne dit pas lequel).
    """
    try:
        code = _activations.issue_code(session, principal, item_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ActivationCode(code=code, expires_in=int(ACTIVATION_TOKEN_TTL.total_seconds()))
