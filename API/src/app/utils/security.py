"""
security.py — Mots de passe (ADR-016) et jetons de connexion JWT (ADR-052).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Un mot de passe en clair ne doit exister QUE dans la variable locale d'une
requête, jamais en base, jamais en log, jamais en cache.

Paramètres mesurés sur cette machine (22/09/2026, conteneur api,
python:3.12-slim) : t=3, m=512 Mo -> ~298 ms. Cible ADR-016 : 250-500 ms.
Ne pas recopier ces valeurs sur une autre machine sans remesurer.

Les paramètres sont inscrits DANS l'empreinte produite (format PHC). Les
durcir plus tard n'invalide donc aucune empreinte existante : c'est ce que
gère needs_rehash().

Le jeton de connexion (ADR-052) : un JWT signé HS256 par `pyjwt`, valable
60 minutes, sans jeton de rafraîchissement. Il ne porte que l'identifiant
de l'utilisateur (`sub`) : le rôle et l'activation se relisent en base à
chaque appel (utils/current_user.py, get_current_user).

Le secret de signature se lit dans la variable JWT_SECRET. Absente ou trop
courte, l'import de ce module échoue : l'API refuse de démarrer, plutôt que
de signer des jetons avec une clé vide.
============================================================================
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=524288,  # 512 Mo — mesuré sur cette machine, ~298 ms
    parallelism=4,
)


def hash_password(plain: str) -> str:
    """Renvoie l'empreinte PHC d'un mot de passe en clair."""
    return _hasher.hash(plain)


def verify_password(stored: str, plain: str) -> bool:
    """
    Compare un mot de passe en clair à une empreinte stockée.

    Utilise la vérification à temps constant d'argon2-cffi : jamais un `==`,
    dont la durée dépend du nombre de caractères corrects (timing attack).

    InvalidHashError couvre les 24 comptes migrés, dont le placeholder n'est
    pas une empreinte valide : ils ne peuvent tout simplement pas se
    connecter, ce qui est le comportement voulu.
    """
    try:
        return _hasher.verify(stored, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    """
    Vrai si l'empreinte a été produite avec des paramètres plus faibles que
    les paramètres courants. À appeler après une connexion RÉUSSIE : c'est le
    seul moment où l'on dispose du mot de passe en clair pour re-hacher.
    """
    try:
        return _hasher.check_needs_rehash(stored)
    except InvalidHashError:
        return False


# --- Jetons de connexion (ADR-052) -----------------------------------------

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=60)  # ADR-052, décision 2

# RFC 7518 §3.2 : une clé HS256 doit faire au moins 256 bits (32 octets).
_JWT_SECRET_MIN_LENGTH = 32


class InvalidTokenError(Exception):
    """Jeton refusé : faux, expiré, ou sans identifiant lisible."""


def _load_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET absente : l'API ne peut pas signer de jeton de connexion "
            "(ADR-052). Ajoute-la dans docker/.env (modèle : docker/.env.exemple)."
        )
    if len(secret) < _JWT_SECRET_MIN_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET trop courte ({len(secret)} caractères, "
            f"{_JWT_SECRET_MIN_LENGTH} au moins) : génère-la avec `openssl rand -hex 32`."
        )
    return secret


_JWT_SECRET = _load_jwt_secret()


def create_access_token(user_id: int, expires_delta: timedelta = ACCESS_TOKEN_TTL) -> str:
    """Signe un jeton qui désigne l'utilisateur `user_id`, valable `expires_delta`."""
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, _JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """
    Vérifie la signature et l'expiration, et rend l'identifiant de
    l'utilisateur. Toute anomalie lève InvalidTokenError : l'appelant n'a pas
    à distinguer un jeton expiré d'un jeton forgé (les deux valent 401).
    """
    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
