-- =====================================================================
-- v2 → v3, chantier SUG (SUG4) — l'état d'un bien dans la sélection
-- =====================================================================
--
-- POURQUOI ? Le moteur de suggestion (chantier SUG) ajoute des biens à la
--   sélection d'une demande sans que le chasseur les ait choisis. Chaque
--   ligne de estate_searchrequest porte donc un état : 'suggested'
--   (proposé par la machine), 'kept' (gardé par le chasseur), 'dismissed'
--   (écarté). On ne propose au client qu'un bien 'kept' (P19 renforcée,
--   acceptée par Seb le 2026-11-03 ; md/journal/2026-11-02-suggestion-de-biens.md).
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant SUG4. Une
--   base créée par init-v3 après SUG4 a déjà la colonne (docker/init-v3/01) :
--   le script ne change rien.
--
-- QUOI ? ADD COLUMN IF NOT EXISTS status, NOT NULL, défaut 'suggested',
--   CHECK sur les trois valeurs. Les lignes qui existaient avant la colonne
--   passent à 'kept' : elles ont été choisies par un chasseur.
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare les deux bases.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/50_etat-de-la-selection.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/50_etat-de-la-selection.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction ; rejouable — la colonne n'est ajoutée, et les
--   lignes passées à 'kept', qu'au premier passage. Retour en arrière :
--   ALTER TABLE estate_searchrequest DROP COLUMN status (les états sont perdus).
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'estate_searchrequest' AND column_name = 'status'
    ) THEN
        -- Ajoutée d'abord au défaut 'kept' : les lignes existantes le prennent,
        -- puis le défaut des lignes neuves devient 'suggested'.
        ALTER TABLE estate_searchrequest
            ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'kept'
            CHECK (status IN ('suggested', 'kept', 'dismissed'));
        ALTER TABLE estate_searchrequest ALTER COLUMN status SET DEFAULT 'suggested';
    END IF;
END
$$;

COMMIT;
