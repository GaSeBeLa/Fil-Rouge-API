"""
DAG annonces_import — importer les annonces chaque nuit, sans doublon (FLX4).

Chaque nuit à 2 h (question flux-15), pour la date logique ds :
  1. generate         : lance le générateur du sujet (airflow/tools/, copie à
                        l'identique) dans un dossier temporaire, et range son
                        CSV brut dans bronze/annonces/{ds}/. Si ce brut existe
                        déjà, il est gardé tel quel : le générateur tire au
                        hasard, et un rejeu doit relire les mêmes annonces ;
  2. clean_validate   : nettoie et valide (src/annonces, FLX3) ; valides dans
                        silver/annonces/{ds}.json, rejets dans
                        quarantine/annonces/{ds}.json ;
  3. load             : charge silver dans estate (clé : reference, flux-16) et
                        note le prix du jour dans estate_price_history.

Rejouer une date ne crée ni bien ni prix en double.

Lancer à la main, depuis docker/ :
    docker compose exec airflow-scheduler airflow dags test annonces_import 2026-10-15
"""
from __future__ import annotations

import csv
import io
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from airflow import DAG  # pyright: ignore[reportMissingImports]  # Airflow vit dans le conteneur, pas sur le poste
from airflow.operators.python import PythonOperator  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.amazon.aws.hooks.s3 import S3Hook  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.postgres.hooks.postgres import PostgresHook  # pyright: ignore[reportMissingImports]  # idem

from src.annonces.clean import clean_annonce
from src.annonces.load import load_estates
from src.annonces.validate import split_valid
from src.config import FIL_ROUGE_DB_CONN_ID, MINIO_CONN_ID, Buckets

logger = logging.getLogger(__name__)

# /opt/airflow/tools, monté par docker-compose.yml (question flux-17).
GENERATOR = Path(__file__).resolve().parent.parent / "tools" / "generer_annonces.py"


def _bronze_key(ds: str) -> str:
    return f"annonces/{ds}/annonces.csv"


def _generate(ds: str, params: dict, **_) -> str:
    """Remplit bronze/annonces/{ds}/ une seule fois ; rend la clé du CSV brut."""
    s3, buckets = S3Hook(aws_conn_id=MINIO_CONN_ID), Buckets.from_env()
    key = _bronze_key(ds)
    if s3.check_for_key(key, bucket_name=buckets.bronze):
        logger.info("Brut déjà présent, gardé tel quel : %s/%s", buckets.bronze, key)
        return key

    with tempfile.TemporaryDirectory() as tmp:
        # Le script écrit dans <son dossier parent>/fixtures/annonces/ : on le
        # recopie dans <tmp>/outils/, jamais lancé depuis le StarterPack.
        script = Path(tmp) / "outils" / GENERATOR.name
        script.parent.mkdir()
        shutil.copy(GENERATOR, script)
        args = [sys.executable, str(script),
                "--nombre-recherches", str(params["nombre_recherches"]),
                "--min-annonces", str(params["min_annonces"]),
                "--max-annonces", str(params["max_annonces"])]
        done = subprocess.run(args, capture_output=True, text=True, check=False)
        logger.info("Générateur : %s", done.stdout.strip())
        if done.returncode != 0:
            raise RuntimeError(f"générateur en échec ({done.returncode}) : {done.stderr.strip()}")
        produced = Path(tmp) / "fixtures" / "annonces" / "annonces.csv"
        s3.load_file(str(produced), key=key, bucket_name=buckets.bronze, replace=False)
    logger.info("Brut écrit : %s/%s", buckets.bronze, key)
    return key


def _clean_validate(ds: str, **_) -> dict[str, int]:
    """bronze -> silver (valides) et quarantine (rejets) ; rend les comptes."""
    s3, buckets = S3Hook(aws_conn_id=MINIO_CONN_ID), Buckets.from_env()
    key = _bronze_key(ds)
    raw = s3.read_key(key, bucket_name=buckets.bronze)
    rows = [clean_annonce(r) for r in csv.DictReader(io.StringIO(raw.lstrip("﻿")))]
    valid, rejects = split_valid(rows, source_file=f"{buckets.bronze}/{key}")

    for bucket, data in ((buckets.silver, valid), (buckets.quarantine, rejects)):
        body = json.dumps(data, ensure_ascii=False, default=str)
        s3.load_string(body, key=f"annonces/{ds}.json", bucket_name=bucket, replace=True)
    counts = {"read": len(rows), "valid": len(valid), "rejected": len(rejects)}
    logger.info("Annonces : %s", counts)
    return counts


def _load(ds: str, **_) -> dict[str, int]:
    """silver -> estate et estate_price_history ; rend le rapport."""
    s3, buckets = S3Hook(aws_conn_id=MINIO_CONN_ID), Buckets.from_env()
    rows = json.loads(s3.read_key(f"annonces/{ds}.json", bucket_name=buckets.silver))
    engine = PostgresHook(postgres_conn_id=FIL_ROUGE_DB_CONN_ID).get_sqlalchemy_engine()
    with engine.begin() as conn:
        report = load_estates(conn, rows, seen_at=date.fromisoformat(ds))
    logger.info("Chargement : %s", report)
    return report.__dict__


with DAG(
    dag_id="annonces_import",
    description="Annonces du générateur -> bronze -> silver/quarantine -> estate",
    start_date=datetime(2026, 10, 1),
    schedule="0 2 * * *",
    catchup=False,
    # Une recherche par nuit, avec les bornes d'annonces par défaut du script
    # (100 à 1000) ; modifiables au lancement (« Trigger DAG w/ config »).
    params={"nombre_recherches": 1, "min_annonces": 100, "max_annonces": 1000},  # pyright: ignore[reportArgumentType]  # un dict est accepté par Airflow 2.11 ; le poste a les types d'Airflow 3
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["flx", "annonces"],
) as dag:
    generate = PythonOperator(task_id="generate", python_callable=_generate)
    clean_validate = PythonOperator(task_id="clean_validate", python_callable=_clean_validate)
    load = PythonOperator(task_id="load", python_callable=_load)

    generate >> clean_validate >> load  # pyright: ignore[reportUnusedExpression]  # chaînage des tâches, idiome d'Airflow
