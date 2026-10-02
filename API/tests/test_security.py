"""
test_security.py — Tests unitaires du hachage des mots de passe (ADR-016).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Aucune base, aucun réseau : on appelle directement les trois fonctions de
src/app/utils/security.py.

La plupart des tests utilisent la fixture `fast_hasher` (conftest.py), qui
remplace le hacheur réel par un hacheur faible : ce qu'on vérifie ici, c'est
le comportement des fonctions, pas la force des paramètres.

Un seul test garde le vrai hacheur (~300 ms) : celui qui prouve qu'une
empreinte produite avec les paramètres courants n'a PAS besoin d'être
re-hachée.
============================================================================
"""

from argon2 import PasswordHasher

from src.app.utils import security
from src.app.utils.security import hash_password, needs_rehash, verify_password

PLAIN = "un-mot-de-passe-assez-long"

# Ce que contient la colonne password des comptes migrés : pas une empreinte.
MIGRATED_PLACEHOLDER = "a-redefinir"


def test_hash_password_never_returns_plain_text(fast_hasher: PasswordHasher):
    stored = hash_password(PLAIN)
    assert stored != PLAIN
    assert PLAIN not in stored


def test_hash_password_produces_argon2id_phc_string(fast_hasher: PasswordHasher):
    assert hash_password(PLAIN).startswith("$argon2id$")


def test_hash_password_is_salted(fast_hasher: PasswordHasher):
    # Même mot de passe, deux empreintes différentes : le sel est aléatoire.
    assert hash_password(PLAIN) != hash_password(PLAIN)


def test_verify_password_accepts_correct_password(fast_hasher: PasswordHasher):
    assert verify_password(hash_password(PLAIN), PLAIN) is True


def test_verify_password_rejects_wrong_password(fast_hasher: PasswordHasher):
    assert verify_password(hash_password(PLAIN), "un-autre-mot-de-passe") is False


def test_verify_password_returns_false_on_invalid_hash(fast_hasher: PasswordHasher):
    # Cas des comptes migrés : refus silencieux, jamais une exception.
    assert verify_password(MIGRATED_PLACEHOLDER, PLAIN) is False


def test_needs_rehash_true_for_weaker_parameters():
    # Empreinte produite avec des paramètres faibles, jugée par le vrai hacheur.
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PLAIN)
    assert needs_rehash(weak_hash) is True


def test_needs_rehash_false_for_current_parameters():
    # Vrai hacheur, vrais paramètres : ~300 ms, assumé pour ce seul test.
    current_hash = security._hasher.hash(PLAIN)  # pyright: ignore[reportPrivateUsage] — on teste justement le hacheur réel du module
    assert needs_rehash(current_hash) is False


def test_needs_rehash_false_on_invalid_hash():
    assert needs_rehash(MIGRATED_PLACEHOLDER) is False
