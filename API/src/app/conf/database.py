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
from urllib.parse import quote_plus

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
def _build_url() -> str:
    """
    Construit l'URL de connexion.

    `DATABASE_URL` est prioritaire quand elle est fournie. Sinon, l'URL est
    assemblée à partir des mêmes variables que `docker/.env`
    (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`), ce qui évite de
    recopier le mot de passe à deux endroits.

    Le nom d'utilisateur et le mot de passe sont **encodés** au passage :
    un mot de passe contenant `@`, `/` ou `:` casse silencieusement une URL
    assemblée à la main — l'hôte lu devient alors la fin du mot de passe,
    et l'erreur ("could not translate host name") n'y fait pas penser.
    """
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    user = quote_plus(os.getenv("POSTGRES_USER", "postgres"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "postgres"))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "fil_rouge_immobilier")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


DATABASE_URL = _build_url()

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
