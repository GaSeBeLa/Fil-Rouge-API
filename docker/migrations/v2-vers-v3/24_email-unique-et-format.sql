-- =====================================================================
-- v2 → v3, après 23 — Un email unique à la majuscule près, et bien formé
-- =====================================================================
--
-- POURQUOI ? ADR-053, P2 (choix du groupe du 2026-10-12) : "user".email
--   était UNIQUE mais sensible à la casse, sans contrôle de format.
--   Alice@Example.com et alice@example.com faisaient deux comptes.
--
-- QUOI ? Un CHECK de forme (ck_user_email_format) et un index unique sur
--   lower(email) (uq_user_email_lower). Rien n'est modifié dans les données :
--   compté le 2026-10-12, 25 emails, 25 distincts en minuscules, 0 mal formé.
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/24_email-unique-et-format.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : DROP INDEX
--   uq_user_email_lower ; DROP CONSTRAINT ck_user_email_format.
-- =====================================================================

BEGIN;

ALTER TABLE "user" DROP CONSTRAINT IF EXISTS ck_user_email_format;
ALTER TABLE "user" ADD CONSTRAINT ck_user_email_format
    CHECK (email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$');

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_email_lower ON "user" (lower(email));

COMMIT;
