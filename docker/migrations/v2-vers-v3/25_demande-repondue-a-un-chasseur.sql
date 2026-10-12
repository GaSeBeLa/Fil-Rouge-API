-- =====================================================================
-- v2 → v3, après 24 — Une demande acceptée a un chasseur
-- =====================================================================
--
-- POURQUOI ? Audit P6 (réparation prête, vérifiée le 2026-10-12) : une
--   demande 'accepted' pouvait n'avoir aucun chasseur. 'accepted', 'rejected'
--   et 'launched' sont la réponse d'un chasseur (ADR-041, Décision 1).
--
-- QUOI ? chk_search_request_hunter_after_confirmed : sans chasseur, seule
--   'confirmed' passe. Rien n'est modifié dans les données : les 18 demandes
--   reprises sont 'launched', toutes avec un chasseur (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/25_demande-repondue-a-un-chasseur.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : DROP CONSTRAINT.
-- =====================================================================

BEGIN;

ALTER TABLE search_request DROP CONSTRAINT IF EXISTS chk_search_request_hunter_after_confirmed;
ALTER TABLE search_request ADD CONSTRAINT chk_search_request_hunter_after_confirmed
    CHECK (status = 'confirmed' OR id_hunter IS NOT NULL);

COMMIT;
