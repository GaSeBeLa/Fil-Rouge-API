"""
Le rôle PostgreSQL fil_rouge_reader suit la cible de Reader (fiche DRO9).

- payment lui est fermée : le montant et l'IBAN ne sont lus que par le
  chasseur concerné et son manager (ADR-027, point 8).
- Un compte désactivé sort de "user", client, hunter et real_estate_manager
  pour lui : une politique par ligne ne lui montre que les comptes actifs
  (ADR-027, point 7).
- L'API, connectée en postgres (propriétaire, superutilisateur), lit toujours
  tout : la politique ne la filtre pas.

Le correctif : docker/init-v3/04_role-lecture-seule.sql, et
docker/migrations/v2-vers-v3/43_lecteur-sans-paiement-ni-compte-desactive.sql
pour une base existante. SET LOCAL ROLE donne les droits du rôle jusqu'au
rollback de la fixture ; RESET ROLE rend ceux de postgres.
"""

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session

# La table, et la colonne qui nomme son compte ("user" : son id).
PROFILE_TABLES = [
    ('"user"', "id"),
    ("client", "id_user"),
    ("hunter", "id_user"),
    ("real_estate_manager", "id_user"),
]


def set_activated(connection: Connection, user_id: int, activated: bool) -> None:
    connection.execute(
        text('UPDATE "user" SET is_activated = :activated WHERE id = :id'),
        {"activated": activated, "id": user_id},
    )


def visible_accounts(connection: Connection, table: str, column: str) -> set[int]:
    return set(connection.execute(text(f"SELECT {column} FROM {table}")).scalars().all())


def test_reader_role_cannot_read_payments(db_session: Session):
    connection = db_session.connection()
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        connection.execute(text("SELECT id FROM payment"))


@pytest.mark.parametrize(("table", "column"), PROFILE_TABLES, ids=[t.strip('"') for t, _ in PROFILE_TABLES])
def test_reader_role_sees_active_accounts_only(db_session: Session, table: str, column: str):
    connection = db_session.connection()
    account = connection.execute(text(f"SELECT {column} FROM {table} ORDER BY {column} LIMIT 1")).scalar_one()

    set_activated(connection, account, False)
    assert account in visible_accounts(connection, table, column), "l'API (postgres) doit lire un compte désactivé"
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    assert account not in visible_accounts(connection, table, column)

    connection.execute(text("RESET ROLE"))
    set_activated(connection, account, True)
    connection.execute(text("SET LOCAL ROLE fil_rouge_reader"))
    assert account in visible_accounts(connection, table, column)
