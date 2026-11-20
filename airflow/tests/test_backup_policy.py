"""Tests de airflow/src/backup/policy.py : où ranger une sauvegarde, et lesquelles effacer.

Choix ENV-B de Sébastien (Discord, 2026-11-20) : une sauvegarde chaque nuit,
7 jours gardés. Sans Airflow, sans Docker, sans MinIO.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.backup.policy import KEEP_DAYS, backup_keys, keys_to_delete


def test_keep_days_is_seven():
    assert KEEP_DAYS == 7


def test_backup_keys_are_grouped_by_day():
    keys = backup_keys("2026-11-20")

    assert keys.database == "2026-11-20/fil_rouge_immobilier.dump"
    assert keys.roles == "2026-11-20/roles.sql"
    assert keys.report == "2026-11-20/report.json"


@pytest.mark.parametrize("bad", ["", "20/11/2026", "2026-11-20/../x", "2026-13-01"])
def test_backup_keys_refuse_a_bad_date(bad):
    with pytest.raises(ValueError):
        backup_keys(bad)


def _day(d: str) -> list[str]:
    return [f"{d}/fil_rouge_immobilier.dump", f"{d}/roles.sql", f"{d}/report.json"]


def test_nothing_to_delete_within_seven_days():
    existing = [k for d in ["2026-11-14", "2026-11-17", "2026-11-20"] for k in _day(d)]

    assert keys_to_delete(existing, today=date(2026, 11, 20)) == []


def test_days_older_than_seven_are_deleted_whole():
    existing = _day("2026-11-12") + _day("2026-11-13") + _day("2026-11-14")

    # 20/11 - 7 jours = 13/11 : le 13 est le premier jour de trop.
    assert keys_to_delete(existing, today=date(2026, 11, 20)) == _day("2026-11-12") + _day("2026-11-13")


def test_unknown_keys_are_never_deleted():
    existing = ["notes.txt", "pas-une-date/x.dump", "2026-01-01"] + _day("2026-01-01")

    assert keys_to_delete(existing, today=date(2026, 11, 20)) == _day("2026-01-01")


def test_keep_days_can_be_changed():
    existing = _day("2026-11-20") + _day("2026-11-19")

    # keep_days=1 : seul le jour même reste (7 = le jour même et les 6 d'avant).
    assert keys_to_delete(existing, today=date(2026, 11, 20), keep_days=1) == _day("2026-11-19")


def test_keep_days_below_one_is_refused():
    with pytest.raises(ValueError):
        keys_to_delete([], today=date(2026, 11, 20), keep_days=0)
