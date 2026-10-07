-- =====================================================================
-- v2 → v3, LOT5 — Paiement : note figée, taux borné, dates
-- =====================================================================
--
-- POURQUOI ? Cinq cartes du registre md/questions/questions-a-trancher.md :
--
--   - Q-REM-17 (revue le 2026-10-07) : la facture est hors périmètre
--     (Q-JEF-23). Les statuts 'invoice_submitted' et 'verified' sortent ;
--     deux dates entrent, announced_at et scheduled_for, chacune tenue par
--     un CHECK comme chk_paid ;
--   - Q-REM-03 : performance_score, le score qui a servi au calcul ;
--   - Q-REM-04 : calculation_details, tous les termes du calcul, en JSONB ;
--   - Q-REM-10 : final_rate exigé hors refus, dans chk_refused ;
--   - Q-REM-19 (R21, confirmé par Jeff : Q-JEF-01) : final_rate entre 20 %
--     et 60 %.
--
-- AVANT D'ACTIVER, compté le 2026-10-07 : 0 paiement en base de dev, et
--   init-v2/02 n'en insère aucun. Une base où des paiements ont été ajoutés
--   depuis doit les compter : un statut de facture, une date manquante ou
--   un taux hors bornes font refuser l'ALTER, et tout est annulé.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   04_mandat-duree-exclusivite.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/05_paiement.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Aucune ligne
--   n'est modifiée.
-- =====================================================================

BEGIN;

-- Q-REM-17 : les étapes de la facture sortent (CHECK en ligne de
-- init-v2/01, nommé payment_status_check par PostgreSQL).
ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_status_check;
ALTER TABLE payment ADD CONSTRAINT payment_status_check
    CHECK (status IN ('refused', 'announced', 'scheduled', 'paid'));

-- Q-REM-17 : une date par étape.
ALTER TABLE payment ADD COLUMN IF NOT EXISTS announced_at  TIMESTAMP;
ALTER TABLE payment ADD COLUMN IF NOT EXISTS scheduled_for DATE;

ALTER TABLE payment DROP CONSTRAINT IF EXISTS chk_announced;
ALTER TABLE payment ADD CONSTRAINT chk_announced
    CHECK ((status IN ('announced', 'scheduled', 'paid')
            AND announced_at IS NOT NULL)
        OR (status = 'refused' AND announced_at IS NULL));

ALTER TABLE payment DROP CONSTRAINT IF EXISTS chk_scheduled;
ALTER TABLE payment ADD CONSTRAINT chk_scheduled
    CHECK ((status IN ('scheduled', 'paid') AND scheduled_for IS NOT NULL)
        OR (status IN ('refused', 'announced') AND scheduled_for IS NULL));

-- Q-REM-19 (R21) : le taux final entre 20 % et 60 %, à la place de 0 à 1
-- (CHECK en ligne, nommé payment_final_rate_check par PostgreSQL).
ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_final_rate_check;
ALTER TABLE payment ADD CONSTRAINT payment_final_rate_check
    CHECK (final_rate BETWEEN 0.20 AND 0.60);

-- Q-REM-03 : le score figé, même domaine que hunter_performance.score.
-- Q-REM-04 : les termes du calcul.
ALTER TABLE payment ADD COLUMN IF NOT EXISTS performance_score NUMERIC(4,1);
ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_performance_score_check;
ALTER TABLE payment ADD CONSTRAINT payment_performance_score_check
    CHECK (performance_score BETWEEN 0 AND 100);
ALTER TABLE payment ADD COLUMN IF NOT EXISTS calculation_details JSONB;

-- Q-REM-10 : final_rate exigé hors refus ; Q-REM-03 : pas de score sur un
-- refus. Le reste de chk_refused (ADR-024) est inchangé.
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
            AND id_commission_scale IS NULL)
        OR (status <> 'refused'
            AND refusal_reason      IS NULL
            AND base_rate           IS NOT NULL
            AND seniority_rate      IS NOT NULL
            AND performance_rate    IS NOT NULL
            AND final_rate          IS NOT NULL
            AND id_commission_scale IS NOT NULL));

COMMIT;
