-- =====================================================================
-- v2 → v3, après 31 — Une offre vient du chasseur de son mandat
-- =====================================================================
--
-- POURQUOI ? Audit P22 (réparation prête, vérifiée le 2026-10-12) :
--   estate_proposed.id_hunter n'était pas comparé à mandate.id_hunter. Une
--   offre sur le mandat de Bruno pouvait nommer Chloé, et la rémunération va
--   au chasseur à l'origine de la vente (00_…feature:34).
--
-- QUOI ? uq_mandate_id_hunter (cible, partagée avec P35) et la clé
--   composite fk_proposed_hunter_of_mandate. Effet de bord : le chasseur d'un
--   mandat qui a des offres ne peut plus changer (réaffectation reportée,
--   Q-MAN-08). Aucune colonne ajoutée, rien de modifié : 0 offre en base
--   (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/32_offre-du-chasseur-du-mandat.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : supprimer la clé
--   composite, puis uq_mandate_id_hunter (si P35 ne s'en sert pas).
-- =====================================================================

BEGIN;

ALTER TABLE estate_proposed DROP CONSTRAINT IF EXISTS fk_proposed_hunter_of_mandate;
ALTER TABLE mandate DROP CONSTRAINT IF EXISTS uq_mandate_id_hunter;

ALTER TABLE mandate ADD CONSTRAINT uq_mandate_id_hunter UNIQUE (id, id_hunter);
ALTER TABLE estate_proposed ADD CONSTRAINT fk_proposed_hunter_of_mandate
    FOREIGN KEY (id_mandate, id_hunter)
    REFERENCES mandate (id, id_hunter) ON DELETE RESTRICT;

COMMIT;
