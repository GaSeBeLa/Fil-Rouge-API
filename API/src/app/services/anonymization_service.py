"""
anonymization_service.py — Effacer un compte sans supprimer de ligne (ADR-049).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
anonymize() sert POST /users/{id}/anonymize, réservée à l'Admin (ADR-049,
Décision 3). Dans l'ordre :
  1. le compte est désactivé : plus de connexion (Décision 1) ;
  2. ce que rien n'oblige à garder devient anonyme TOUT DE SUITE (Décisions
     4, 6 et 7) : email, mot de passe, téléphone, adresse, naissance et
     situation, textes écrits par la personne. Une colonne obligatoire
     reçoit une valeur neutre au bon format, les autres sont vidées ;
  3. prénom et nom deviennent « Anonyme » seulement quand le plus long délai
     qui concerne la personne est fini (Décision 5) : 10 ans après la fin du
     dernier mandat de la chaîne (décret, article 72) ou après le paiement
     (obligation comptable). Aucun délai : tout de suite. Sinon le rapport
     dit jusqu'à quand ils restent.

La même route, rappelée après ce jour, finit le travail (Décision 9) : tout
est rejoué, et ce qui est déjà anonyme le reste. Pas de tâche planifiée
(V2). Une seule transaction : les lignes modifiées sont préparées (stage),
le commit du compte les écrit toutes, ou aucune.
============================================================================
"""

from collections.abc import Iterable, Sequence
from datetime import date
from typing import List, Optional, TypeVar

from sqlmodel import Session, SQLModel

from ..models import Mandate
from ..repositories.client_repository import ClientRepository
from ..repositories.criteria_repository import CriteriaRepository
from ..repositories.estate_proposed_repository import EstateProposedRepository
from ..repositories.hunter_repository import HunterRepository
from ..repositories.mandate_repository import MandateRepository
from ..repositories.payment_repository import PaymentRepository
from ..repositories.real_estate_manager_repository import RealEstateManagerRepository
from ..repositories.user_repository import UserRepository
from ..utils.exceptions import NotFoundError

# Décision 5 : mandats (décret, article 72) et paiements (obligation comptable).
RETENTION_YEARS = 10

# Décision 7 : les valeurs neutres, au format que la base exige.
ANONYMOUS_NAME = "Anonyme"
ANONYMOUS_TEXT = "anonyme"
ANONYMOUS_PHONE = "+33000000000"  # valeur factice déjà admise (Q-MIG-07)
ANONYMOUS_POSTAL_CODE = "00000"
ANONYMOUS_COUNTRY = "FR"
# Pas une empreinte argon2 : verify_password la refuse, comme le placeholder
# des comptes repris (utils/security.py).
ANONYMIZED_PASSWORD = "!ANONYMIZED_NO_LOGIN"

_PAID = "paid"
_REFUSED = "refused"

RowT = TypeVar("RowT")


class AnonymizationReport(SQLModel):
    id_user: int
    names_anonymized: bool
    # Fin du plus long délai (Décision 5) : rappeler la route après ce jour.
    names_kept_until: Optional[date] = None


def plus_years(day: date, years: int) -> date:
    """Même jour, `years` ans plus tard ; un 29 février devient un 28."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def names_kept_until(reference_dates: Iterable[date]) -> Optional[date]:
    """
    Le jour où finit le plus long délai : la plus tardive des dates de
    référence, plus 10 ans. None s'il n'y en a aucune : rien n'oblige à
    garder le nom.
    """
    latest = max(reference_dates, default=None)
    return None if latest is None else plus_years(latest, RETENTION_YEARS)


def _first(rows: Sequence[RowT]) -> Optional[RowT]:
    return rows[0] if rows else None


class AnonymizationService:
    def __init__(self) -> None:
        # Repositories sans état : le service crée les siens.
        self.users = UserRepository()
        self.clients = ClientRepository()
        self.hunters = HunterRepository()
        self.managers = RealEstateManagerRepository()
        self.mandates = MandateRepository()
        self.payments = PaymentRepository()
        self.criteria = CriteriaRepository()
        self.offers = EstateProposedRepository()

    def anonymize(self, session: Session, user_id: int, today: Optional[date] = None) -> AnonymizationReport:
        today = today or date.today()
        user = self.users.get_by_id(session, user_id)
        if user is None:
            raise NotFoundError("Utilisateur introuvable")

        until = names_kept_until(self._retention_dates(session, user_id, today))
        names_free = until is None or until <= today

        user.is_activated = False
        user.email = f"anonyme-{user_id}@exemple.invalid"  # unique par construction
        user.password = ANONYMIZED_PASSWORD

        client = _first(self.clients.list_where(session, id_user=user_id))
        hunter = _first(self.hunters.list_where(session, id_user=user_id))
        manager = _first(self.managers.list_where(session, id_user=user_id))
        for profile in (client, hunter, manager):
            if profile is not None:
                profile.phone_number = ANONYMOUS_PHONE
                if names_free:
                    profile.first_name = ANONYMOUS_NAME
                    profile.last_name = ANONYMOUS_NAME
        if hunter is not None:
            self.hunters.stage(session, hunter)
        if manager is not None:
            self.managers.stage(session, manager)
        if client is not None:
            self.clients.stage(session, client)
            client.address = ANONYMOUS_TEXT
            client.address_complement = None
            client.postal_code = ANONYMOUS_POSTAL_CODE
            client.town = ANONYMOUS_TEXT
            client.country_iso = ANONYMOUS_COUNTRY
            client.birth_date = None
            client.gender = None
            client.is_married = None
            client.is_civil_solidarity_pact = None
            client.nb_children = None

        self._clear_written_texts(session, user_id)
        self.users.save(session, user)  # le commit écrit tout, ou rien
        return AnonymizationReport(
            id_user=user_id,
            names_anonymized=names_free,
            names_kept_until=None if names_free else until,
        )

    def _retention_dates(self, session: Session, user_id: int, today: date) -> List[date]:
        """Les dates d'où part un délai de 10 ans pour cette personne (Décision 5)."""
        dates: List[date] = []
        mandates = [
            *self.mandates.list_where(session, id_client=user_id),
            *self.mandates.list_where(session, id_hunter=user_id),
        ]
        for mandate in mandates:
            # Un mandat jamais signé n'a pas de fin : il n'entre pas au registre.
            end = self._last_of_chain(session, mandate).ends_at
            if end is not None:
                dates.append(end)
        for payment in self.payments.list_where(session, id_hunter=user_id):
            if payment.status == _PAID and payment.paid_at is not None:
                dates.append(payment.paid_at.date())
            elif payment.status != _REFUSED:
                # Annoncé ou programmé, pas encore versé : le délai n'a pas
                # commencé, il part au plus tôt d'aujourd'hui.
                dates.append(today)
        return dates

    def _last_of_chain(self, session: Session, mandate: Mandate) -> Mandate:
        """Le dernier renouvellement du mandat (id_mandate_parent, UNIQUE)."""
        current, seen = mandate, {mandate.id}
        while (child := _first(self.mandates.list_where(session, id_mandate_parent=current.id))) is not None:
            if child.id in seen:  # garde contre une boucle
                break
            current = child
            seen.add(child.id)
        return current

    def _clear_written_texts(self, session: Session, user_id: int) -> None:
        """Les textes écrits par la personne (Décision 7), vidés tout de suite."""
        for mandate in self.mandates.list_where(session, id_client=user_id):
            for offer in self.offers.list_where(session, id_mandate=mandate.id):
                offer.comment_client = None
                self.offers.stage(session, offer)
        for version in self.criteria.list_where(session, id_author=user_id):
            # chk_criteria_change_reason : une révision garde un motif, neutre.
            version.change_reason = None if version.id_previous_version is None else ANONYMOUS_TEXT
            self.criteria.stage(session, version)
