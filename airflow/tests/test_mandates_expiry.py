"""Tests de airflow/src/mandates/expiry.py, sur une base SQLite en mémoire.

La table ne garde que ce que expire_finished lit et écrit.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, text

from src.mandates.expiry import expire_finished

TODAY = date(2026, 11, 23)


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE mandate (id INTEGER PRIMARY KEY, reference TEXT NOT NULL UNIQUE, "
                       "status TEXT NOT NULL, ends_at DATE)"))
        yield c


def _add(conn, reference: str, status: str, ends_at: date | None) -> None:
    conn.execute(text("INSERT INTO mandate (reference, status, ends_at) VALUES (:r, :s, :e)"),
                 {"r": reference, "s": status, "e": ends_at})


def _status(conn, reference: str) -> str:
    return conn.execute(text("SELECT status FROM mandate WHERE reference = :r"), {"r": reference}).scalar_one()


def test_an_active_mandate_past_its_end_expires(conn):
    _add(conn, "MAND-0013", "active", date(2026, 8, 10))

    assert expire_finished(conn, TODAY) == ["MAND-0013"]
    assert _status(conn, "MAND-0013") == "expired"


def test_the_end_day_itself_counts_as_finished(conn):
    # Même borne que le calcul du paiement : fini quand ends_at <= le jour.
    _add(conn, "MAND-1", "active", TODAY)

    assert expire_finished(conn, TODAY) == ["MAND-1"]


def test_a_mandate_still_running_stays_active(conn):
    _add(conn, "MAND-2", "active", date(2026, 11, 24))

    assert expire_finished(conn, TODAY) == []
    assert _status(conn, "MAND-2") == "active"


@pytest.mark.parametrize("status", ["completed", "renewed", "canceled", "lost", "expired"])
def test_other_statuses_are_left_alone(conn, status):
    _add(conn, "MAND-3", status, date(2026, 1, 1))

    assert expire_finished(conn, TODAY) == []
    assert _status(conn, "MAND-3") == status


def test_a_mandate_without_end_date_is_left_alone(conn):
    _add(conn, "MAND-4", "pending_signature", None)
    _add(conn, "MAND-5", "active", None)

    assert expire_finished(conn, TODAY) == []


def test_replaying_the_same_day_changes_nothing_more(conn):
    _add(conn, "MAND-13", "active", date(2026, 8, 10))
    _add(conn, "MAND-14", "active", date(2026, 9, 1))

    assert sorted(expire_finished(conn, TODAY)) == ["MAND-13", "MAND-14"]
    assert expire_finished(conn, TODAY) == []
