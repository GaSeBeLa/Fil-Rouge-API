-- =====================================================================
-- v2 → v3, après 37 — Un bien n'est vendu qu'une fois
-- =====================================================================
--
-- POURQUOI ? ADR-053, P37 (Gabriel, choix du groupe du 2026-10-12) :
--   sale.id_mandate est UNIQUE, mais pas sale.id_estate. Le même bien
--   pouvait donc être vendu deux fois, sur deux mandats. Une revente
--   plus tard serait une nouvelle annonce, donc un autre estate.
--
-- QUOI ? La contrainte uq_sale_estate UNIQUE (id_estate). Rien n'est
--   modifié : 0 vente en base (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/38_un-bien-vendu-une-fois.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière :
--   ALTER TABLE sale DROP CONSTRAINT uq_sale_estate.
-- =====================================================================

BEGIN;

ALTER TABLE sale DROP CONSTRAINT IF EXISTS uq_sale_estate;
ALTER TABLE sale ADD CONSTRAINT uq_sale_estate UNIQUE (id_estate);

COMMIT;
