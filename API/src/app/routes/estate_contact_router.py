from fastapi import Depends, HTTPException
from sqlmodel import Session

from ..conf.database import get_session
from ..models import EstateContact
from ..repositories.estate_contact_repository import EstateContactRepository
from ..services.estate_contact_service import ContactAnonymizationReport, EstateContactService
from ..utils.exceptions import ConflictError
from ..utils.roles import ADMIN, HUNTER, MANAGER, require_roles
from .crud_router import build_crud_router

# ADR-054 : le contact du vendeur est une donnée personnelle d'un tiers.
# Le chasseur et le manager en ont besoin pour joindre le vendeur ; le
# client, non (l'offre passe « par l'intermédiaire de mon chasseur »,
# user-stories/03_particulier_offre_et_signature.feature:16) ; Reader non
# plus, par minimisation.
STAFF_ROLES = (ADMIN, HUNTER, MANAGER)

_service = EstateContactService(EstateContactRepository())

router = build_crud_router(
    service=_service,
    prefix="/estate-contacts",
    tag="estate_contact",
    response_model=EstateContact,
    read_roles=STAFF_ROLES,
    write_roles=STAFF_ROLES,
)


# ADR-054, question 4 : 3 ans après la dernière activité du bien. Admin seul,
# lancée à la main, comme POST /users/{id}/anonymize (ADR-049) : le geste ne
# se défait pas et touche les contacts de tous les biens. Revue en DRO3 :
# inchangée.
@router.post(
    "/anonymize-expired",
    response_model=ContactAnonymizationReport,
    dependencies=[Depends(require_roles(ADMIN))],
    summary="Rendre anonymes les contacts sans activité depuis 3 ans",
)
def anonymize_expired_contacts(session: Session = Depends(get_session)) -> ContactAnonymizationReport:
    """Rend anonymes les contacts de vendeur dont le bien n'a plus bougé depuis **3 ans**.

    La dernière activité d'un bien est la plus récente de ces dates : création
    du bien ou du contact, sélection, proposition, fin de mandat, visite, vente.

    Rien n'est supprimé : le nom devient « Anonyme », agence, téléphone et email
    sont vidés. La case « particulier » et l'auteur restent. Rappelée, la route
    ne compte que les nouveaux.

    **Qui peut** : `Admin` seul.

    Réponses :

    - `200` : la date limite (`cutoff`) et le nombre de contacts rendus anonymes ;
    - `401` : clé d'API ou jeton absent ;
    - `403` : vous n'êtes pas `Admin` ;
    - `409` : la base refuse l'écriture.
    """
    try:
        return _service.anonymize_expired(session)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
