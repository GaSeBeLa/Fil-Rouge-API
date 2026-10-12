"""
input_check.py — Les règles d'entrée ne jugent que les entrées (fiche API4).

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
P16, P29 et P32 sont des validateurs Pydantic posés sur les modèles de
table. Or Pydantic les relance à CHAQUE validation, y compris quand FastAPI
vérifie la réponse d'un GET : un bien repris qui ne respecte pas P16 (251
en base, ADR-053) rendait alors 500 à la lecture.

Donc : `_validated` (routes/crud_router.py), le seul passage qui fait foi
pour une entrée, valide avec `context=INPUT_CONTEXT` ; chaque règle commence
par `if not is_input(info): return ...`. La lecture ne rejuge rien.
============================================================================
"""

from pydantic import ValidationInfo

INPUT_CONTEXT = {"input": True}


def is_input(info: ValidationInfo) -> bool:
    """Vrai pour la revalidation d'une entrée (POST, PUT), faux à la lecture."""
    return isinstance(info.context, dict) and info.context.get("input") is True
