"""
estate_model.py — Les biens immobiliers (annonces) proposés aux clients.

Deux choses à savoir avant d'écrire du code sur cette table :

- **`price` est en euros entiers**, `INTEGER`, donc `int` ici (Q-REM-01,
  2026-10-05) : un prix n'a pas de centimes. ⚠️ Un prix à virgule n'est
  **pas encore refusé** : le modèle de table ne valide pas l'entrée, et
  PostgreSQL arrondit en silence (199 999.5 → 200 000, mesuré), ce qui
  change la tranche du barème. Voir Q-INF-06 et le test xfail
  `test_estate_price_with_cents_is_refused`.
- **L'énergie est décrite en cinq colonnes** (`energy_class`,
  `energy_class_scheme`, `energy_class_date`, `energy_kwh_m2`,
  `energy_co2_m2`) ; l'ancien score unique est retiré (Q-MIG-05). Les
  biens repris n'ont que la lettre du DPE, quand le CSV la donne
  (Q-MIG-06).
- **`id_author`** : qui a saisi le bien à la main, chasseur ou manager ;
  vide = bien importé (Q-ACC-09, Q-JEF-24).

Les colonnes à liste fermée (`estate_type`, `typology`, `floor`,
`energy_class`, `country_iso`) portent un CHECK côté base : c'est
PostgreSQL qui rejette une valeur hors liste, pas SQLModel.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from pydantic import ValidationInfo, model_validator
from sqlmodel import SQLModel, Field
from .input_check import is_input


class Estate(SQLModel, table=True):
    __tablename__ = "estate"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference: str = Field(max_length=50, unique=True)
    country_iso: Optional[str] = Field(default=None, max_length=2)
    estate_type: str = Field(max_length=50)
    price: Optional[int] = None
    construction_date: Optional[date] = None
    energy_class: Optional[str] = Field(default=None, max_length=1)
    energy_class_scheme: Optional[str] = Field(default=None, max_length=20)
    energy_class_date: Optional[date] = None
    energy_kwh_m2: Optional[int] = None
    energy_co2_m2: Optional[int] = None
    latitude: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=6)
    longitude: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=6)
    floor: Optional[str] = Field(default=None, max_length=10)
    typology: Optional[str] = Field(default=None, max_length=50)
    nb_rooms: Optional[int] = None
    nb_bedrooms: Optional[int] = None
    nb_bathrooms: Optional[int] = None
    nb_toilets: Optional[int] = None
    nb_swimming_pool: Optional[int] = None
    has_garden: Optional[bool] = None
    nb_balcony: Optional[int] = None
    nb_terrace: Optional[int] = None
    is_climatised: Optional[bool] = None
    surface: Decimal = Field(max_digits=7, decimal_places=2)
    land_surface: Optional[Decimal] = Field(default=None, max_digits=9, decimal_places=2)
    has_cellar: Optional[bool] = None
    has_view: Optional[bool] = None
    is_quiet: Optional[bool] = None
    is_bright: Optional[bool] = None
    has_garage: Optional[bool] = None
    has_elevator: Optional[bool] = None
    has_chimney: Optional[bool] = None
    parking_spaces: Optional[int] = None
    has_separate_kitchen: Optional[bool] = None
    # Deux états, FALSE par défaut (ADR-032) : TRUE = l'annonce signale des travaux.
    needs_renovation: bool = False
    town: str = Field(max_length=100)
    street: Optional[str] = Field(default=None, max_length=100)
    street_number: Optional[str] = Field(default=None, max_length=10)
    # CHECK côté base : format par pays, comme client et criteria ; un code
    # postal exige un pays (chk_estate_postal_code_format, Q-SCH-11).
    postal_code: Optional[str] = Field(default=None, max_length=10)
    # Quartier, facultatif (Q-MIG-08) ; vide sur les biens repris du CSV.
    district: Optional[str] = Field(default=None, max_length=100)
    information: Optional[str] = None
    # Clé vers "user" ; le rôle (chasseur ou manager) se vérifie dans l'API.
    id_author: Optional[int] = Field(default=None, foreign_key="user.id")

    @model_validator(mode="after")
    def _bedrooms_within_rooms(self, info: ValidationInfo) -> "Estate":
        """
        P16 (ADR-053) : une chambre est une pièce, donc chambres <= pièces.
        Contrôlé à la saisie (POST, PUT) seulement : les 251 biens repris
        qui ne le respectent pas restent tels quels et se relisent (voir
        input_check.py).
        """
        if not is_input(info):
            return self
        # Construit deux fois (voir crud_router.py, `_validated`) : seul le
        # passage converti, où les nombres sont des int, fait foi.
        rooms, bedrooms = self.nb_rooms, self.nb_bedrooms
        if isinstance(rooms, int) and isinstance(bedrooms, int) and bedrooms > rooms:
            raise ValueError(
                f"{self.nb_bedrooms} chambres pour {self.nb_rooms} pièces : une chambre est une pièce (P16)."
            )
        return self
