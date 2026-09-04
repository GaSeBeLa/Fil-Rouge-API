"""
models — Définitions SQLModel des 11 tables du projet, une classe par
fichier dans ce dossier.

============================================================================
COMMENT LIRE CE PACKAGE
============================================================================
Chaque fichier `*_model.py` représente UNE table déjà existante dans la
base (créée par create_fil_rouge_immobilier.sql). On utilise `table=True`
pour dire à SQLModel "cette classe correspond à une vraie table", mais on
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

Les `foreign_key="table.colonne"` sont de simples chaînes : SQLAlchemy les
résout par nom de table, pas par import Python. Aucune dépendance d'ordre
d'import entre les fichiers de ce dossier.
============================================================================
"""

from .user_model import User
from .role_model import Role
from .hunter_model import Hunter
from .client_model import Client
from .real_estate_manager_model import RealEstateManager
from .search_request_model import SearchRequest
from .criteria_model import Criteria
from .mandate_model import Mandate
from .estate_model import Estate
from .estate_proposed_model import EstateProposed
from .estate_search_request_model import EstateSearchRequest
from .picture_model import Picture

__all__ = [
    "User",
    "Role",
    "Hunter",
    "Client",
    "RealEstateManager",
    "SearchRequest",
    "Criteria",
    "Mandate",
    "Estate",
    "EstateProposed",
    "EstateSearchRequest",
    "Picture",
]
