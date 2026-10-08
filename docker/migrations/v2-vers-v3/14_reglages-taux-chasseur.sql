-- =====================================================================
-- v2 → v3, après le chantier LOT — Réglages du taux du chasseur
-- =====================================================================
--
-- POURQUOI ? Décidé par le groupe le 2026-10-08 (G2, rapport
--   md/journal/2026-10-08-tables-parametres-et-schema.html, option A) :
--   remuneration_parameters devient hunter_rate_parameters.
--   « Paramètres de rémunération » se confondait avec parameters_fees, les
--   honoraires de l'agence. Le nouveau nom dit ce que règle la table : tout
--   ce qui fait passer du taux du barème au taux final du chasseur
--   (performance, ancienneté, bornes).
--
--   Suivent le nom : la séquence de l'id, la clé primaire et la contrainte
--   UNIQUE, pour qu'une base migrée porte les mêmes noms qu'une base neuve.
--   06_parametres.sql garde l'ancien nom : c'est l'historique.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   13_compte-active-et-quartier.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/14_reglages-taux-chasseur.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord : chaque
--   renommage ne se fait que si l'ancien nom existe encore. Aucune ligne
--   ne change ; les droits de fil_rouge_reader suivent la table.
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.remuneration_parameters') IS NOT NULL THEN
        ALTER TABLE remuneration_parameters RENAME TO hunter_rate_parameters;
    END IF;
    IF to_regclass('public.remuneration_parameters_id_seq') IS NOT NULL THEN
        ALTER SEQUENCE remuneration_parameters_id_seq
            RENAME TO hunter_rate_parameters_id_seq;
    END IF;
    -- Renommer la contrainte renomme aussi son index.
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'remuneration_parameters_pkey') THEN
        ALTER TABLE hunter_rate_parameters
            RENAME CONSTRAINT remuneration_parameters_pkey
            TO hunter_rate_parameters_pkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'uq_remuneration_effective_from') THEN
        ALTER TABLE hunter_rate_parameters
            RENAME CONSTRAINT uq_remuneration_effective_from
            TO uq_hunter_rate_effective_from;
    END IF;
END $$;

COMMIT;
