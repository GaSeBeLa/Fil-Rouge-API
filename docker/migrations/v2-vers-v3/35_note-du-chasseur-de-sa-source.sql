-- =====================================================================
-- v2 → v3, après 34 — Une note va au chasseur de son paiement ou de son mandat
-- =====================================================================
--
-- POURQUOI ? Audit P35 (réparation prête, vérifiée le 2026-10-12) :
--   hunter_performance.id_hunter n'était comparé ni au chasseur du paiement,
--   ni à celui du mandat. La note du paiement de Bruno pouvait aller à Chloé.
--   Un paiement ou un mandat échu note SON chasseur (ADR-042).
--
-- QUOI ? uq_payment_id_hunter (cible) et deux clés composites,
--   fk_perf_payment_same_hunter et fk_perf_mandate_same_hunter. La cible du
--   mandat, uq_mandate_id_hunter, vient de la migration 32. Qu'un mandat
--   noté 'mandate_expired' soit vraiment échu change dans le temps : API.
--   Aucune colonne ajoutée, rien de modifié : 0 note en base (compté le
--   2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée, après 32_offre-du-chasseur-du-mandat.sql.
--   Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/35_note-du-chasseur-de-sa-source.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : supprimer les deux
--   clés composites, puis uq_payment_id_hunter.
-- =====================================================================

BEGIN;

ALTER TABLE hunter_performance DROP CONSTRAINT IF EXISTS fk_perf_payment_same_hunter;
ALTER TABLE hunter_performance DROP CONSTRAINT IF EXISTS fk_perf_mandate_same_hunter;
ALTER TABLE payment DROP CONSTRAINT IF EXISTS uq_payment_id_hunter;

ALTER TABLE payment ADD CONSTRAINT uq_payment_id_hunter UNIQUE (id, id_hunter);
ALTER TABLE hunter_performance ADD CONSTRAINT fk_perf_payment_same_hunter
    FOREIGN KEY (id_payment, id_hunter)
    REFERENCES payment (id, id_hunter) ON DELETE RESTRICT;
ALTER TABLE hunter_performance ADD CONSTRAINT fk_perf_mandate_same_hunter
    FOREIGN KEY (id_mandate, id_hunter)
    REFERENCES mandate (id, id_hunter) ON DELETE RESTRICT;

COMMIT;
