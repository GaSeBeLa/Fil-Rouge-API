"""
exceptions.py — Erreurs "métier", indépendantes de FastAPI.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
Repositories et services ne doivent rien savoir de HTTP (ils doivent rester
utilisables depuis un script, un test, une future interface CLI...). Ils
lèvent donc ces deux exceptions "neutres" plutôt que HTTPException.

C'est la couche routers/ (la seule qui connaît FastAPI) qui les attrape et
les traduit en codes HTTP (404, 409) — voir routers/crud_router.py.
============================================================================
"""


class NotFoundError(Exception):
    """La ligne demandée n'existe pas."""


class ConflictError(Exception):
    """Une contrainte de la base a été violée (doublon, FK inexistante,
    suppression d'une ligne encore référencée...)."""
