"""
DAG db_backup — sauvegarder la base chaque nuit, garder 7 jours (choix ENV-B).

Décidé par Sébastien (Discord, 2026-11-20) : la politique de sauvegarde du
PCA/PRA était écrite, pas codée. Chaque nuit à 1 h, avant annonces_import (2 h),
pour la date logique ds :
  1. dump   : `pg_dump -Fc` de fil_rouge_immobilier, et `pg_dumpall
              --globals-only --no-role-passwords` pour les rôles (sans aucun
              mot de passe), envoyés dans le bucket `backup` de MinIO, sous
              `{ds}/` (src/backup/policy.py) ; le rapport (tailles, sha256)
              va dans `{ds}/report.json` ;
  2. purge  : efface les jours de plus de 7 jours ; ne touche à aucune clé
              qu'il n'a pas écrite.

Limite : MinIO tourne sur la même machine que la base. C'est une copie
datée (erreur humaine, base cassée), pas une copie hors site.

Restaurer, depuis le conteneur airflow (son pg_restore 18 lit ce que son
pg_dump 18 écrit ; celui de PostgreSQL 16 ne le lit pas) :
    pg_restore -h db -U <user> -d <base vide> --no-owner fil_rouge_immobilier.dump
Une seule erreur attendue, sans effet : `SET transaction_timeout` (paramètre
de PostgreSQL 17+, inconnu du serveur 16). Éprouvé le 2026-11-20 : 3 219 biens,
539 comptes, 501 ventes et 22 tables, les mêmes que la base d'origine.

Lancer à la main, depuis docker/ :
    docker compose exec airflow-scheduler airflow dags test db_backup 2026-11-20
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from airflow import DAG  # pyright: ignore[reportMissingImports, reportAttributeAccessIssue]  # Airflow vit dans le conteneur ; sur le poste, pyright prend le dossier airflow/ du dépôt pour le paquet
from airflow.operators.python import PythonOperator  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.amazon.aws.hooks.s3 import S3Hook  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.postgres.hooks.postgres import PostgresHook  # pyright: ignore[reportMissingImports]  # idem

from src.backup.policy import KEEP_DAYS, backup_keys, keys_to_delete
from src.config import FIL_ROUGE_DB_CONN_ID, MINIO_CONN_ID

logger = logging.getLogger(__name__)
BUCKET = os.getenv("BUCKET_BACKUP", "backup")


def _run(cmd: list[str], out: Path, password: str) -> None:
    """Lance `cmd` (pg_dump ou pg_dumpall) vers `out` ; lève une erreur avec stderr s'il échoue."""
    env = {**os.environ, "PGPASSWORD": password}
    with out.open("wb") as fh:
        done = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, env=env, check=False)
    if done.returncode != 0:
        logger.error("%s a échoué (code %s) : %s", cmd[0], done.returncode, done.stderr.decode(errors="replace"))
        raise RuntimeError(f"{cmd[0]} a échoué, code {done.returncode}")


def _sha256(path: Path) -> str:
    """Rend l'empreinte sha256 du fichier, lu par blocs."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _dump(ds: str, **_) -> dict[str, object]:
    """Sauvegarde la base et les rôles dans `backup/{ds}/` ; rend le rapport écrit."""
    conn = PostgresHook(postgres_conn_id=FIL_ROUGE_DB_CONN_ID).get_connection(FIL_ROUGE_DB_CONN_ID)
    target = ["-h", conn.host, "-p", str(conn.port or 5432), "-U", conn.login]
    keys = backup_keys(ds)
    s3 = S3Hook(aws_conn_id=MINIO_CONN_ID)
    if not s3.check_for_bucket(BUCKET):
        s3.create_bucket(bucket_name=BUCKET)
        logger.info("Bucket créé : %s", BUCKET)
    report: dict[str, object] = {"ds": ds, "database": conn.schema, "files": {}}
    with tempfile.TemporaryDirectory() as tmp:
        db_file, roles_file = Path(tmp, "db.dump"), Path(tmp, "roles.sql")
        _run(["pg_dump", "-Fc", *target, "-d", conn.schema], db_file, conn.password)
        _run(["pg_dumpall", "--globals-only", "--no-role-passwords", *target, "-l", conn.schema],
             roles_file, conn.password)
        for key, path in ((keys.database, db_file), (keys.roles, roles_file)):
            s3.load_file(filename=str(path), key=key, bucket_name=BUCKET, replace=True)
            report["files"][key] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}  # type: ignore[index]
    s3.load_string(json.dumps(report, ensure_ascii=False), key=keys.report, bucket_name=BUCKET, replace=True)
    logger.info("Sauvegarde écrite : %s", report)
    return report


def _purge(ds: str, **_) -> list[str]:
    """Efface les jours de plus de KEEP_DAYS jours ; rend les clés effacées."""
    s3 = S3Hook(aws_conn_id=MINIO_CONN_ID)
    existing = s3.list_keys(bucket_name=BUCKET) or []
    doomed = keys_to_delete(existing, today=date.fromisoformat(ds), keep_days=KEEP_DAYS)
    if doomed:
        s3.delete_objects(bucket=BUCKET, keys=doomed)
    logger.info("Purge : %d clé(s) effacée(s) sur %d", len(doomed), len(existing))
    return doomed


with DAG(
    dag_id="db_backup",
    description="pg_dump de la base + rôles dans MinIO (bucket backup), 7 jours gardés",
    start_date=datetime(2026, 11, 1),
    schedule="0 1 * * *",
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["pca", "backup"],
) as dag:
    dump = PythonOperator(task_id="dump", python_callable=_dump)
    purge = PythonOperator(task_id="purge", python_callable=_purge)

    dump >> purge  # pyright: ignore[reportUnusedExpression]  # chaînage des tâches, idiome d'Airflow
