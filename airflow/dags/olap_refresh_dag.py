"""
DAG olap_refresh — rafraîchir le schéma olap chaque nuit (FLX6).

Chaque nuit à 3 h, après annonces_import (2 h), pour la date logique ds :
  1. refresh : lit l'OLTP (src/olap/extract.py), calcule l'étoile en Python
               pur (src/olap/transform.py) et la réécrit en entier
               (src/olap/load.py), le tout dans UNE transaction : un échec
               laisse l'étoile d'hier intacte ;
  2. report  : écrit le rapport qualité (lues, chargées, rejetées par raison,
               invalid_count, pass_rate) dans gold/olap/{ds}.json.

Rejouer une date redonne la même étoile (TRUNCATE ... RESTART IDENTITY).

Lancer à la main, depuis docker/ :
    docker compose exec airflow-scheduler airflow dags test olap_refresh 2026-10-15
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from airflow import DAG  # pyright: ignore[reportMissingImports]  # Airflow vit dans le conteneur, pas sur le poste
from airflow.operators.python import PythonOperator  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.amazon.aws.hooks.s3 import S3Hook  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.postgres.hooks.postgres import PostgresHook  # pyright: ignore[reportMissingImports]  # idem

from src.config import FIL_ROUGE_DB_CONN_ID, MINIO_CONN_ID, Buckets
from src.olap.extract import extract
from src.olap.load import load_star
from src.olap.transform import build_star

logger = logging.getLogger(__name__)


def _refresh(**_) -> dict[str, object]:
    """OLTP -> étoile olap, en une transaction ; rend le rapport qualité."""
    engine = PostgresHook(postgres_conn_id=FIL_ROUGE_DB_CONN_ID).get_sqlalchemy_engine()
    with engine.begin() as conn:
        star = build_star(extract(conn))
        written = load_star(conn, star)
    report = {**star.report(), "written": written}
    logger.info("Étoile olap : %s", report)
    return report


def _report(ds: str, ti, **_) -> str:
    """Rapport du passage -> gold/olap/{ds}.json ; rend la clé écrite."""
    report = ti.xcom_pull(task_ids="refresh")
    s3, buckets = S3Hook(aws_conn_id=MINIO_CONN_ID), Buckets.from_env()
    key = f"olap/{ds}.json"
    s3.load_string(json.dumps(report, ensure_ascii=False), key=key,
                   bucket_name=buckets.gold, replace=True)
    logger.info("Rapport écrit : %s/%s", buckets.gold, key)
    return key


with DAG(
    dag_id="olap_refresh",
    description="OLTP -> étoile olap (dimensions, fait_ventes) + rapport qualité dans gold",
    start_date=datetime(2026, 10, 1),
    schedule="0 3 * * *",
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["flx", "olap"],
) as dag:
    refresh = PythonOperator(task_id="refresh", python_callable=_refresh)
    report = PythonOperator(task_id="report", python_callable=_report)

    refresh >> report  # pyright: ignore[reportUnusedExpression]  # chaînage des tâches, idiome d'Airflow
