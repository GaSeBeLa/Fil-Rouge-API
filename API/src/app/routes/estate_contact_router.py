from ..models import EstateContact
from ..repositories.estate_contact_repository import EstateContactRepository
from ..services.estate_contact_service import EstateContactService
from ..utils.roles import ADMIN, HUNTER, MANAGER
from .crud_router import build_crud_router

# ADR-054 : le contact du vendeur est une donnée personnelle d'un tiers.
# Le chasseur et le manager en ont besoin pour joindre le vendeur ; le
# client, non (l'offre passe « par l'intermédiaire de mon chasseur »,
# user-stories/03_particulier_offre_et_signature.feature:16) ; Reader non
# plus, par minimisation.
STAFF_ROLES = (ADMIN, HUNTER, MANAGER)

router = build_crud_router(
    service=EstateContactService(EstateContactRepository()),
    prefix="/estate-contacts",
    tag="estate_contact",
    response_model=EstateContact,
    read_roles=STAFF_ROLES,
    write_roles=STAFF_ROLES,
)
