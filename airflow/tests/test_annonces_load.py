"""Tests de airflow/src/annonces/load.py, sur une base SQLite en mémoire.

SQLite comprend le même INSERT ... ON CONFLICT ... DO UPDATE que PostgreSQL :
pas besoin de Docker. Les deux tables ne gardent que ce que load.py touche.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, text

from src.annonces.clean import ESTATE_COLUMNS, KEY, clean_annonce
from src.annonces.load import load_estates

DAY1, DAY2 = date(2026, 10, 15), date(2026, 10, 16)


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    columns = ", ".join(c for c in ESTATE_COLUMNS if c != KEY)
    with engine.begin() as c:
        c.execute(text(f"CREATE TABLE estate (id INTEGER PRIMARY KEY, {KEY} TEXT NOT NULL UNIQUE, "
                       f"{columns}, id_author INTEGER)"))
        c.execute(text("CREATE TABLE estate_price_history (id INTEGER PRIMARY KEY, id_estate INTEGER NOT NULL, "
                       "price INTEGER NOT NULL, seen_at DATE NOT NULL, UNIQUE (id_estate, seen_at))"))
        yield c


def _row(reference: str, price: str = "250000") -> dict[str, object]:
    return clean_annonce({"reference": reference, "type_bien": "Maison", "ville": "Toulouse",
                          "code_postal": "31000", "surface": "100", "prix": price})


def _count(conn, table: str) -> int:
    return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_first_load_inserts_every_row(conn):
    report = load_estates(conn, [_row("AN-1"), _row("AN-2")], DAY1)

    assert (report.inserted, report.updated, report.prices_added) == (2, 0, 2)
    assert _count(conn, "estate") == 2


def test_replaying_the_same_day_adds_nothing(conn):
    rows = [_row("AN-1"), _row("AN-2")]
    load_estates(conn, rows, DAY1)

    report = load_estates(conn, rows, DAY1)

    assert (report.inserted, report.updated, report.prices_added) == (0, 2, 0)
    assert _count(conn, "estate") == 2
    assert _count(conn, "estate_price_history") == 2


def test_new_price_updates_estate_and_keeps_the_old_one(conn):
    load_estates(conn, [_row("AN-1", "100000")], DAY1)

    load_estates(conn, [_row("AN-1", "120000")], DAY2)

    assert conn.execute(text("SELECT price FROM estate")).scalar_one() == 120000
    history = conn.execute(text("SELECT price, seen_at FROM estate_price_history ORDER BY seen_at")).all()
    assert [h[0] for h in history] == [100000, 120000]


def test_manual_estate_is_never_overwritten(conn):
    conn.execute(text(f"INSERT INTO estate ({KEY}, price, id_author) VALUES ('AN-1', 90000, 7)"))

    report = load_estates(conn, [_row("AN-1", "120000")], DAY1)

    assert report.skipped_manual == 1
    assert conn.execute(text("SELECT price, id_author FROM estate")).one() == (90000, 7)
    assert _count(conn, "estate_price_history") == 0


def test_imported_estate_has_no_author(conn):
    load_estates(conn, [_row("AN-1")], DAY1)

    assert conn.execute(text("SELECT id_author FROM estate")).scalar_one() is None


def test_row_without_price_has_no_history(conn):
    report = load_estates(conn, [_row("AN-1", "")], DAY1)

    assert (report.inserted, report.prices_added) == (1, 0)


def test_construction_date_read_back_from_json_is_a_date(conn):
    row = _row("AN-1")
    row["construction_date"] = "1888-01-01"

    load_estates(conn, [row], DAY1)

    assert conn.execute(text("SELECT construction_date FROM estate")).scalar_one() == "1888-01-01"
