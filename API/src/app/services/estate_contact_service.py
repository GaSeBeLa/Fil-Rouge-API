"""
estate_contact_service.py — Le contact du vendeur d'un bien, et qui l'a
saisi (ADR-054).

Même règle d'auteur que estate_service.py (ADR-047) :
- create : `id_author` est le compte connecté, jamais la valeur reçue ;
  sans compte (un script), il reste vide : contact importé ;
- replace : `id_author` garde la valeur en base.

Un second contact pour le même bien, ou un bien inexistant, est refusé par
la base (UNIQUE, clé étrangère) : 409.

Lecture et écriture sont réservées à Admin, Hunter et Manager par le
routeur (routes/estate_contact_router.py).

Effacement à 3 ans (ADR-054, question 4, tranché le 13/10/2026) :
`anonymize_expired` rend anonymes les contacts dont le bien n'a eu aucune
activité depuis 3 ans (création, sélection, proposition, fin de mandat,
visite, vente). Comme ADR-049 : la ligne reste, le nom devient « Anonyme »,
agence, téléphone et email sont vidés ; `is_private` et l'auteur restent.
Route Admin, lancée à la main : pas de tâche planifiée (V2).
"""

from datetime import date
from typing import Optional

from sqlmodel import Session, SQLModel

from ..models import EstateContact, User
from ..repositories.estate_contact_repository import EstateContactRepository
from .anonymization_service import ANONYMOUS_NAME, plus_years
from .base_service import BaseService

# ADR-054, question 4 : 3 ans après la dernière activité du bien.
CONTACT_RETENTION_YEARS = 3


class ContactAnonymizationReport(SQLModel):
    # Les contacts dont le bien n'a plus bougé depuis ce jour sont anonymes.
    cutoff: date
    anonymized: int


def is_anonymous(contact: EstateContact) -> bool:
    return (
        contact.contact_name == ANONYMOUS_NAME
        and contact.agency_name is None
        and contact.phone_number is None
        and contact.email is None
    )


class EstateContactService(BaseService[EstateContact]):
    def __init__(self, repository: EstateContactRepository):
        super().__init__(repository, not_found_detail="Contact introuvable")
        self.contacts = repository  # typé : ses méthodes propres, pour pyright

    def create(self, session: Session, item: EstateContact, actor: Optional[User] = None) -> EstateContact:
        item.id_author = actor.id if actor is not None else None
        return super().create(session, item, actor)

    def replace(self, session: Session, item_id: int, data: EstateContact) -> EstateContact:
        existing = self.get_by_id(session, item_id)
        data.id_author = existing.id_author
        return self.repository.replace(session, existing, data)

    def anonymize_expired(self, session: Session, today: Optional[date] = None) -> ContactAnonymizationReport:
        """
        Rend anonymes les contacts sans activité depuis 3 ans, en une
        transaction. Rejouée, elle ne compte que les nouveaux.
        """
        cutoff = plus_years(today or date.today(), -CONTACT_RETENTION_YEARS)
        anonymized = 0
        for contact_id in self.contacts.ids_inactive_since(session, cutoff):
            contact = self.get_by_id(session, contact_id)
            if is_anonymous(contact):
                continue
            # ck_estate_contact_not_empty : une ligne garde un renseignement,
            # le nom neutre.
            contact.contact_name = ANONYMOUS_NAME
            contact.agency_name = None
            contact.phone_number = None
            contact.email = None
            self.repository.stage(session, contact)
            anonymized += 1
        self.contacts.commit(session)  # tout, ou rien
        return ContactAnonymizationReport(cutoff=cutoff, anonymized=anonymized)
