"""
security.py — Hachage et vérification des mots de passe (ADR-016).

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
============================================================================
"""

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