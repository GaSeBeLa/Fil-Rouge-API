-- =====================================================================
-- v2 → v3, après 19 — Un paiement versé garde sa note et le détail de son calcul
-- =====================================================================
--
-- POURQUOI ? ADR-033, Décision 3, confirmée par Sébastien le 2026-10-09
--   (D2 du rapport ADR du 8 octobre) : tout paiement non refusé garde la note
--   du chasseur (performance_score) et le détail de son calcul
--   (calculation_details), pour qu'il s'explique toujours. Un refus n'a ni
--   l'un ni l'autre. Cela revient sur le 3e point de la carte D8 du rapport
--   LOT1 à LOT5 (« pas obligatoire ailleurs »).
--
-- QUOI ? chk_refused : performance_score et calculation_details sont NULL sur
--   un refus, et NOT NULL sinon. Le reste de la contrainte est inchangé
--   (même texte que 15_paiement-reglages-taux.sql, plus ces deux colonnes).
--
-- AVANT D'ACTIVER, compté le 2026-10-09 en base de dev : 0 paiement. Une base
--   qui en a depuis est protégée ainsi : un paiement non refusé sans note ou
--   sans détail, on ne devine pas ce qu'ils auraient dû être, la migration
--   s'arrête avant. Un refus qui porterait un détail l'arrête aussi.
--
-- POUR QUI ? Toute base v2 déjà migrée, après 19. Une base neuve part de
--   docker/init-v3/. Le banc `bash docker/compare_v2_v3.sh` vérifie que les
--   deux chemins mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/20_paiement-note-et-detail-obligatoires.sql
--
-- SÛRETÉ : une transaction, rejouable. Aucune ligne ne change ni n'est
--   supprimée. Retour en arrière : rejouer 15_paiement-reglages-taux.sql
--   (partie chk_refused).
-- =====================================================================

BEGIN;

DO $$
DECLARE
    n_versé_incomplet INTEGER;
    n_refus_avec_detail INTEGER;
BEGIN
    SELECT count(*) INTO n_versé_incomplet FROM payment
    WHERE status <> 'refused'
      AND (performance_score IS NULL OR calculation_details IS NULL);
    IF n_versé_incomplet > 0 THEN
        RAISE EXCEPTION '% paiement(s) non refusé(s) sans note ou sans détail du '
            'calcul : les renseigner avant de migrer', n_versé_incomplet;
    END IF;

    SELECT count(*) INTO n_refus_avec_detail FROM payment
    WHERE status = 'refused' AND calculation_details IS NOT NULL;
    IF n_refus_avec_detail > 0 THEN
        RAISE EXCEPTION '% refus portent un détail de calcul : le vider avant de '
            'migrer', n_refus_avec_detail;
    END IF;
END $$;

ALTER TABLE payment DROP CONSTRAINT IF EXISTS chk_refused;
ALTER TABLE payment ADD CONSTRAINT chk_refused
    CHECK ((status =  'refused'
            AND refusal_reason      IS NOT NULL
            AND amount              =  0
            AND base_rate           IS NULL
            AND seniority_rate      IS NULL
            AND performance_rate    IS NULL
            AND final_rate          IS NULL
            AND performance_score   IS NULL
            AND calculation_details IS NULL
            AND id_commission_scale IS NULL
            AND id_hunter_rate_parameters IS NULL)
        OR (status <> 'refused'
            AND refusal_reason      IS NULL
            AND base_rate           IS NOT NULL
            AND seniority_rate      IS NOT NULL
            AND performance_rate    IS NOT NULL
            AND final_rate          IS NOT NULL
            AND performance_score   IS NOT NULL
            AND calculation_details IS NOT NULL
            AND id_commission_scale IS NOT NULL
            AND id_hunter_rate_parameters IS NOT NULL));

COMMIT;
