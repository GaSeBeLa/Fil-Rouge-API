-- =====================================================================
-- v2 → v3, après 35 — Une seule note de départ par chasseur
-- =====================================================================
--
-- POURQUOI ? ADR-053, P36 (choix du groupe du 2026-10-12) : un chasseur
--   pouvait avoir deux notes 'initial' (50 puis 90). La note de départ est
--   unique (ADR-042 l. 122 ; ADR-048, point 8).
--
-- QUOI ? L'index unique partiel uq_perf_one_initial. Rien n'est modifié :
--   0 note en base (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/36_une-note-initiale-par-chasseur.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : DROP INDEX.
-- =====================================================================

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_perf_one_initial
    ON hunter_performance (id_hunter) WHERE trigger_type = 'initial';

COMMIT;
