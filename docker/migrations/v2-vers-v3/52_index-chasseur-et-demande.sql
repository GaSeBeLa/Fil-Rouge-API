-- =====================================================================
-- v2 → v3 — les index des filtres par chasseur et par demande
-- =====================================================================
--
-- POURQUOI ? PostgreSQL n'indexe pas une clé étrangère tout seul. Trois
--   filtres de l'API lisent toute la table sans index : les biens retenus
--   pour une demande (suggestions), les sélections d'un chasseur, les
--   dernières demandes d'un chasseur. Mesuré le 2026-11-19 à ~500 000
--   sélections : × 35, × 15 et × 100 (note d'indexation, dépôt Fil-Rouge,
--   livrables/2-modelisation/2.8-note-indexation.md). Choix A de Sébastien.
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant le
--   2026-11-19. Une base créée par init-v3 après a déjà les index
--   (docker/init-v3/01) : IF NOT EXISTS, le script ne change rien.
--
-- QUOI ? Trois index : estate_searchrequest (id_search_request),
--   estate_searchrequest (id_hunter), search_request (id_hunter,
--   created_at DESC). Aucune donnée ne change.
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare les deux bases.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/52_index-chasseur-et-demande.sql
--
-- =====================================================================

BEGIN;

CREATE INDEX IF NOT EXISTS idx_estate_searchrequest_request
    ON estate_searchrequest (id_search_request);

CREATE INDEX IF NOT EXISTS idx_estate_searchrequest_hunter
    ON estate_searchrequest (id_hunter);

CREATE INDEX IF NOT EXISTS idx_search_request_hunter_created
    ON search_request (id_hunter, created_at DESC);

COMMIT;
