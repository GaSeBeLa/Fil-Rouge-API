-- =====================================================================
-- v2 → v3, chantier PRF (PRF8) — "user".id_role disparaît ; role ne
-- garde que les trois rôles qui ont une fiche
-- =====================================================================
--
-- POURQUOI ? Décision de Seb du 2026-10-15 (chantier PRF, maquette
--   https://claude.ai/artifact/YNT5ANwbWYKp6SERVvvn9K) : le rôle se lit sur
--   "user".system_role (Admin, Reader) ou sur role_wording de la fiche
--   (PRF6, PRF7). id_role n'est plus lu par l'API depuis PRF7.
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant PRF8. Une
--   base créée par init-v3 après PRF8 n'a plus id_role (docker/init-v3/01
--   et 02) : le script le voit et ne fait rien.
--
-- QUOI ?
--   0) mesure : un compte Admin ou Reader par id_role SANS le system_role
--      qui va avec perdrait son rôle : la migration s'arrête (ROLLBACK) avec
--      son numéro, à régler à la main (46 le remplit d'ordinaire) ;
--   1) DROP COLUMN id_role (sa FK vers role(id) part avec elle, et le droit
--      de lecture de fil_rouge_reader sur la colonne aussi) ;
--   2) role ne garde que 'Client', 'Hunter', 'Manager' : lignes Admin et
--      Reader supprimées, CHECK resserré (même nom, role_wording_check).
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare les deux bases.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/47_sans-id-role.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/47_sans-id-role.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction ; rejouable. Retour en arrière : remettre les
--   lignes Admin (4) et Reader (5) et l'ancien CHECK de role, puis
--   ADD COLUMN id_role, rempli depuis system_role ou la fiche du compte.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    v_bad TEXT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'user'
                      AND column_name = 'id_role') THEN
        RAISE NOTICE '47 : "user".id_role est deja retire, rien a faire.';
        RETURN;
    END IF;

    -- 0) Mesure (EXECUTE : la colonne n'existe pas toujours à la compilation).
    EXECUTE $q$
        SELECT string_agg(u.id::text, ', ')
          FROM "user" u JOIN role r ON r.id = u.id_role
         WHERE r.wording IN ('Admin', 'Reader')
           AND u.system_role IS DISTINCT FROM r.wording
    $q$ INTO v_bad;
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION '47 : comptes Admin ou Reader sans le system_role qui va avec : %', v_bad;
    END IF;

    -- 1) La colonne, et sa FK avec elle.
    ALTER TABLE "user" DROP COLUMN id_role;

    -- 2) role : les trois rôles qui ont une fiche.
    DELETE FROM role WHERE wording NOT IN ('Client', 'Hunter', 'Manager');
    ALTER TABLE role DROP CONSTRAINT role_wording_check;
    ALTER TABLE role ADD CONSTRAINT role_wording_check
        CHECK (wording IN ('Client', 'Hunter', 'Manager'));
END
$$;

COMMIT;
