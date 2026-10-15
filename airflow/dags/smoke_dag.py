"""
DAG smoke_dag — vérifie que la plomberie tient (chantier FLX, fiche FLX2).

Deux tâches, lancées à la main seulement (schedule=None) :
  1. write_bronze : écrit un petit objet JSON dans bronze/smoke/{ds}.json,
     par la connexion Airflow minio_default ;
  2. count_estates : lit SELECT count(*) FROM estate dans fil_rouge_immobilier,
     par la connexion Airflow fil_rouge_db, et écrit le nombre dans les logs.

Rejouer le DAG pour la même date réécrit le même objet : aucun doublon.

Lancer à la main, depuis docker/ :
    docker compose exec airflow-scheduler airflow dags test smoke_dag 2026-10-15
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

logger = logging.getLogger(__name__)


def _write_bronze(ds: str, **_) -> str:
    """Écrit bronze/smoke/{ds}.json ; rend la clé écrite."""
    bucket = Buckets.from_env().bronze
    key = f"smoke/{ds}.json"
    body = json.dumps({"dag": "smoke_dag", "ds": ds})
    S3Hook(aws_conn_id=MINIO_CONN_ID).load_string(body, key=key, bucket_name=bucket, replace=True)
    logger.info("Objet écrit : %s/%s", bucket, key)
    return f"{bucket}/{key}"


def _count_estates(**_) -> int:
    """Compte les biens de la table estate ; rend le nombre."""
    row = PostgresHook(postgres_conn_id=FIL_ROUGE_DB_CONN_ID).get_first("SELECT count(*) FROM estate")
    count = int(row[0])
    logger.info("Nombre de biens dans estate : %d", count)
    return count


with DAG(
    dag_id="smoke_dag",
    description="Essai : un objet dans bronze, un comptage dans estate",
    start_date=datetime(2026, 10, 1),
    schedule=None,
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=5),
    },
    tags=["flx", "smoke"],
) as dag:
    write_bronze = PythonOperator(task_id="write_bronze", python_callable=_write_bronze)
    count_estates = PythonOperator(task_id="count_estates", python_callable=_count_estates)

    write_bronze >> count_estates
