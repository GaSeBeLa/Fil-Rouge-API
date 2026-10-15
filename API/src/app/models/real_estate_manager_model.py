"""
real_estate_manager_model.py — Spécialisation "gestionnaire immobilier"
de User.

Même choix de modélisation que Hunter (voir hunter_model.py) : "id" est
une clé primaire technique indépendante, "id_user" est le lien logique
vers User (UNIQUE côté base).

Les sept champs communs aux trois fiches (created_at, id_user,
first_name, last_name, phone_number, gender, country_iso) viennent
d'AbstractPerson (abstract_person_model.py) ; id_user est redéclaré ici
pour garder sa description Swagger.
"""

from typing import Optional

from sqlmodel import Field

from .abstract_person_model import AbstractPerson
from .field_descriptions import MANAGER_ID, MANAGER_USER


class RealEstateManager(AbstractPerson, table=True):
    __tablename__ = "real_estate_manager"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(description=MANAGER_ID, default=None, primary_key=True)
    id_user: int = Field(description=MANAGER_USER, foreign_key="user.id", unique=True)
    company_name: Optional[str] = Field(default=None, max_length=80)
