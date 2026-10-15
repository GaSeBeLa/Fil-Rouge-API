"""
hunter_model.py — Spécialisation "chasseur immobilier" de User.

Rappel du choix de modélisation du groupe : "id" est une clé primaire
technique indépendante, "id_user" est le lien logique vers User (UNIQUE
côté base). Objectif : découpler la clé technique de cette table de la
façon dont "user.id" est généré (portabilité en cas de changement de
SGBD). Toutes les FK du reste du schéma pointent vers id, le numéro de
fiche (chantier PRF, 2026-10-15 ; vers id_user avant) — même choix pour
Client et RealEstateManager (voir client_model.py,
real_estate_manager_model.py).

Les sept champs communs aux trois fiches (created_at, id_user,
first_name, last_name, phone_number, gender, country_iso) viennent
d'AbstractPerson (abstract_person_model.py) ; id_user est redéclaré ici
pour garder sa description Swagger.
"""

from datetime import date
from typing import Optional

from sqlmodel import Field

from .abstract_person_model import AbstractPerson
from .field_descriptions import HUNTER_ID, HUNTER_USER, MANAGER_ACCOUNT


class Hunter(AbstractPerson, table=True):
    __tablename__ = "hunter"  # pyright: ignore[reportAssignmentType] -- même motif que les autres modèles SQLModel

    id: Optional[int] = Field(description=HUNTER_ID, default=None, primary_key=True)
    id_user: int = Field(description=HUNTER_USER, foreign_key="user.id", unique=True)
    company_name: Optional[str] = Field(default=None, max_length=80)
    # hire_date : NOT NULL en base. Pour les 6 chasseurs migres, la valeur
    # retenue est la date de creation du compte — hypothese assumee,
    # a confirmer (docker/init-v3/README.md §3.4).
    hire_date: date
    education_level: Optional[str] = Field(default=None, max_length=20)
    # La « carte T » (carte professionnelle d'agent immobilier). Renommée
    # depuis le nom replié du MPD le 2026-10-07 (Q-SCH-10).
    is_carte_t: Optional[bool] = None
    certification_date: Optional[date] = None
    # is_hunter_ai : le chasseur est-il l'agent automatique ?
    is_hunter_ai: Optional[bool] = None
    # Le manager du chasseur (MPD 03 4, 2026-09-22). NOT NULL en base, FK
    # vers real_estate_manager.id — le numero de fiche, pas un id de "user",
    # comme toutes les FK vers les fiches (chantier PRF). Meme nom tout en minuscules que dans
    # search_request_model.py, ou il designe le manager de la demande.
    id_realestatemanager: int = Field(description=MANAGER_ACCOUNT, foreign_key="real_estate_manager.id")
