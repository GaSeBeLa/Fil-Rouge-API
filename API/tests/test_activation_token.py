"""
test_activation_token.py — Le code d'activation d'un compte (user story 01, @creation-compte).

Sans base. Le code est un JWT à part : il ne doit jamais servir de jeton de
connexion, et un jeton de connexion ne doit jamais servir de code.
"""

from datetime import timedelta

import pytest

from src.app.utils.security import (
    ACTIVATION_TOKEN_TTL,
    InvalidTokenError,
    create_access_token,
    create_activation_token,
    decode_access_token,
    decode_activation_token,
)


def test_activation_code_names_its_account() -> None:
    assert decode_activation_token(create_activation_token(42)) == 42


def test_activation_code_lasts_seven_days() -> None:
    assert ACTIVATION_TOKEN_TTL == timedelta(days=7)


def test_expired_activation_code_refused() -> None:
    code = create_activation_token(42, expires_delta=timedelta(seconds=-1))

    with pytest.raises(InvalidTokenError):
        decode_activation_token(code)


def test_access_token_is_not_an_activation_code() -> None:
    with pytest.raises(InvalidTokenError):
        decode_activation_token(create_access_token(42))


def test_activation_code_is_not_an_access_token() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(create_activation_token(42))


def test_garbage_activation_code_refused() -> None:
    with pytest.raises(InvalidTokenError):
        decode_activation_token("pas-un-jeton")
