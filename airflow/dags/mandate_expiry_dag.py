"""
DAG mandate_expiry — faire expirer les mandats finis, chaque nuit (choix MAND-EXP).

Chaque nuit à 2 h 30, avant olap_refresh (3 h) pour que l'étoile voie les
statuts du jour : un mandat 'active' dont la date de fin est atteinte passe
en 'expired' (src/mandates/expiry.py, qui porte la règle et ses limites).

Le jour pris est la fin de l'intervalle du passage (data_interval_end) :
le passage de la nuit du 23 au 24 juge au 24. Rejouer un jour ne change
rien de plus.

Lancer à la main, depuis docker/ :
    docker compose exec airflow-scheduler airflow dags test mandate_expiry 2026-11-23
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from airflow import DAG  # pyright: ignore[reportMissingImports]  # Airflow vit dans le conteneur, pas sur le poste
from airflow.operators.python import PythonOperator  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.postgres.hooks.postgres import PostgresHook  # pyright: ignore[reportMissingImports]  # idem

from src.config import FIL_ROUGE_DB_CONN_ID
from src.mandates.expiry import expire_finished

logger = logging.getLogger(__name__)


def _expire(data_interval_end: datetime, **_) -> list[str]:
    """Passe en 'expired' les mandats finis au jour du passage ; rend leurs références."""
    engine = PostgresHook(postgres_conn_id=FIL_ROUGE_DB_CONN_ID).get_sqlalchemy_engine()
    today = data_interval_end.date()
    with engine.begin() as conn:
        expired = expire_finished(conn, today)
    logger.info("Mandats expirés au %s : %d %s", today, len(expired), expired)
    return expired


with DAG(
    dag_id="mandate_expiry",
    description="Mandats 'active' dont la date de fin est atteinte -> 'expired'",
    start_date=datetime(2026, 11, 1),
    schedule="30 2 * * *",
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=10),
    },
    tags=["mandat"],
) as dag:
    PythonOperator(task_id="expire", python_callable=_expire)
