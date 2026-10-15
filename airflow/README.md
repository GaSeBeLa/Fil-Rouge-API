# airflow/ — les flux de données

Chantier FLX. Airflow 2.11.2 tourne dans le profil `airflow` du
`docker/docker-compose.yml` (lancement : `API/README.md`, « Airflow »).

Règle du cours : **le DAG orchestre, `src/` transforme**.

## Arborescence

| Chemin | Rôle | Dans le conteneur |
|---|---|---|
| `Dockerfile` | l'image `apache/airflow:2.11.2`, étendue | — |
| `dags/` | les DAG : `with DAG(...)` + `PythonOperator` | `/opt/airflow/dags` (lecture seule) |
| `src/` | le code métier, en Python pur | `/opt/airflow/src` (lecture seule) |
| `src/config.py` | réglages lus dans l'environnement, sans secret par défaut | |
| `tests/` | tests de `src/`, sans Airflow ni Docker | — |

Un DAG importe le métier par `from src.config import ...`.

## Les connexions

Déclarées par des variables `AIRFLOW_CONN_*` dans `docker-compose.yml`, avec
les valeurs de `docker/.env`. Rien à saisir dans l'interface.

| Connexion | Vers | Utilisée par |
|---|---|---|
| `minio_default` | MinIO, `http://minio:9000` | `S3Hook` |
| `fil_rouge_db` | base `fil_rouge_immobilier` du service `db` | `PostgresHook` |

Buckets de MinIO, créés par `minio-setup` : `bronze`, `silver`, `gold`,
`quarantine`.

## Lancer les tests

Depuis la racine du dépôt, avec `pytest` installé sur le poste :

```bash
pytest airflow/tests -q
```

## Lancer un DAG à la main

Depuis `docker/`, une exécution complète, sans passer par le scheduler :

```bash
docker compose exec airflow-scheduler airflow dags test smoke_dag 2026-10-15
```

Ou dans l'interface http://localhost:8080 : activer le DAG, puis le bouton
« Trigger DAG ».

`smoke_dag` vérifie la plomberie : il écrit `bronze/smoke/<date>.json`, puis
compte les lignes de `estate`. Pour voir l'objet :

```bash
docker compose --profile airflow exec minio sh -c 'mc alias set m http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc ls m/bronze/smoke/'
```
