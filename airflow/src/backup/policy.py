"""
Politique de la sauvegarde quotidienne : où ranger chaque fichier, lesquels effacer.

Choix ENV-B de Sébastien (Discord, 2026-11-20) : une copie de la base chaque
nuit, 7 jours gardés. Python pur, testé sans Airflow (tests/test_backup_policy.py).

Rangement dans le bucket : un dossier par jour, `AAAA-MM-JJ/`, qui porte
la base (`fil_rouge_immobilier.dump`), les rôles (`roles.sql`) et le rapport
(`report.json`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

KEEP_DAYS = 7
_DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})/[^/]+$")


@dataclass(frozen=True)
class BackupKeys:
    """Les trois clés d'objet d'une sauvegarde d'un jour."""

    database: str
    roles: str
    report: str


def _parse_day(ds: str) -> date:
    """Rend la date de `ds` (AAAA-MM-JJ) ; lève ValueError si ce n'est pas une vraie date."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
        raise ValueError(f"date attendue au format AAAA-MM-JJ : {ds!r}")
    return date.fromisoformat(ds)


def backup_keys(ds: str) -> BackupKeys:
    """Rend les clés de la sauvegarde du jour `ds` ; lève ValueError sur une date invalide."""
    day = _parse_day(ds).isoformat()
    return BackupKeys(
        database=f"{day}/fil_rouge_immobilier.dump",
        roles=f"{day}/roles.sql",
        report=f"{day}/report.json",
    )


def keys_to_delete(existing: list[str], today: date, keep_days: int = KEEP_DAYS) -> list[str]:
    """
    Rend, dans l'ordre reçu, les clés des jours plus vieux que `keep_days` jours.

    Seul un dossier de jour (`AAAA-MM-JJ/<fichier>`) peut être effacé : toute
    autre clé est gardée, pour ne jamais toucher à ce que la sauvegarde n'a
    pas écrit. Lève ValueError si `keep_days` < 1 (tout effacer).
    """
    if keep_days < 1:
        raise ValueError("keep_days doit valoir au moins 1")
    limit = today - timedelta(days=keep_days)
    doomed = []
    for key in existing:
        match = _DAY.match(key)
        if not match:
            continue
        try:
            day = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if day <= limit:
            doomed.append(key)
    return doomed
