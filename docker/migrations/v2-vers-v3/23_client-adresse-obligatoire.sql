-- =====================================================================
-- v2 → v3, après 22 — L'adresse du client devient obligatoire
-- =====================================================================
--
-- POURQUOI ? ADR-053, P3, choix du groupe du 2026-10-12 : un client sans
--   adresse était accepté (tout-ou-rien, Q-SCH-01). L'adresse est désormais
--   obligatoire. Un client rendu anonyme reçoit une adresse neutre :
--   'anonyme', '00000', 'anonyme', 'FR' (ADR-049, valeur validée par
--   Sébastien le 2026-10-12).
--
-- QUOI ? address, postal_code, town et country_iso passent en NOT NULL.
--   ck_client_address_all_or_nothing et ck_client_postal_code_needs_country
--   sont retirées : le NOT NULL les rend toujours vraies. Rien n'est modifié
--   dans les données : les 18 clients repris ont déjà 'non renseigné', 00000,
--   leur ville et 'FR' (compté le 2026-10-12, 18 sur 18).
--
-- POUR QUI ? Toute base v2 déjà migrée, après 07_personnes.sql.
--   Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/23_client-adresse-obligatoire.sql
--
-- SÛRETÉ : une transaction, rejouable. Un client sans adresse fait échouer
--   le SET NOT NULL, et rien n'est écrit. Retour en arrière : DROP NOT NULL
--   sur les quatre colonnes, puis recréer les deux contraintes (07).
-- =====================================================================

BEGIN;

ALTER TABLE client
    ALTER COLUMN address     SET NOT NULL,
    ALTER COLUMN postal_code SET NOT NULL,
    ALTER COLUMN town        SET NOT NULL,
    ALTER COLUMN country_iso SET NOT NULL;

ALTER TABLE client DROP CONSTRAINT IF EXISTS ck_client_address_all_or_nothing;
ALTER TABLE client DROP CONSTRAINT IF EXISTS ck_client_postal_code_needs_country;

COMMIT;
