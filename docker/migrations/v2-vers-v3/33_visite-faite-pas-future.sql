-- =====================================================================
-- v2 → v3, après 32 — Une visite enregistrée est une visite faite
-- =====================================================================
--
-- POURQUOI ? ADR-053, P24 (choix du groupe du 2026-10-12) : on n'enregistre
--   que les visites faites. Une visite datée de 2030 était acceptée, et le
--   nombre de visites entre dans la rémunération (Readme l. 88).
--
-- QUOI ? chk_visit_not_in_future : visit_date au plus la date UTC du jour,
--   plus un jour de marge pour les fuseaux en avance sur UTC (Paris : UTC+1,
--   UTC+2). clock_timestamp(), pas now() (heure du début de la transaction,
--   même piège que P34). Limite : comme tout CHECK, vérifié à l'écriture
--   seulement. Rien n'est modifié : 0 visite en base (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/33_visite-faite-pas-future.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : DROP CONSTRAINT.
-- =====================================================================

BEGIN;

ALTER TABLE visit DROP CONSTRAINT IF EXISTS chk_visit_not_in_future;
ALTER TABLE visit ADD CONSTRAINT chk_visit_not_in_future
    CHECK (visit_date <= (clock_timestamp() AT TIME ZONE 'utc')::date + 1);

COMMIT;
