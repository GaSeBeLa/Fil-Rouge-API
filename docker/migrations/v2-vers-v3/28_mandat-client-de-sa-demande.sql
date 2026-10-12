-- =====================================================================
-- v2 → v3, après 27 — Un mandat appartient au client de sa demande
-- =====================================================================
--
-- POURQUOI ? ADR-053, P12 (choix du groupe du 2026-10-12) : un mandat du
--   client 1 pouvait viser la demande de recherche du client 2.
--
-- QUOI ? uq_search_request_id_client (cible) et la clé composite
--   fk_mandate_request_same_client. Le chasseur n'est pas comparé : la
--   réaffectation est reportée (Q-MAN-08). Aucune colonne ajoutée, rien de
--   modifié : 18 mandats repris, 0 sur la demande d'un autre client (compté
--   le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/28_mandat-client-de-sa-demande.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : supprimer la clé
--   composite, puis la contrainte UNIQUE.
-- =====================================================================

BEGIN;

ALTER TABLE mandate DROP CONSTRAINT IF EXISTS fk_mandate_request_same_client;
ALTER TABLE search_request DROP CONSTRAINT IF EXISTS uq_search_request_id_client;

ALTER TABLE search_request ADD CONSTRAINT uq_search_request_id_client UNIQUE (id, id_client);
ALTER TABLE mandate ADD CONSTRAINT fk_mandate_request_same_client
    FOREIGN KEY (id_search_request, id_client)
    REFERENCES search_request (id, id_client) ON DELETE RESTRICT;

COMMIT;
