#!/usr/bin/env bash
# ============================================================================
# create_test_db.sh — (Re)crée la base de test `fil_rouge_test`.
# ============================================================================
#
# POURQUOI : les tests d'intégration (API/tests/integration/) écrivent en base.
# Ils ne doivent JAMAIS toucher la base de développement `fil_rouge_immobilier`.
# Cette base de test vit dans le MÊME conteneur PostgreSQL, à côté de l'autre.
#
# CE QU'ELLE CONTIENT : les scripts 01 (schéma, 18 tables) et 02 (rôles,
# comptes migrés, correction de ck_client_address_all_or_nothing) de init-v2,
# rejoués tels quels — donc exactement les mêmes contraintes que la base de
# dev. Pas le 03 (2 556 biens) : aucun test n'en a besoin.
#
# REJOUABLE : la base est supprimée puis recréée à chaque lancement. À relancer
# après toute modification de init-v2/01 ou 02.
#
# LANCER (depuis n'importe où, conteneur `db` démarré) :
#     bash docker/create_test_db.sh
#
# docker-compose.yml n'est pas modifié : on passe par `docker compose exec`.
# ============================================================================

set -euo pipefail
cd "$(dirname "$0")"

TEST_DB="${TEST_POSTGRES_DB:-fil_rouge_test}"

# Garde-fou : ce script efface la base qu'il vise.
if [ "$TEST_DB" = "fil_rouge_immobilier" ]; then
    echo "Refusé : $TEST_DB est la base de développement." >&2
    exit 1
fi

docker compose exec -T db sh -c "
    set -e
    dropdb --if-exists --force -U \"\$POSTGRES_USER\" $TEST_DB
    createdb -U \"\$POSTGRES_USER\" $TEST_DB
    psql -q -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d $TEST_DB \
        -f /docker-entrypoint-initdb.d/01_create_fil_rouge_immobilier.sql \
        -f /docker-entrypoint-initdb.d/02_migration.sql
    psql -tA -U \"\$POSTGRES_USER\" -d $TEST_DB -c \
        \"SELECT 'tables : ' || count(*) FROM information_schema.tables WHERE table_schema = 'public'\"
"

echo "Base de test $TEST_DB prête."
