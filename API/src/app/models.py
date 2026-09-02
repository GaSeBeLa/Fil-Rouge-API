"""
models.py — Définitions SQLModel des 11 tables du projet.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Chaque classe ci-dessous représente UNE table déjà existante dans la base
(créée par create_fil_rouge_immobilier.sql). On utilise `table=True` pour
dire à SQLModel "cette classe correspond à une vraie table", mais on
n'appelle JAMAIS `SQLModel.metadata.create_all()` dans ce projet — les
tables existent déjà, avec leurs contraintes exactes (CHECK, NOT NULL...)
définies dans le script SQL, qui reste la source de vérité.

SQLModel sert ici uniquement à LIRE et ÉCRIRE des lignes de façon
type-safe depuis Python, pas à définir le schéma.

Point important : les contraintes CHECK (ex: typology IN (...)) sont
appliquées par PostgreSQL lui-même à l'insertion, pas par SQLModel. Si tu
veux une validation côté Python AVANT d'atteindre la base (plus rapide à
l'utilisateur, message d'erreur plus clair), il faudra l'ajouter séparément
avec un validator Pydantic — pas fait ici pour rester simple au démarrage.
============================================================================
"""

from datetime import date, datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship


# ============================================================================
# 1. USER — table racine
# ============================================================================
class User(SQLModel, table=True):
    __tablename__ = "user"  # "user" est un mot réservé SQL ; SQLAlchemy le
    # met automatiquement entre guillemets doubles à la génération des
    # requêtes, comme le fait le script SQL — pas d'action supplémentaire
    # nécessaire de notre côté.

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    first_name: str = Field(max_length=80)
    last_name: str = Field(max_length=80)
    email: str = Field(max_length=150, unique=True)
    password: str = Field(max_length=80)
    phone_number: str = Field(max_length=20)
    gender: Optional[str] = Field(default=None, max_length=10)
    country_iso: Optional[str] = Field(default=None, max_length=2)


# ============================================================================
# 2. HUNTER, CLIENT, REAL_ESTATE_MANAGER — spécialisations de User
# ============================================================================
# Rappel du choix de modélisation du groupe : "id" est une clé primaire
# technique indépendante, "id_user" est le lien logique vers User (UNIQUE
# côté base). On mappe donc les deux colonnes explicitement.

class Hunter(SQLModel, table=True):
    __tablename__ = "hunter"

    id: Optional[int] = Field(default=None, primary_key=True)
    id_user: int = Field(foreign_key="user.id", unique=True)
    company_name: Optional[str] = Field(default=None, max_length=80)
    education_level: Optional[str] = Field(default=None, max_length=20)
    # Note : la colonne s'appelle "is_cartet" (tout en minuscules) en base,
    # pas "is_carteT" — PostgreSQL met automatiquement en minuscules les
    # identifiants non "quotés" à la création. On utilise donc le nom réel.
    is_cartet: Optional[bool] = None
    certification_date: Optional[date] = None
    commission_rate: Optional[float] = None


class Client(SQLModel, table=True):
    __tablename__ = "client"

    id: Optional[int] = Field(default=None, primary_key=True)
    id_user: int = Field(foreign_key="user.id", unique=True)
    address: Optional[str] = Field(default=None, max_length=150)
    address_complement: Optional[str] = Field(default=None, max_length=150)
    postal_code: Optional[str] = Field(default=None, max_length=10)
    town: Optional[str] = Field(default=None, max_length=100)
    is_married: Optional[bool] = None
    is_civil_solidarity_pact: Optional[bool] = None
    nb_children: Optional[int] = None
    birth_date: Optional[date] = None


class RealEstateManager(SQLModel, table=True):
    __tablename__ = "real_estate_manager"

    id: Optional[int] = Field(default=None, primary_key=True)
    id_user: int = Field(foreign_key="user.id", unique=True)
    company_name: Optional[str] = Field(default=None, max_length=80)


# ============================================================================
# 3. SEARCH_REQUEST
# ============================================================================
class SearchRequest(SQLModel, table=True):
    __tablename__ = "search_request"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    id_author: int = Field(foreign_key="user.id")
    id_client: int = Field(foreign_key="client.id_user")
    id_hunter: Optional[int] = Field(default=None, foreign_key="hunter.id_user")
    # Même remarque que pour is_cartet : "id_realestatemanager" tout en
    # minuscules côté base, malgré le "camelCase" du diagramme source.
    id_realestatemanager: Optional[int] = Field(
        default=None, foreign_key="real_estate_manager.id_user"
    )


# ============================================================================
# 4. CRITERIA
# ============================================================================
class Criteria(SQLModel, table=True):
    __tablename__ = "criteria"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    change_reason: Optional[str] = Field(default=None, max_length=255)
    estate_type: Optional[str] = Field(default=None, max_length=50)
    # typology : NOT NULL + CHECK côté base (liste fermée de valeurs T1-T6+).
    # SQLModel ne réplique pas ce CHECK ici — c'est PostgreSQL qui le
    # fera respecter à l'insertion. Une valeur hors liste sera rejetée par
    # la base, pas avant, avec une erreur PostgreSQL (pas une erreur
    # Pydantic "propre"). À améliorer plus tard si besoin (voir le
    # commentaire d'en-tête du fichier).
    typology: str = Field(max_length=50)
    # floor n'est plus NOT NULL côté base (retiré du schéma) : optionnel ici aussi.
    floor: Optional[str] = Field(default=None, max_length=10)
    budget_min: float
    budget_max: float
    is_new_build: Optional[bool] = None
    needs_renovation: Optional[bool] = None
    renovation_budget_min: Optional[float] = None
    renovation_budget_max: Optional[float] = None
    energy_kwh_m2_min: Optional[int] = None
    energy_kwh_m2_max: Optional[int] = None
    rooms_min: Optional[int] = None
    rooms_max: Optional[int] = None
    bedrooms_min: Optional[int] = None
    bedrooms_max: Optional[int] = None
    toilets_min: Optional[int] = None
    toilets_max: Optional[int] = None
    swimming_pool_min: Optional[int] = None
    swimming_pool_max: Optional[int] = None
    has_garden: Optional[bool] = None
    nb_balcony_min: Optional[int] = None
    nb_balcony_max: Optional[int] = None
    nb_terrace_min: Optional[int] = None
    nb_terrace_max: Optional[int] = None
    is_climatised: Optional[bool] = None
    surface_min: Optional[float] = None
    surface_max: Optional[float] = None
    land_surface_min: Optional[float] = None
    land_surface_max: Optional[float] = None
    has_separate_kitchen: Optional[bool] = None
    has_cellar: Optional[bool] = None
    has_view: Optional[bool] = None
    is_quiet: Optional[bool] = None
    is_bright: Optional[bool] = None
    has_garage: Optional[bool] = None
    has_elevator: Optional[bool] = None
    has_chimney: Optional[bool] = None
    parking_spaces: Optional[int] = None
    has_swimming_pool: Optional[bool] = None
    id_author: int = Field(foreign_key="user.id")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_previous_version: Optional[int] = Field(default=None, foreign_key="criteria.id")


# ============================================================================
# 5. MANDATE
# ============================================================================
class Mandate(SQLModel, table=True):
    __tablename__ = "mandate"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reference: str = Field(max_length=20, unique=True)
    # status : NOT NULL + CHECK côté base (voir remarque sur typology
    # ci-dessus, même logique).
    status: str = Field(max_length=20)
    signature_date: Optional[date] = None
    signature_type: Optional[str] = Field(default=None, max_length=20)
    ends_at: date
    is_client_signed: bool = False
    is_exclusive: bool
    id_hunter: int = Field(foreign_key="hunter.id_user")
    id_client: int = Field(foreign_key="client.id_user")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_mandate_parent: Optional[int] = Field(default=None, foreign_key="mandate.id")


# ============================================================================
# 6. ESTATE
# ============================================================================
class Estate(SQLModel, table=True):
    __tablename__ = "estate"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reference: str = Field(max_length=50, unique=True)
    estate_type: str = Field(max_length=50)  # NOT NULL + CHECK côté base
    price: Optional[float] = None
    construction_date: Optional[date] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # floor n'est plus NOT NULL côté base (retiré du schéma) : optionnel ici aussi.
    floor: Optional[str] = Field(default=None, max_length=10)  # CHECK côté base
    nb_rooms: Optional[int] = None
    nb_bedrooms: Optional[int] = None
    nb_bathrooms: Optional[int] = None
    nb_toilets: Optional[int] = None
    nb_swimming_pool: Optional[int] = None
    has_garden: Optional[bool] = None
    nb_balcony: Optional[int] = None
    nb_terrace: Optional[int] = None
    is_climatised: Optional[bool] = None
    energetic_score: Optional[int] = None
    surface: float
    land_surface: Optional[float] = None
    has_cellar: Optional[bool] = None
    has_view: Optional[bool] = None
    is_quiet: Optional[bool] = None
    is_bright: Optional[bool] = None
    has_garage: Optional[bool] = None
    has_elevator: Optional[bool] = None
    has_chimney: Optional[bool] = None
    parking_spaces: Optional[int] = None
    has_separate_kitchen: Optional[bool] = None
    needs_renovation: Optional[bool] = None
    town: str = Field(max_length=100)
    street: Optional[str] = Field(default=None, max_length=100)
    street_number: Optional[str] = Field(default=None, max_length=10)
    postal_code: Optional[str] = Field(default=None, max_length=10)
    information: Optional[str] = None


# ============================================================================
# 7. ESTATE_PROPOSED
# ============================================================================
class EstateProposed(SQLModel, table=True):
    __tablename__ = "estate_proposed"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    comment_hunter: Optional[str] = None
    comment_client: Optional[str] = None
    amount_proposition: Optional[float] = None
    is_accepted: Optional[bool] = None
    id_hunter: int = Field(foreign_key="hunter.id_user")
    id_estate: int = Field(foreign_key="estate.id")
    id_mandate: int = Field(foreign_key="mandate.id")


# ============================================================================
# 8. ESTATE_SEARCHREQUEST
# ============================================================================
class EstateSearchRequest(SQLModel, table=True):
    __tablename__ = "estate_searchrequest"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    review_hunter: Optional[str] = None
    media_url: Optional[str] = None
    media_type: str = Field(max_length=10)  # NOT NULL + CHECK ('audio'/'video')
    id_estate: int = Field(foreign_key="estate.id")
    id_search_request: int = Field(foreign_key="search_request.id")
    id_hunter: int = Field(foreign_key="hunter.id_user")


# ============================================================================
# 9. PICTURE
# ============================================================================
class Picture(SQLModel, table=True):
    __tablename__ = "picture"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    url: Optional[str] = None
    id_estate: int = Field(foreign_key="estate.id")
