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
  3. la search_request, au statut 'confirmed' (demande reçue, sans chasseur).
Les deux premières lignes sont écrites sans valider (insert_pending) ; le
commit de la troisième valide les trois. Un refus de la base en chemin
annule tout : rien n'est écrit.

Un email déjà connu, majuscules comprises (P2), retrouve son compte : la
demande s'y rattache, et une fiche client existante n'est PAS réécrite — un
formulaire envoyé sans connexion ne doit pas changer l'adresse d'un autre.

Même réponse pour tous (relecture de la série API6 → API10) : la route ne
dit jamais si l'email existait. Un email de chasseur, de manager ou d'admin
ne reçoit pas de fiche client (P1) : la demande est écartée sans le dire,
et notée dans les logs. Limite connue : les formats (code postal, téléphone)
ne sont contrôlés que par la base, et seulement quand une fiche s'écrit ;
un formulaire mal formé donne donc 409 pour un email neuf, 202 pour un
email connu.

L'activation passe par PUT /users/{id} (mot de passe et is_activated) :
aucun envoi d'email ici.
============================================================================
"""

import logging
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, Session, SQLModel

from ..models import Client, SearchRequest, User
from ..repositories.client_repository import ClientRepository
from ..repositories.role_repository import RoleRepository
from ..repositories.search_request_repository import SearchRequestRepository
from ..repositories.user_repository import UserRepository
from ..utils.roles import CLIENT
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


class SubmissionReceipt(SQLModel):
    """La réponse au formulaire : rien qui dise si l'email existait."""

    detail: str = RECEIPT


class SignupService:
    """Enregistre la demande d'un visiteur, compte et fiche client compris (P5)."""

    def __init__(
        self,
        users: UserRepository,
        clients: ClientRepository,
        roles: RoleRepository,
        requests: SearchRequestRepository,
    ):
        self.users = users
        self.clients = clients
        self.roles = roles
        self.requests = requests

    def submit(self, session: Session, form: SearchRequestSubmission) -> Optional[SearchRequest]:
        """La demande enregistrée, ou None si l'email est celui d'un compte non client."""
        client_role_id = self._client_role_id(session)
        user = self.users.find_by_email_ignoring_case(session, form.email)
        if user is None:
            user = self.users.insert_pending(
                session,
                User(
                    email=form.email,
                    password=PENDING_SIGNUP_PASSWORD,
                    is_activated=False,
                    id_role=client_role_id,
                ),
            )
        user_id = user.id
        if user_id is None:  # posé par la base au flush ; garde pour le typage
            raise RuntimeError("Le compte n'a pas reçu d'id.")

        if not self.clients.exists_with(session, "id_user", user_id):
            if user.id_role != client_role_id:
                # P1 : pas de fiche client pour un chasseur, un manager… Rien
                # n'est écrit, et rien n'est dit au visiteur. Le log garde
                # l'id du compte, pas l'email.
                logger.warning("Demande écartée : le compte %s n'est pas un compte client.", user_id)
                return None
            self.clients.insert_pending(
                session, Client(id_user=user_id, **form.model_dump(include=_CLIENT_FIELDS))
            )

        # Le commit de la demande valide aussi le compte et la fiche en attente.
        request = SearchRequest(id_author=user_id, id_client=user_id, status=_RECEIVED)
        return self.requests.create(session, request)

    def _client_role_id(self, session: Session) -> int:
        role = self.roles.get_by_wording(session, CLIENT)
        if role is None or role.id is None:
            raise RuntimeError(f"Rôle '{CLIENT}' absent de la table role (posé par 02_migration.sql).")
        return role.id
