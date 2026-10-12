-- =====================================================================
-- v2 → v3, après 33 — Un paiement payé et une note ne sont pas datés du futur
-- =====================================================================
--
-- POURQUOI ? Audit P34 (réparation prête, vérifiée le 2026-10-12) : un
--   paiement 'paid' daté de 2099 était accepté, et une note de performance
--   aussi. Un paiement payé a eu lieu ; une note est calculée, pas prévue.
--
-- QUOI ? chk_paid_not_in_future (payment.paid_at) et chk_perf_not_in_future
--   (hunter_performance.scored_at) : au plus l'heure UTC, plus 5 minutes de
--   marge pour l'écart d'horloge avec l'API. clock_timestamp(), pas now() :
--   now() est l'heure du début de la transaction, et une heure prise par
--   l'API juste après serait refusée. Limite : comme tout CHECK, vérifié à
--   l'écriture seulement. Rien n'est modifié : 0 paiement, 0 note en base
--   (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/34_paiement-et-note-pas-futurs.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : DROP CONSTRAINT.
-- =====================================================================

BEGIN;

ALTER TABLE payment DROP CONSTRAINT IF EXISTS chk_paid_not_in_future;
ALTER TABLE payment ADD CONSTRAINT chk_paid_not_in_future
    CHECK (paid_at <= (clock_timestamp() AT TIME ZONE 'utc') + INTERVAL '5 minutes');

ALTER TABLE hunter_performance DROP CONSTRAINT IF EXISTS chk_perf_not_in_future;
ALTER TABLE hunter_performance ADD CONSTRAINT chk_perf_not_in_future
    CHECK (scored_at <= (clock_timestamp() AT TIME ZONE 'utc') + INTERVAL '5 minutes');

COMMIT;
