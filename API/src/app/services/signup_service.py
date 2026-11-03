"""
signup_service.py — Demande de recherche déposée avant le compte (P5).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Le visiteur remplit le formulaire du site : son email, son nom, son
téléphone, son adresse (P3). Sa demande doit être enregistrée tout de suite,
mais search_request.id_client exige déjà une fiche client, donc un user.

Solution recommandée de P5 (md/journal/problemes-a-regler.md), sans changer
le schéma — en UNE transaction :
  1. le user, inactif, avec un mot de passe factice qui n'est pas une
     empreinte argon2 (PENDING_SIGNUP_PASSWORD : la connexion est refusée) ;
  2. sa fiche client ;
  3. la search_request, au statut 'confirmed' (demande reçue, sans chasseur) ;
  4. sa 1re version de criteria (M2, voté le 2026-11-03, fiche SUG3) : le
     budget et le type du formulaire, le pays de l'adresse, l'auteur = le
     compte du visiteur, sans version précédente.
Les trois premières lignes sont écrites sans valider (insert_pending) ; le
commit de la quatrième valide les quatre. Un refus de la base en chemin
annule tout : rien n'est écrit.

Un email déjà connu, majuscules comprises (P2), retrouve son compte : la
demande s'y rattache, et une fiche client existante n'est PAS réécrite — un
formulaire envoyé sans connexion ne doit pas changer l'adresse d'un autre.

Même réponse pour tous (relecture de la série API6 → API10) : la route ne
dit jamais si l'email existait. Un email de chasseur, de manager ou d'admin
ne reçoit pas de fiche client (P1) : la demande est écartée sans le dire,
et notée dans les logs.

Les formats (code postal, téléphone…) ne sont jugés que par la base, quand
une fiche s'écrit. Pour qu'un formulaire mal formé rende la même réponse
quel que soit l'email (fiche DRO11, choix B de Sébastien, 2026-10-13), un
email connu rejoue d'abord le chemin d'un email neuf dans un SAVEPOINT
annulé (_probe_new_signup) : un compte jetable, sa fiche client avec les
champs du formulaire. Un refus de la base → ConflictError, comme pour un
email neuf ; sinon le chemin connu continue, sans rien réécrire. Les CHECK
ne sont pas recopiés en Python : la base reste seul juge. La sonde avance
les compteurs d'id (une séquence ne recule pas) ; rien d'autre n'en reste.

L'activation passe par PUT /users/{id} (mot de passe et is_activated) :
aucun envoi d'email ici.
============================================================================
"""

import logging
from typing import Optional
from uuid import uuid4

from pydantic import EmailStr
from sqlmodel import Field, Session, SQLModel

from ..models import Client, Criteria, SearchRequest, User
from ..models.estate_model import EstateType
from ..repositories.base_repository import discarded_writes
from ..repositories.client_repository import ClientRepository
from ..repositories.criteria_repository import CriteriaRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..repositories.user_repository import UserRepository
from ..utils.roles import HUNTER, MANAGER, profile_id_of
from ..utils.security import PENDING_SIGNUP_PASSWORD

logger = logging.getLogger(__name__)

_RECEIVED = "confirmed"  # demande reçue, pas encore de chasseur (ADR-041)

# La seule réponse de la route, quel que soit l'email.
RECEIPT = "Demande reçue."

_CLIENT_FIELDS = {
    "first_name",
    "last_name",
    "phone_number",
    "gender",
    "country_iso",
    "address",
    "address_complement",
    "postal_code",
    "town",
}


class SearchRequestSubmission(SQLModel):
    """
    Le formulaire du site. Mêmes longueurs que la table client ; l'adresse
    est obligatoire (P3). Les formats (pays, téléphone, code postal) restent
    contrôlés par la base : un refus y annule toute la transaction.
    """

    email: EmailStr = Field(max_length=150)  # P2
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone_number: str = Field(min_length=1, max_length=20)
    gender: Optional[str] = Field(default=None, max_length=10)
    country_iso: str = Field(min_length=2, max_length=2)
    address: str = Field(min_length=1, max_length=150)
    address_complement: Optional[str] = Field(default=None, max_length=150)
    postal_code: str = Field(min_length=1, max_length=10)
    town: str = Field(min_length=1, max_length=100)
    # M2 (fiche SUG3) : la 1re version des critères naît avec la demande.
    budget_max: int = Field(gt=0, description="Budget maximum, en euros")
    estate_type: EstateType


class SubmissionReceipt(SQLModel):
    """La réponse au formulaire : rien qui dise si l'email existait."""

    detail: str = RECEIPT


class SignupService:
    """Enregistre la demande d'un visiteur, compte et fiche client compris (P5)."""

    def __init__(
        self,
        users: UserRepository,
        clients: ClientRepository,
        requests: SearchRequestRepository,
        criteria: CriteriaRepository,
    ):
        self.users = users
        self.clients = clients
        self.requests = requests
        self.criteria = criteria

    def submit(self, session: Session, form: SearchRequestSubmission) -> Optional[SearchRequest]:
        """
        La demande enregistrée, avec sa 1re version de critères, ou None si
        l'email est celui d'un compte non client (rien n'est alors écrit).
        Un refus de la base lève ConflictError, et rien n'est écrit.
        """
        user = self.users.find_by_email_ignoring_case(session, form.email)
        if user is not None:
            self._probe_new_signup(session, form)
        else:
            user = self.users.insert_pending(
                session,
                User(
                    email=form.email,
                    password=PENDING_SIGNUP_PASSWORD,
                    is_activated=False,
                ),
            )
        user_id = user.id
        if user_id is None:  # posé par la base au flush ; garde pour le typage
            raise RuntimeError("Le compte n'a pas reçu d'id.")

        client = next(iter(self.clients.list_where(session, id_user=user_id)), None)
        if client is None:
            # Chantier PRF : le rôle se lit sur system_role ou sur la fiche.
            has_other_role = user.system_role is not None or any(
                profile_id_of(session, user, role) is not None for role in (HUNTER, MANAGER)
            )
            if has_other_role:
                # P1 : pas de fiche client pour un chasseur, un manager, un
                # Admin, un Reader… Rien n'est écrit, et rien n'est dit au
                # visiteur. Le log garde l'id du compte, pas l'email.
                logger.warning("Demande écartée : le compte %s n'est pas un compte client.", user_id)
                return None
            client = self.clients.insert_pending(
                session, Client(id_user=user_id, **form.model_dump(include=_CLIENT_FIELDS))
            )

        # id_client cite la fiche (client.id), id_author le compte (chantier PRF).
        if client.id is None:  # posé par la base au flush ; garde pour le typage
            raise RuntimeError("La fiche client n'a pas reçu d'id.")
        request = self.requests.insert_pending(
            session, SearchRequest(id_author=user_id, id_client=client.id, status=_RECEIVED)
        )
        if request.id is None:  # posé par la base au flush ; garde pour le typage
            raise RuntimeError("La demande n'a pas reçu d'id.")
        # Le commit des critères valide aussi le compte, la fiche et la demande.
        first = Criteria(
            id_author=user_id,
            id_search_request=request.id,
            country_iso=form.country_iso,
            estate_type=form.estate_type,
            budget_max=form.budget_max,
        )
        self.criteria.create(session, first)
        session.refresh(request)
        return request

    def _probe_new_signup(self, session: Session, form: SearchRequestSubmission) -> None:
        """
        Le chemin d'un email neuf, joué puis annulé (fiche DRO11) : la base
        juge le formulaire comme pour un inconnu. Refus → ConflictError.
        """
        with discarded_writes(session):
            probe = self.users.insert_pending(
                session,
                User(
                    # Jetable, et unique : il ne heurte aucun compte réel.
                    email=f"sonde-{uuid4().hex}@formulaire.invalid",
                    password=PENDING_SIGNUP_PASSWORD,
                    is_activated=False,
                ),
            )
            if probe.id is None:  # posé par la base au flush ; garde pour le typage
                raise RuntimeError("Le compte de la sonde n'a pas reçu d'id.")
            self.clients.insert_pending(session, Client(id_user=probe.id, **form.model_dump(include=_CLIENT_FIELDS)))
