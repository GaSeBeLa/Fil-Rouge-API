#!/usr/bin/env bash
# ============================================================================
# compare_v2_v3.sh — Lance le banc « base neuve = base migrée ».
# ============================================================================
#
# Le banc est un test pytest depuis le chantier BAN :
# API/tests/integration/test_banc_v2_v3.py. Il recrée deux bases jetables
# (init-v2 + migrations/v2-vers-v3 d'un côté, init-v3 de l'autre), compare
# leurs descriptions, et échoue en montrant le diff. Son en-tête dit tout ;
# ce script ne fait que le lancer dans le conteneur `api`.
#
# Il tourne aussi à chaque `python -m pytest`, avec le reste de la suite.
#
# VARIABLES (passées au test si elles sont posées) : BANC_V2_DIR,
# BANC_V3_DIR, BANC_MIG_DIR, BANC_DEMO_TABLES. Les dossiers sont des chemins
# DANS le conteneur api ; un mutant joue sur une copie, par exemple :
#     docker compose exec -T api cp -r /api/sql/init-v3 /tmp/v3-mutant
#     BANC_V3_DIR=/tmp/v3-mutant bash docker/compare_v2_v3.sh
#
# LANCER (depuis n'importe où, conteneurs `db` et `api` démarrés) :
#     bash docker/compare_v2_v3.sh
#
# Sortie : celle de pytest ; 0 si les deux bases sont identiques.
# ============================================================================

set -euo pipefail
# Git Bash (Windows) réécrit /tmp/… en C:/…/tmp/… : les chemins passés au
# conteneur doivent rester tels quels.
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")"   # docker compose lit docker-compose.yml ici

env_args=()
for name in BANC_V2_DIR BANC_V3_DIR BANC_MIG_DIR BANC_DEMO_TABLES; do
    if [ -n "${!name+x}" ]; then
        env_args+=(-e "$name=${!name}")
    fi
done

exec docker compose exec -T "${env_args[@]}" api \
    python -m pytest -q tests/integration/test_banc_v2_v3.py
