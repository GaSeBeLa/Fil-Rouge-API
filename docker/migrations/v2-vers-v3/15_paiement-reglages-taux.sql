-- =====================================================================
-- v2 → v3, après le chantier LOT — Le paiement pointe vers ses réglages
-- =====================================================================
--
-- POURQUOI ? Décidé par le groupe le 2026-10-08 (G1, rapport
--   md/journal/2026-10-08-tables-parametres-et-schema.html) : chaque
--   paiement dit quelle version de hunter_rate_parameters a servi à son
--   calcul, comme il dit déjà quelle tranche du barème
--   (id_commission_scale), et comme la vente dit quelle grille
--   d'honoraires (sale.id_parameters_fees, Q-REM-13).
--
--   - payment.id_hunter_rate_parameters : clé vers hunter_rate_parameters,
--     ON DELETE RESTRICT ;
--   - chk_refused : NULL sur un refus, exigée sinon — comme
--     id_commission_scale.
--
-- AVANT D'ACTIVER, compté le 2026-10-08 en base de dev : 0 paiement, 0
--   version de réglages. Une base qui a des paiements depuis est protégée
--   ainsi : un paiement non refusé sans version, on ne devine pas laquelle
--   a servi, la migration s'arrête avant.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   14_reglages-taux-chasseur.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/15_paiement-reglages-taux.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Aucune ligne ne
--   change ni n'est supprimée.
-- =====================================================================

BEGIN;

ALTER TABLE payment ADD COLUMN IF NOT EXISTS id_hunter_rate_parameters INTEGER
    REFERENCES hunter_rate_parameters(id) ON DELETE RESTRICT;

-- Garde : un paiement non refusé sans version de réglages.
DO $$
DECLARE
    n_sans_version INTEGER;
BEGIN
    SELECT count(*) INTO n_sans_version FROM payment
    WHERE status <> 'refused' AND id_hunter_rate_parameters IS NULL;
    IF n_sans_version > 0 THEN
        RAISE EXCEPTION '% paiement(s) non refusé(s) sans version de réglages : '
            'renseigner id_hunter_rate_parameters avant de migrer', n_sans_version;
    END IF;
END $$;

-- chk_refused, avec la nouvelle clé dans les deux branches.
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
            AND id_commission_scale IS NULL
            AND id_hunter_rate_parameters IS NULL)
        OR (status <> 'refused'
            AND refusal_reason      IS NULL
            AND base_rate           IS NOT NULL
            AND seniority_rate      IS NOT NULL
            AND performance_rate    IS NOT NULL
            AND final_rate          IS NOT NULL
            AND id_commission_scale IS NOT NULL
            AND id_hunter_rate_parameters IS NOT NULL));

COMMIT;
