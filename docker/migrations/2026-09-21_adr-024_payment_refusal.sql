-- =====================================================================
-- ADR-024 — Traçabilité du refus de rémunération du chasseur
-- =====================================================================
--
-- POUR QUI ? Seulement pour une base **déjà créée** que l'on ne veut pas
--   refaire. Si tu peux repartir de zéro, ne lance pas ce script : fais
--   plutôt, depuis docker/ :
--
--       docker compose down -v
--       docker compose up -d
--
--   Les scripts de init-v2/ ne s'exécutent qu'à la création du volume.
--   01_create_fil_rouge_immobilier.sql contient déjà tout ce qui suit.
--   Le « -v » efface les données : sans conséquence tant que tout vient
--   des scripts, ce qui ne sera plus vrai une fois le seed écrit.
--
-- CE DOSSIER N'EST PAS MONTÉ par docker compose (seul init-v2/ l'est) :
--   ce fichier ne part donc jamais tout seul. Il se lance à la main.
--
-- COMMENT ? Depuis docker/ :
--
--   docker exec -i fil_rouge_immobilier_db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/2026-09-21_adr-024_payment_refusal.sql
--
-- SÛRETÉ : tout est dans une transaction. En cas d'erreur, rien n'est
--   appliqué. Le script est rejouable : le relancer ne casse rien.
--
-- Détail et justification : md/adr-024-motif-refus-remuneration.md
-- =====================================================================

BEGIN;

-- 1. Le motif du droit refusé -----------------------------------------
--    Les deux valeurs viennent de l'énumération MotifRefus du sujet
--    (REGLES-CALCUL-REMUNERATION.md l. 385), en anglais (ADR-002).

ALTER TABLE payment
    ADD COLUMN IF NOT EXISTS refusal_reason VARCHAR(30);

ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_refusal_reason_check;
ALTER TABLE payment ADD  CONSTRAINT payment_refusal_reason_check
    CHECK (refusal_reason IN ('mandate_expired', 'out_of_scope'));

-- 2. L'état « refusé » -------------------------------------------------

ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_status_check;
ALTER TABLE payment ADD  CONSTRAINT payment_status_check
    CHECK (status IN ('refused', 'announced', 'invoice_submitted',
                      'verified', 'scheduled', 'paid'));

-- 3. Taux et barème deviennent facultatifs ----------------------------
--    Les bornes des CHECK ne bougent pas : en PostgreSQL, un CHECK ne
--    s'applique pas à une valeur NULL.

ALTER TABLE payment ALTER COLUMN base_rate           DROP NOT NULL;
ALTER TABLE payment ALTER COLUMN seniority_rate      DROP NOT NULL;
ALTER TABLE payment ALTER COLUMN performance_rate    DROP NOT NULL;
ALTER TABLE payment ALTER COLUMN id_commission_scale DROP NOT NULL;

-- 4. Un refus et un paiement ne se ressemblent jamais à moitié --------

ALTER TABLE payment DROP CONSTRAINT IF EXISTS chk_refused;
ALTER TABLE payment ADD  CONSTRAINT chk_refused
    CHECK ((status =  'refused'
            AND refusal_reason      IS NOT NULL
            AND amount              =  0
            AND base_rate           IS NULL
            AND seniority_rate      IS NULL
            AND performance_rate    IS NULL
            AND final_rate          IS NULL
            AND id_commission_scale IS NULL)
        OR (status <> 'refused'
            AND refusal_reason      IS NULL
            AND base_rate           IS NOT NULL
            AND seniority_rate      IS NOT NULL
            AND performance_rate    IS NOT NULL
            AND id_commission_scale IS NOT NULL));

-- 5. Documentation de la colonne --------------------------------------

COMMENT ON COLUMN payment.refusal_reason IS
  'Motif du droit refuse (ADR-024) ; NULL si le droit est ouvert.';

COMMIT;

-- =====================================================================
-- Vérifier après coup : les neuf contraintes CHECK de payment, dont
-- chk_refused et payment_refusal_reason_check.
--
--   SELECT conname, pg_get_constraintdef(oid)
--   FROM pg_constraint
--   WHERE conrelid = 'payment'::regclass AND contype = 'c'
--   ORDER BY conname;
-- =====================================================================
