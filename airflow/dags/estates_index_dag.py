"""
DAG estates_index — remplir l'index Elasticsearch `estates` chaque nuit (FLX8).

Chaque nuit à 4 h, après olap_refresh (3 h) :
  1. index : crée l'index s'il manque (src/search/mapping.py), puis verse
             chaque bien de estate par helpers.bulk, _id = estate.id : rejouer
             remplace les documents, sans doublon ;
  2. prune : retire de l'index les _id absents de estate (bien supprimé).

Connexion elasticsearch_default (docker-compose.yml) : compte dédié
airflow_indexer, droits limités à l'index estates (rôle estates_writer, créé
par es-setup), jamais le compte elastic.

Lancer à la main, depuis docker/ (profils airflow et elk) :
    docker compose exec airflow-scheduler airflow dags test estates_index 2026-10-15
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from airflow import DAG  # pyright: ignore[reportMissingImports]  # Airflow vit dans le conteneur, pas sur le poste
from airflow.hooks.base import BaseHook  # pyright: ignore[reportMissingImports, reportAttributeAccessIssue]  # idem ; Airflow 3 l'a déplacé, pas la 2.11.2
from airflow.operators.python import PythonOperator  # pyright: ignore[reportMissingImports]  # idem
from airflow.providers.postgres.hooks.postgres import PostgresHook  # pyright: ignore[reportMissingImports]  # idem
from elasticsearch import Elasticsearch, helpers  # pyright: ignore[reportMissingImports]  # client installé dans l'image (airflow/Dockerfile)

from src.config import FIL_ROUGE_DB_CONN_ID
from src.search.documents import ESTATE_IDS_QUERY, ESTATE_QUERY, delete_actions, index_actions
from src.search.mapping import INDEX, MAPPINGS, SETTINGS

logger = logging.getLogger(__name__)

ES_CONN_ID = "elasticsearch_default"


def _client() -> Elasticsearch:
    conn = BaseHook.get_connection(ES_CONN_ID)
    return Elasticsearch(conn.host, basic_auth=(conn.login, conn.password), request_timeout=30)


def _bulk(es: Elasticsearch, actions) -> int:
    """helpers.bulk, et un échec si un seul document est refusé."""
    ok, errors = helpers.bulk(es, actions, chunk_size=1000, raise_on_error=False)
    if isinstance(errors, list) and errors:
        logger.error("Documents refusés : %s (premier : %s)", len(errors), errors[0])
        raise RuntimeError(f"{len(errors)} document(s) refusé(s) par Elasticsearch")
    return ok


def _index(**_) -> dict[str, int]:
    """estate -> index estates ; rend les comptes."""
    es = _client()
    if not es.indices.exists(index=INDEX):
        es.indices.create(index=INDEX, settings=SETTINGS, mappings=MAPPINGS)
        logger.info("Index créé : %s", INDEX)
    engine = PostgresHook(postgres_conn_id=FIL_ROUGE_DB_CONN_ID).get_sqlalchemy_engine()
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(ESTATE_QUERY)]
    indexed = _bulk(es, index_actions(rows))
    es.indices.refresh(index=INDEX)
    report = {"read": len(rows), "indexed": indexed}
    logger.info("Indexation : %s", report)
    return report


def _prune(**_) -> dict[str, int]:
    """Retire de l'index les biens qui ne sont plus dans estate."""
    es = _client()
    engine = PostgresHook(postgres_conn_id=FIL_ROUGE_DB_CONN_ID).get_sqlalchemy_engine()
    with engine.connect() as conn:
        in_db = {str(r[0]) for r in conn.execute(ESTATE_IDS_QUERY)}
    in_index = {hit["_id"] for hit in helpers.scan(es, index=INDEX, query={"query": {"match_all": {}}}, _source=False)}
    gone = sorted(in_index - in_db)
    deleted = _bulk(es, delete_actions(gone)) if gone else 0
    es.indices.refresh(index=INDEX)
    report = {"in_index": len(in_index), "deleted": deleted, "count": es.count(index=INDEX)["count"]}
    logger.info("Ménage : %s", report)
    return report


with DAG(
    dag_id="estates_index",
    description="estate -> index Elasticsearch estates, puis retrait des biens disparus",
    start_date=datetime(2026, 10, 1),
    schedule="0 4 * * *",
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["flx", "search"],
) as dag:
    index = PythonOperator(task_id="index", python_callable=_index)
    prune = PythonOperator(task_id="prune", python_callable=_prune)

    index >> prune  # pyright: ignore[reportUnusedExpression]  # chaînage des tâches, idiome d'Airflow
