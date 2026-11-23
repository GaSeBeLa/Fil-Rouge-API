"""
Passer en 'expired' les mandats finis sans vente.

Choix MAND-EXP de Sébastien (Discord, 2026-11-23). Un mandat dure 6 mois
(chk_mandate_six_months, init-v3/01) ; fini sans vente, il expire, ou il
est renouvelé (ADR-050). La migration a fait expirer ceux déjà finis le
25/07/2026 ; les suivants, « les faire expirer revient à l'application »
(docker/init-v3/02_migration.sql, bloc MANDATE ; ADR-046).

Un mandat vendu est déjà 'completed' (sale_service, P28), un mandat
renouvelé déjà 'renewed' : seul 'active' est touché.

Fini veut dire `ends_at <= jour` : même borne que le calcul du paiement
(API/src/app/services/payment_calculation_service.py, `expired`) et que
le trigger d'exclusivité, où un nouveau mandat peut commencer le jour où
l'ancien finit.

Pas encore fait : la note de performance 'mandate_expired' que l'expiration
devrait écrire (ADR-046, ADR-048) ; son calcul reste à trancher.

Testé sans Airflow, sur SQLite (tests/test_mandates_expiry.py).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection

_EXPIRE = text(
    "UPDATE mandate SET status = 'expired' "
    "WHERE status = 'active' AND ends_at IS NOT NULL AND ends_at <= :today "
    "RETURNING reference"
)


def expire_finished(conn: Connection, today: date) -> list[str]:
    """Passe en 'expired' les mandats 'active' finis au jour `today`.

    Rend les références des mandats changés, dans l'ordre de la base ; une
    liste vide si aucun. Un mandat sans date de fin (pas encore signé) n'est
    jamais touché. Rejouée le même jour, elle ne change rien de plus.
    """
    return list(conn.execute(_EXPIRE, {"today": today}).scalars())
