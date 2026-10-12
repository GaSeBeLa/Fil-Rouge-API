-- =====================================================================
-- v2 → v3, après 26 — Une nouvelle version de critères donne son motif
-- =====================================================================
--
-- POURQUOI ? Audit P9 (réparation prête, vérifiée le 2026-10-12) : le
--   Readme (l. 234) demande « date, auteur, motif de chaque changement »,
--   mais criteria.change_reason était facultatif.
--
-- QUOI ? chk_criteria_change_reason : une version qui a une version
--   précédente a un motif. La version de départ n'en a pas besoin. Rien
--   n'est modifié : aucune version reprise n'a de version précédente
--   (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/27_criteres-motif-obligatoire.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : DROP CONSTRAINT.
-- =====================================================================

BEGIN;

ALTER TABLE criteria DROP CONSTRAINT IF EXISTS chk_criteria_change_reason;
ALTER TABLE criteria ADD CONSTRAINT chk_criteria_change_reason
    CHECK (id_previous_version IS NULL OR change_reason IS NOT NULL);

COMMIT;
