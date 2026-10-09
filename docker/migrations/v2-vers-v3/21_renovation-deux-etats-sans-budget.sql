-- 21 : needs_renovation passe à deux états (S7, ADR-032) et les budgets travaux disparaissent.
--
-- Pourquoi : la règle de rapprochement d'ADR-012 ne peut pas se calculer (estate n'a pas de
-- montant de travaux). Les deux budgets ne servent plus ; needs_renovation devient
-- BOOLEAN NOT NULL DEFAULT FALSE sur criteria et estate (décision du 09/10/2026).
--
-- Rejouable. Refuse de supprimer un budget travaux déjà saisi : aucune donnée perdue en silence.

BEGIN;

DO $$
DECLARE
    saisis BOOLEAN := FALSE;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'criteria'
          AND column_name = 'renovation_budget_min'
    ) THEN
        -- SQL dynamique : la colonne peut déjà avoir disparu (rejeu)
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM criteria WHERE renovation_budget_min IS NOT NULL '
             || 'OR renovation_budget_max IS NOT NULL)' INTO saisis;
        IF saisis THEN
            RAISE EXCEPTION 'criteria porte un budget travaux saisi : migration 21 arrêtée, rien supprimé';
        END IF;
    END IF;
END $$;

-- NULL -> FALSE avant de poser NOT NULL (aucun NULL dans le jeu de données connu)
UPDATE criteria SET needs_renovation = FALSE WHERE needs_renovation IS NULL;
UPDATE estate   SET needs_renovation = FALSE WHERE needs_renovation IS NULL;

ALTER TABLE criteria ALTER COLUMN needs_renovation SET DEFAULT FALSE;
ALTER TABLE criteria ALTER COLUMN needs_renovation SET NOT NULL;
ALTER TABLE estate   ALTER COLUMN needs_renovation SET DEFAULT FALSE;
ALTER TABLE estate   ALTER COLUMN needs_renovation SET NOT NULL;

ALTER TABLE criteria DROP CONSTRAINT IF EXISTS chk_renov_budget;
ALTER TABLE criteria DROP COLUMN IF EXISTS renovation_budget_min;
ALTER TABLE criteria DROP COLUMN IF EXISTS renovation_budget_max;

COMMENT ON COLUMN criteria.needs_renovation IS
  'FALSE (defaut) : pas de bien a renover. TRUE : le client accepte un bien avec travaux. Deux etats, jamais NULL (ADR-032).';
COMMENT ON COLUMN estate.needs_renovation IS
  'TRUE : l''annonce signale des travaux a prevoir. FALSE (defaut) : elle n''en parle pas. Deux etats, jamais NULL (ADR-032).';

COMMIT;
