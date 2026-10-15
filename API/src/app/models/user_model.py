"""
user_model.py — Table USER, racine du schéma (Hunter, Client et
RealEstateManager en dépendent tous via id_user).

Choix du groupe (2026-09) : "user" est minimaliste — uniquement
l'essentiel pour créer un compte. first_name/last_name/phone_number/
gender/country_iso ont été redescendus dans Hunter/Client/
RealEstateManager (voir ces fichiers).

Le rôle (chantier PRF) : system_role pour un compte sans fiche (Admin,
Reader), sinon role_wording de sa fiche. L'ancienne clé id_role vers la
table role est retirée par PRF8.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import EmailStr
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    __tablename__ = "user"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel
    # "user" est un mot réservé SQL ; SQLAlchemy le
    # met automatiquement entre guillemets doubles à la génération des
    # requêtes, comme le fait le script SQL — pas d'action supplémentaire
    # nécessaire de notre côté.

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    email: str = Field(max_length=150, unique=True)
    password: str = Field(max_length=255)
    # NOT NULL DEFAULT FALSE en base (88ab154, migration 13) : un None serait
    #   envoyé tel quel, et refusé.
    is_activated: bool = False
    # PRF6 : le rôle d'un compte SANS fiche, 'Admin' ou 'Reader' (CHECK côté
    # base) ; vide pour un compte qui a une fiche (trigger
    # check_one_profile_per_user : sinon 409).
    system_role: Optional[str] = Field(default=None, max_length=10)


class UserPublic(SQLModel):
    """
    Ce que l'API RENVOIE pour un utilisateur : tout, sauf `password`.

    Un mot de passe, même haché, ne sort jamais d'une API.
    """

    id: int
    created_at: datetime
    email: str
    is_activated: Optional[bool] = None
    system_role: Optional[str] = None


class UserCreate(SQLModel):
    """
    Ce que l'API ACCEPTE pour créer un compte (ADR-016).

    `password` est ici le mot de passe EN CLAIR : c'est la seule forme sous
    laquelle il entre dans le système. Il est haché dans UserService.create()
    et n'atteint jamais la base tel quel.

    Ni `id` ni `created_at` : le serveur les décide seul.

    `email` en EmailStr (P2, ADR-053) : un format faux rend 422 avant la
    base. Le domaine est mis en minuscules au passage, pas la partie avant
    `@` ; les doublons par la casse sont refusés par la base (migration 24).
    """

    email: EmailStr = Field(max_length=150)
    # min_length=12 : proposition du tuto, pas une décision actée par le
    # groupe (contrairement à ADR-016 lui-même). À confirmer en réunion.
    password: str = Field(min_length=12)
    # Omis : le compte n'est pas activé (même défaut que la base).
    is_activated: bool = False
    # PRF6 : 'Admin' ou 'Reader' pour un compte sans fiche ; omis, vide.
    system_role: Optional[str] = Field(default=None, max_length=10)


class UserUpdate(SQLModel):
    """
    Modification partielle. Tout est optionnel : on ne change que ce qui est
    fourni. Un `password` présent est haché comme à la création.
    """

    email: Optional[EmailStr] = Field(default=None, max_length=150)  # P2
    password: Optional[str] = Field(default=None, min_length=12)
    is_activated: Optional[bool] = None
    system_role: Optional[str] = Field(default=None, max_length=10)  # PRF6