"""
database.py — Connexion à PostgreSQL, partagée par toute l'API.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Ce fichier crée UNE SEULE fois un "engine" (le pool de connexions vers
PostgreSQL), réutilisé par toutes les routes de l'API. On ne se reconnecte
JAMAIS à la base à chaque requête HTTP — ce serait beaucoup trop lent.

`get_session()` fournit, pour chaque requête HTTP, une "session" (une
connexion empruntée au pool, utilisée le temps de traiter la requête, puis
rendue automatiquement au pool). FastAPI appelle cette fonction pour nous
via son système d'"injection de dépendances" (le `Depends(get_session)`
qu'on verra dans main.py).
============================================================================
"""

import os

from dotenv import load_dotenv
from sqlmodel import create_engine, Session

# Charge automatiquement les variables du fichier .env s'il existe (convention
# standard : .env n'est jamais commité, seul .env.example l'est, en exemple).
load_dotenv()

# L'URL de connexion est lue depuis une variable d'environnement plutôt que
# codée en dur : ça permet de pointer facilement vers différentes bases
# (locale, Docker, staging...) sans jamais toucher au code.
#
# Format : postgresql://<user>:<password>@<host>:<port>/<database>
#
# Valeur par défaut ci-dessous = celle de docker-compose.yml, pour que ça
# marche "out of the box" une fois le conteneur lancé.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/fil_rouge_immobilier",
)

# echo=False : ne pas afficher chaque requête SQL générée dans les logs
# (mets à True temporairement si tu veux déboguer ce que SQLModel envoie
# réellement à PostgreSQL).
engine = create_engine(DATABASE_URL, echo=False)


def get_session():
    """
    Fournit une session de base de données à une route FastAPI, et la
    ferme proprement une fois la requête terminée (même en cas d'erreur,
    grâce au `with`).
    """
    with Session(engine) as session:
        yield session
