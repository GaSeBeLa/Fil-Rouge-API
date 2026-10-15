#!/usr/bin/env bash
# =====================================================================
# init-v3, FLX1 — La base de métadonnées d'Airflow
# =====================================================================
#
# POURQUOI ? Airflow garde ses DAG, ses exécutions et ses connexions dans
# une base à lui. Décision de Seb (Discord, 2026-10-15, chantier FLX) : une
# base « airflow » dans NOTRE PostgreSQL (service db), jamais mêlée à
# fil_rouge_immobilier.
#
# QUOI ?
#   - le rôle airflow, propriétaire de la base airflow. Mot de passe :
#     AIRFLOW_DB_PASSWORD, lu dans docker/.env et passé au conteneur db par
#     docker-compose.yml. Vide ou absent : le rôle existe sans pouvoir se
#     connecter (NOLOGIN), comme fil_rouge_reader (04) ;
#   - la base airflow, fermée aux autres rôles (REVOKE CONNECT ... FROM
#     PUBLIC) : fil_rouge_reader n'y entre pas.
#
# QUAND ? Un script .sh de /docker-entrypoint-initdb.d est joué par
# l'entrypoint de l'image postgres, à la création d'une base NEUVE
# seulement. Le banc v2/v3 et create_test_db.sh ne jouent que les *.sql :
# ce script ne les touche pas.
#
# BASE EXISTANTE (volume déjà créé) : le même script se rejoue à la main,
# depuis docker/ (voir API/README.md, « Airflow ») :
#     docker compose up -d db
#     docker compose exec db bash /docker-entrypoint-initdb.d/07_airflow-base.sh
# Il est rejouable : il ne crée que ce qui manque, et remet le mot de passe.
# =====================================================================
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v airflow_password="${AIRFLOW_DB_PASSWORD:-}" <<'EOSQL'
SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'airflow') AS role_missing \gset
\if :role_missing
    CREATE ROLE airflow NOLOGIN;
\endif

SELECT :'airflow_password' <> '' AS has_password \gset
\if :has_password
    ALTER ROLE airflow LOGIN PASSWORD :'airflow_password';
\else
    ALTER ROLE airflow NOLOGIN PASSWORD NULL;
\endif

SELECT 'CREATE DATABASE airflow OWNER airflow'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'airflow') \gexec

REVOKE CONNECT ON DATABASE airflow FROM PUBLIC;
GRANT CONNECT ON DATABASE airflow TO airflow;
EOSQL
