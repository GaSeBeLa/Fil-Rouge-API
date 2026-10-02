"""
test_user_models.py — Tests unitaires des modèles d'entrée/sortie de User.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
UserCreate, UserUpdate et UserPublic ne sont pas des tables : Pydantic les
valide à la construction. On vérifie trois promesses de user_model.py :

- un mot de passe de moins de 12 caractères est refusé (min_length=12 :
  proposition du tuto, pas encore actée par le groupe — si la valeur change,
  seul ce test change) ;
- une mise à jour peut ne rien fournir ;
- un mot de passe, même haché, ne sort jamais de l'API.
============================================================================
"""

import pytest
from pydantic import ValidationError

from src.app.models import UserCreate, UserPublic, UserUpdate


def test_user_create_rejects_short_password():
    with pytest.raises(ValidationError):
        UserCreate.model_validate({"email": "a@exemple.fr", "password": "x" * 11, "id_role": 1})


def test_user_create_accepts_twelve_characters():
    user = UserCreate.model_validate({"email": "a@exemple.fr", "password": "x" * 12, "id_role": 1})
    assert user.password == "x" * 12


def test_user_create_requires_password():
    with pytest.raises(ValidationError):
        UserCreate.model_validate({"email": "a@exemple.fr", "id_role": 1})


def test_user_update_accepts_empty_body():
    assert UserUpdate.model_validate({}).model_dump(exclude_unset=True) == {}


def test_user_update_rejects_short_password():
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"password": "court"})


def test_user_public_has_no_password_field():
    assert "password" not in UserPublic.model_fields
