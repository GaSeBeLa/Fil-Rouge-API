# Image d'Airflow du projet (chantier FLX, fiche FLX1) : l'image officielle,
# étendue. Construite par docker/docker-compose.yml (profil "airflow") pour
# airflow-init, airflow-webserver et airflow-scheduler.
#
# Version : Airflow 2.11.2, décidée par Seb (Discord, 2026-10-15, flux-1).
# Le tag existe sur Docker Hub (hub.docker.com/v2/repositories/apache/airflow/tags/2.11.2,
# poussé le 2026-03-14, lu le 2026-10-15). Airflow 2 est en fin de vie
# depuis le 2026-04-22 (airflow.apache.org, « Supported versions »).
#
# Pourquoi une image étendue et pas _PIP_ADDITIONAL_REQUIREMENTS : le compose
# officiel de la 2.11.2 réserve cette variable aux « quick checks » ; pour le
# développement et les tests, il dit d'étendre l'image
# (airflow.apache.org/docs/apache-airflow/2.11.2/docker-compose.yaml, lu le
# 2026-10-15). Méthode : airflow.apache.org/docs/docker-stack/build.html,
# « Adding new PyPI packages individually » (lu le 2026-10-15) :
#   - pip s'exécute avec l'utilisateur airflow, jamais root ;
#   - toujours réinstaller apache-airflow==${AIRFLOW_VERSION}, pour que pip
#     ne change pas la version d'Airflow en passant.
#
# Aucun paquet ajouté pour l'instant : les providers amazon (MinIO, S3) et
# postgres sont déjà dans l'image officielle. Une fiche qui en ajoute un le
# fait ici, version figée, sur ce modèle :
#   RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" "paquet==x.y.z"
FROM apache/airflow:2.11.2
