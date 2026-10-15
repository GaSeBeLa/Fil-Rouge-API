"""
test_base_repository.py — Tests unitaires de BaseRepository, sans base.

============================================================================
COMMENT LIRE CE FICHIER
============================================================================
La Session SQLModel est remplacée par un MagicMock. On ne teste donc PAS
SQL ni PostgreSQL (ce sera le rôle des tests d'intégration, avec une base
de test isolée) : on teste la logique propre au repository.

- `create` ignore l'id fourni (PostgreSQL le génère : GENERATED ALWAYS).
- `replace` recopie les champs mais jamais l'id.
- une IntegrityError au commit devient rollback + ConflictError, dont le
  message dit la sorte de refus et nomme la contrainte (fiche FIN1) ;
- `conflict_detail` ne recopie jamais la valeur refusée.

`User` sert de modèle concret : instancier une classe SQLModel `table=True`
ne touche pas la base.
============================================================================
"""

from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.app.models import User
from src.app.repositories.base_repository import BaseRepository
from src.app.repositories.estate_contact_repository import EstateContactRepository
from src.app.utils.constraint_messages import conflict_detail
from src.app.utils.exceptions import ConflictError


def integrity_error(pgcode: Optional[str], constraint_name: Optional[str]) -> IntegrityError:
    """Une IntegrityError comme psycopg2 la remonte : `pgcode` et `diag.constraint_name`."""
    orig = SimpleNamespace(
        pgcode=pgcode,
        diag=SimpleNamespace(constraint_name=constraint_name, message_detail="Key (email)=(secret@exemple.fr)"),
    )
    return IntegrityError("INSERT ...", {}, orig)  # pyright: ignore[reportArgumentType] — faux psycopg2.Error, mêmes attributs


@pytest.fixture
def repository() -> BaseRepository[User]:
    return BaseRepository(User)


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def failing_session() -> MagicMock:
    s = MagicMock()
    s.commit.side_effect = integrity_error("23503", "client_id_user_fkey")
    return s


def make_user(**overrides: object) -> User:
    fields: dict[str, object] = {"email": "a@exemple.fr", "password": "empreinte"}
    fields.update(overrides)
    return User(**fields)  # pyright: ignore[reportArgumentType] — champs fournis dynamiquement, validés par SQLModel


def test_create_resets_client_supplied_id(repository: BaseRepository[User], session: MagicMock):
    user = make_user(id=42)
    repository.create(session, user)
    assert user.id is None
    session.add.assert_called_once_with(user)
    session.commit.assert_called_once()


def test_replace_copies_fields_but_keeps_id(repository: BaseRepository[User], session: MagicMock):
    existing = make_user(id=1)
    data = make_user(id=99, email="nouveau@exemple.fr", system_role="Reader")

    result = repository.replace(session, existing, data)

    assert result.id == 1
    assert result.email == "nouveau@exemple.fr"
    assert result.system_role == "Reader"


def test_create_conflict_rolls_back_and_raises(repository: BaseRepository[User], failing_session: MagicMock):
    with pytest.raises(ConflictError) as exc:
        repository.create(failing_session, make_user())
    assert str(exc.value) == "Référence inexistante : la ligne citée n'existe pas (contrainte client_id_user_fkey)."
    failing_session.rollback.assert_called_once()
    failing_session.refresh.assert_not_called()


def test_save_conflict_uses_write_detail(repository: BaseRepository[User], failing_session: MagicMock):
    with pytest.raises(ConflictError) as exc:
        repository.save(failing_session, make_user(id=1))
    assert "client_id_user_fkey" in str(exc.value)
    assert not str(exc.value).startswith("Suppression")


def test_delete_conflict_uses_delete_detail(repository: BaseRepository[User], failing_session: MagicMock):
    with pytest.raises(ConflictError) as exc:
        repository.delete(failing_session, make_user(id=1))
    assert str(exc.value) == "Suppression impossible : la ligne est encore référencée par client_id_user_fkey."
    failing_session.rollback.assert_called_once()


def test_insert_pending_conflict_names_the_constraint(repository: BaseRepository[User]):
    s = MagicMock()
    s.flush.side_effect = integrity_error("23505", "user_email_key")
    with pytest.raises(ConflictError) as exc:
        repository.insert_pending(s, make_user())
    assert str(exc.value) == "Cet email a déjà un compte (contrainte user_email_key)."
    s.rollback.assert_called_once()


@pytest.mark.parametrize(
    ("pgcode", "name", "deleting", "expected"),
    [
        ("23505", "mandate_reference_key", False, "Cette référence de mandat existe déjà (contrainte mandate_reference_key)."),
        ("23505", "uq_criteria_one_successor", False, "Valeur déjà utilisée : la base refuse un doublon (contrainte uq_criteria_one_successor)."),
        ("23514", "chk_budget", False, "Valeur refusée par une règle de la base (contrainte chk_budget)."),
        ("23P01", "excl_scale_no_overlap", False, "Chevauchement refusé par la base (contrainte excl_scale_no_overlap)."),
        ("23503", None, False, "Référence inexistante : la ligne citée n'existe pas."),
        ("23503", None, True, "Suppression impossible : la ligne est encore référencée ailleurs."),
        (None, None, False, "Écriture refusée par la base."),
    ],
)
def test_conflict_detail_sort_then_name(pgcode: Optional[str], name: Optional[str], deleting: bool, expected: str):
    assert conflict_detail(integrity_error(pgcode, name), deleting) == expected


def test_conflict_detail_without_psycopg2_attributes():
    # Une erreur sans pgcode ni diag : la phrase par défaut, jamais un message vide.
    assert conflict_detail(IntegrityError("INSERT ...", {}, Exception("violation")), deleting=False) == "Écriture refusée par la base."


def test_estate_contact_commit_is_a_write_not_a_delete():
    # Un refus pendant l'anonymisation des contacts est une écriture refusée,
    # pas une suppression bloquée.
    s = MagicMock()
    s.commit.side_effect = integrity_error("23503", "estate_contact_id_estate_fkey")
    with pytest.raises(ConflictError) as exc:
        EstateContactRepository().commit(s)
    assert str(exc.value) == (
        "Référence inexistante : la ligne citée n'existe pas (contrainte estate_contact_id_estate_fkey)."
    )
    s.rollback.assert_called_once()


def test_conflict_detail_never_copies_the_refused_value():
    detail = conflict_detail(integrity_error("23505", "user_email_key"), deleting=False)
    assert "secret@exemple.fr" not in detail
