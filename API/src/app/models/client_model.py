"""
client_model.py — Spécialisation "client" de User.

Même choix de modélisation que Hunter (voir hunter_model.py) : "id" est
une clé primaire technique indépendante, "id_user" est le lien logique
vers User (UNIQUE côté base).

Les sept champs communs aux trois fiches (created_at, id_user,
first_name, last_name, phone_number, gender, country_iso) viennent
d'AbstractPerson (abstract_person_model.py) ; id_user est redéclaré ici
pour garder sa description Swagger.

country_iso est redéclaré obligatoire : l'adresse du client l'est
(ADR-053, P3), alors qu'il est facultatif dans AbstractPerson.
"""

from datetime import date
from typing import Optional

from sqlmodel import Field

from .abstract_person_model import AbstractPerson
from .field_descriptions import CLIENT_ID, CLIENT_USER


class Client(AbstractPerson, table=True):
    __tablename__ = "client"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(description=CLIENT_ID, default=None, primary_key=True)
    id_user: int = Field(description=CLIENT_USER, foreign_key="user.id", unique=True)
    # Adresse, code postal, ville et pays : obligatoires (ADR-053, P3). Les
    # clients repris ont 'non renseigne' et '00000' (Q-SCH-18) ; un client
    # rendu anonyme, 'anonyme', '00000', 'anonyme', 'FR' (ADR-049).
    country_iso: str = Field(max_length=2)  # pyright: ignore[reportIncompatibleVariableOverride] -- voulu : obligatoire pour le client (ADR-053), facultatif dans AbstractPerson
    address: str = Field(max_length=150)
    address_complement: Optional[str] = Field(default=None, max_length=150)
    # CHECK cote base : format par pays ; l'Eircode s'ecrit sans espace,
    # ex. D02X285 (ck_client_postal_code_format, Q-SCH-12).
    postal_code: str = Field(max_length=10)
    town: str = Field(max_length=100)
    is_married: Optional[bool] = None
    is_civil_solidarity_pact: Optional[bool] = None
    nb_children: Optional[int] = None
    birth_date: Optional[date] = None
