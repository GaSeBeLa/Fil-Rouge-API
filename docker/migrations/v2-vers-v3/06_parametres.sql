-- =====================================================================
-- v2 → v3, LOT6 — Paramètres de rémunération et journal des notes
-- =====================================================================
--
-- POURQUOI ? Cinq cartes du registre md/questions-a-trancher-2026-10-02.md :
--
--   - Q-REM-05 : une table versionnée remuneration_parameters ; les CHECK
--     de seniority_rate (0 à 0,10) et performance_rate (-0,20 à 0,20) sont
--     relâchés au domaine d'un taux (0 à 1, -1 à 1 ; bornes choisies le
--     2026-10-07, justifiées dans init-v3/01) ;
--   - Q-SCH-17 : parameters_fees, une grille vaut jusqu'à la suivante —
--     valid_from devient effective_from, valid_until et l'EXCLUDE sortent,
--     un UNIQUE (effective_from) entre ;
--   - Q-SCH-15 : un taux de tranche de commission_scale est > 0 ;
--   - Q-REM-13 : une clé de sale vers parameters_fees ;
--   - Q-SCH-06 : hunter_performance devient un journal — scored_at, deux
--     UNIQUE et un index ; valid_from, valid_until, chk_perf_period et
--     excl_perf_no_overlap sortent.
--
-- AVANT D'ACTIVER, compté le 2026-10-07 : 0 vente, 0 grille d'honoraires,
--   0 note, 0 tranche en base de dev, et init-v2/02 n'en insère aucune.
--   Une base qui en a eu depuis est protégée ainsi :
--   - une date de fin qui dirait autre chose que « jusqu'à la suivante »
--     serait perdue : la migration s'arrête avant (Q-JEF-26, aucune ancienne
--     donnée supprimée) ;
--   - une vente reçoit la grille en vigueur à sa date (la dernière dont
--     effective_from <= signature_date) ; sans grille, la migration s'arrête ;
--   - une tranche à 0 %, deux grilles le même jour, deux notes pour un même
--     paiement font refuser l'ALTER.
--   Dans tous ces cas, tout est annulé.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   05_paiement.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/06_parametres.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Seules les
--   lignes de sale (la clé) et de hunter_performance (la date) sont
--   complétées ; aucune n'est supprimée.
-- =====================================================================

BEGIN;

-- Garde (Q-JEF-26) : avant de retirer les dates de fin, vérifier qu'elles
-- ne disaient rien de plus que « jusqu'à la suivante ». Les bornes de v2
-- sont incluses ('[]') : une période qui s'arrête la veille de la suivante
-- ne perd rien. Ne joue que si les colonnes v2 sont encore là.
DO $$
DECLARE
    n_fees INTEGER := 0;
    n_perf INTEGER := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'parameters_fees' AND column_name = 'valid_until') THEN
        EXECUTE $q$
            SELECT count(*) FROM (
                SELECT valid_until,
                       lead(valid_from) OVER (ORDER BY valid_from) - 1 AS veille
                FROM parameters_fees) t
            WHERE valid_until IS NOT NULL AND valid_until IS DISTINCT FROM veille
        $q$ INTO n_fees;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'hunter_performance' AND column_name = 'valid_until') THEN
        EXECUTE $q$
            SELECT count(*) FROM (
                SELECT valid_until,
                       lead(valid_from) OVER (PARTITION BY id_hunter
                                              ORDER BY valid_from) - 1 AS veille
                FROM hunter_performance) t
            WHERE valid_until IS NOT NULL AND valid_until IS DISTINCT FROM veille
        $q$ INTO n_perf;
    END IF;
    IF n_fees > 0 OR n_perf > 0 THEN
        RAISE EXCEPTION 'LOT6 : % grille(s) et % note(s) ont une date de fin '
            'qui ne tombe pas la veille de la suivante ; elle serait perdue. '
            'Les relire avant de migrer (Q-SCH-17, Q-SCH-06).', n_fees, n_perf;
    END IF;
END $$;

-- Q-SCH-17 : une grille d'honoraires vaut jusqu'à la suivante.
ALTER TABLE parameters_fees DROP CONSTRAINT IF EXISTS excl_fees_no_overlap;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'parameters_fees' AND column_name = 'valid_from') THEN
        ALTER TABLE parameters_fees RENAME COLUMN valid_from TO effective_from;
    END IF;
END $$;
ALTER TABLE parameters_fees DROP COLUMN IF EXISTS valid_until;
ALTER TABLE parameters_fees DROP CONSTRAINT IF EXISTS uq_fees_effective_from;
ALTER TABLE parameters_fees ADD CONSTRAINT uq_fees_effective_from
    UNIQUE (effective_from);

-- Q-SCH-15 : un taux de tranche est > 0 (CHECK en ligne de init-v2/01,
-- nommé commission_scale_rate_check par PostgreSQL).
ALTER TABLE commission_scale DROP CONSTRAINT IF EXISTS commission_scale_rate_check;
ALTER TABLE commission_scale ADD CONSTRAINT commission_scale_rate_check
    CHECK (rate > 0 AND rate <= 1);

-- Q-REM-05 : les deux réglages sortent des CHECK ; restent les bornes du
-- domaine (CHECK en ligne, nommés par PostgreSQL).
ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_seniority_rate_check;
ALTER TABLE payment ADD CONSTRAINT payment_seniority_rate_check
    CHECK (seniority_rate BETWEEN 0 AND 1);
ALTER TABLE payment DROP CONSTRAINT IF EXISTS payment_performance_rate_check;
ALTER TABLE payment ADD CONSTRAINT payment_performance_rate_check
    CHECK (performance_rate BETWEEN -1 AND 1);

-- Q-REM-05 : la table des paramètres, vide (les valeurs viendront du seed).
-- Même définition que init-v3/01, où elle est commentée.
CREATE TABLE IF NOT EXISTS remuneration_parameters (
    id                      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at              TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    effective_from          DATE NOT NULL,
    weight_delay            NUMERIC(5,4) NOT NULL,
    weight_exclusivity      NUMERIC(5,4) NOT NULL,
    weight_sales            NUMERIC(5,4) NOT NULL,
    weight_mandates         NUMERIC(5,4) NOT NULL,
    weight_visits           NUMERIC(5,4) NOT NULL,
    delay_tiers             JSONB NOT NULL,
    visit_tiers             JSONB NOT NULL,
    score_exclusive         NUMERIC(4,1) NOT NULL,
    score_non_exclusive     NUMERIC(4,1) NOT NULL,
    points_per_sale         NUMERIC(4,1) NOT NULL,
    points_per_mandate      NUMERIC(4,1) NOT NULL,
    window_months           INTEGER NOT NULL,
    seniority_rate_per_year NUMERIC(5,4) NOT NULL,
    seniority_cap           NUMERIC(5,4) NOT NULL,
    score_pivot             NUMERIC(4,1) NOT NULL,
    score_half_range        NUMERIC(4,1) NOT NULL,
    performance_amplitude   NUMERIC(5,4) NOT NULL,
    rate_floor              NUMERIC(5,4) NOT NULL,
    rate_ceiling            NUMERIC(5,4) NOT NULL,

    CONSTRAINT uq_remuneration_effective_from UNIQUE (effective_from)
);

-- Q-REM-13 : chaque vente pointe la grille qui a donné ses honoraires —
-- la grille en vigueur à la date de l'acte.
ALTER TABLE sale ADD COLUMN IF NOT EXISTS id_parameters_fees INTEGER
    REFERENCES parameters_fees(id) ON DELETE RESTRICT;
UPDATE sale s
   SET id_parameters_fees = (SELECT pf.id FROM parameters_fees pf
                              WHERE pf.effective_from <= s.signature_date
                              ORDER BY pf.effective_from DESC
                              LIMIT 1)
 WHERE s.id_parameters_fees IS NULL;
DO $$
DECLARE
    n INTEGER;
BEGIN
    SELECT count(*) INTO n FROM sale WHERE id_parameters_fees IS NULL;
    IF n > 0 THEN
        RAISE EXCEPTION 'LOT6 : % vente(s) datée(s) avant la première grille '
            'd''honoraires. Ajouter la grille de leur date, puis relancer '
            '(Q-REM-13, Q-REM-15).', n;
    END IF;
END $$;
ALTER TABLE sale ALTER COLUMN id_parameters_fees SET NOT NULL;

-- Q-SCH-06 : le journal des notes. La date d'une note reprise = le début
-- de sa période v2, à minuit.
ALTER TABLE hunter_performance ADD COLUMN IF NOT EXISTS scored_at TIMESTAMP;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'hunter_performance' AND column_name = 'valid_from') THEN
        EXECUTE 'UPDATE hunter_performance SET scored_at = valid_from::timestamp
                  WHERE scored_at IS NULL';
    END IF;
END $$;
ALTER TABLE hunter_performance ALTER COLUMN scored_at SET NOT NULL;
ALTER TABLE hunter_performance DROP CONSTRAINT IF EXISTS chk_perf_period;
ALTER TABLE hunter_performance DROP CONSTRAINT IF EXISTS excl_perf_no_overlap;
ALTER TABLE hunter_performance DROP COLUMN IF EXISTS valid_from;
ALTER TABLE hunter_performance DROP COLUMN IF EXISTS valid_until;
ALTER TABLE hunter_performance DROP CONSTRAINT IF EXISTS uq_perf_payment;
ALTER TABLE hunter_performance ADD CONSTRAINT uq_perf_payment UNIQUE (id_payment);
ALTER TABLE hunter_performance DROP CONSTRAINT IF EXISTS uq_perf_mandate;
ALTER TABLE hunter_performance ADD CONSTRAINT uq_perf_mandate UNIQUE (id_mandate);
CREATE INDEX IF NOT EXISTS idx_perf_hunter_scored_at
    ON hunter_performance (id_hunter, scored_at DESC);

COMMIT;
