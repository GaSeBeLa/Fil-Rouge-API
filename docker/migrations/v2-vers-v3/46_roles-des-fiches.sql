-- =====================================================================
-- v2 → v3, chantier PRF (PRF6) — Le rôle porté par la fiche, ou par le
-- compte sans fiche ; une fiche au plus par compte
-- =====================================================================
--
-- POURQUOI ? Décision de Seb du 2026-10-15 (chantier PRF, maquette
--   https://claude.ai/artifact/YNT5ANwbWYKp6SERVvvn9K) : un compte porte une
--   seule casquette. Soit une fiche (client, hunter, real_estate_manager),
--   qui dit son rôle par role_wording ; soit un system_role (Admin, Reader),
--   sans fiche. Ajout seulement : "user".id_role reste jusqu'à PRF8.
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant PRF6. Une
--   base créée par init-v3 après PRF6 a déjà tout (docker/init-v3/01 et
--   02) : les IF NOT EXISTS et CREATE OR REPLACE ne changent rien.
--
-- QUOI ?
--   0) mesure : un compte présent dans deux tables de fiche, ou un compte
--      Admin / Reader qui a une fiche, arrête la migration (ROLLBACK) avec
--      son numéro — à trancher à la main, jamais en silence ;
--   1) "user".system_role, rempli depuis id_role pour Admin et Reader ;
--   2) role_wording sur les trois fiches, rempli par sa valeur par défaut ;
--   3) check_one_profile_per_user() et ses quatre triggers ;
--   4) fil_rouge_reader lit system_role (même liste que init-v3/04).
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql, section
--   2 bis. Le banc v2/v3 (API/tests/integration/test_banc_v2_v3.py) compare
--   les deux bases, texte de la fonction compris : il garde ce fichier et
--   01 alignés.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/46_roles-des-fiches.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/46_roles-des-fiches.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction ; rejouable. Retour en arrière : DROP des quatre
--   triggers et de la fonction, puis DROP COLUMN system_role et des trois
--   role_wording.
-- =====================================================================

BEGIN;

-- 0) Mesure : la règle doit déjà tenir sur les données présentes.
DO $$
DECLARE
    v_bad TEXT;
BEGIN
    WITH f AS (
        SELECT id_user FROM client
        UNION ALL SELECT id_user FROM hunter
        UNION ALL SELECT id_user FROM real_estate_manager)
    SELECT string_agg(id_user::text, ', ') INTO v_bad
      FROM (SELECT id_user FROM f GROUP BY id_user HAVING count(*) > 1) d;
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION '46 : comptes avec plusieurs fiches : %', v_bad;
    END IF;

    SELECT string_agg(u.id::text, ', ') INTO v_bad
      FROM "user" u JOIN role r ON r.id = u.id_role
     WHERE r.wording IN ('Admin', 'Reader')
       AND (EXISTS (SELECT 1 FROM client WHERE id_user = u.id)
            OR EXISTS (SELECT 1 FROM hunter WHERE id_user = u.id)
            OR EXISTS (SELECT 1 FROM real_estate_manager WHERE id_user = u.id));
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION '46 : comptes Admin ou Reader avec une fiche : %', v_bad;
    END IF;
END
$$;

-- 1) Le rôle d'un compte sans fiche.
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS
    system_role VARCHAR(10) CHECK (system_role IN ('Admin', 'Reader'));

UPDATE "user" u SET system_role = r.wording
  FROM role r
 WHERE r.id = u.id_role AND r.wording IN ('Admin', 'Reader')
   AND u.system_role IS DISTINCT FROM r.wording;

-- 2) Le rôle porté par chaque fiche.
ALTER TABLE client ADD COLUMN IF NOT EXISTS
    role_wording VARCHAR(20) NOT NULL DEFAULT 'Client'
    CHECK (role_wording = 'Client') REFERENCES role(wording);
ALTER TABLE hunter ADD COLUMN IF NOT EXISTS
    role_wording VARCHAR(20) NOT NULL DEFAULT 'Hunter'
    CHECK (role_wording = 'Hunter') REFERENCES role(wording);
ALTER TABLE real_estate_manager ADD COLUMN IF NOT EXISTS
    role_wording VARCHAR(20) NOT NULL DEFAULT 'Manager'
    CHECK (role_wording = 'Manager') REFERENCES role(wording);

-- 3) Une fiche au plus par compte (même texte que 01, section 2 bis).
CREATE OR REPLACE FUNCTION check_one_profile_per_user() RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    v_user INTEGER;
BEGIN
    IF TG_TABLE_NAME = 'user' THEN
        IF NEW.system_role IS NULL THEN
            RETURN NEW;
        END IF;
        v_user := NEW.id;
    ELSE
        v_user := NEW.id_user;
        PERFORM 1 FROM "user" WHERE id = v_user FOR NO KEY UPDATE;
        IF EXISTS (SELECT 1 FROM "user" WHERE id = v_user AND system_role IS NOT NULL) THEN
            RAISE EXCEPTION
                'PRF6 : le compte % a un system_role, il ne peut pas avoir de fiche', v_user
                USING ERRCODE = '23514', CONSTRAINT = 'one_profile_per_user';
        END IF;
    END IF;
    IF (TG_TABLE_NAME <> 'client' AND EXISTS (SELECT 1 FROM client WHERE id_user = v_user))
       OR (TG_TABLE_NAME <> 'hunter' AND EXISTS (SELECT 1 FROM hunter WHERE id_user = v_user))
       OR (TG_TABLE_NAME <> 'real_estate_manager'
           AND EXISTS (SELECT 1 FROM real_estate_manager WHERE id_user = v_user)) THEN
        RAISE EXCEPTION
            'PRF6 : le compte % a deja une fiche, une seule par compte (et aucune avec un system_role)', v_user
            USING ERRCODE = '23514', CONSTRAINT = 'one_profile_per_user';
    END IF;
    RETURN NEW;
END $fn$;

DROP TRIGGER IF EXISTS trg_client_one_profile ON client;
CREATE TRIGGER trg_client_one_profile
    BEFORE INSERT OR UPDATE OF id_user ON client
    FOR EACH ROW EXECUTE FUNCTION check_one_profile_per_user();
DROP TRIGGER IF EXISTS trg_hunter_one_profile ON hunter;
CREATE TRIGGER trg_hunter_one_profile
    BEFORE INSERT OR UPDATE OF id_user ON hunter
    FOR EACH ROW EXECUTE FUNCTION check_one_profile_per_user();
DROP TRIGGER IF EXISTS trg_real_estate_manager_one_profile ON real_estate_manager;
CREATE TRIGGER trg_real_estate_manager_one_profile
    BEFORE INSERT OR UPDATE OF id_user ON real_estate_manager
    FOR EACH ROW EXECUTE FUNCTION check_one_profile_per_user();
DROP TRIGGER IF EXISTS trg_user_system_role ON "user";
CREATE TRIGGER trg_user_system_role
    BEFORE INSERT OR UPDATE OF system_role ON "user"
    FOR EACH ROW EXECUTE FUNCTION check_one_profile_per_user();

-- 4) Le lecteur lit system_role (init-v3/04 : même liste, après le REVOKE
--    de 18_role-lecture-seule-sans-mot-de-passe.sql).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fil_rouge_reader') THEN
        GRANT SELECT (system_role) ON "user" TO fil_rouge_reader;
    END IF;
END
$$;

COMMENT ON COLUMN "user".system_role IS
  'Role d''un compte SANS fiche (Admin, Reader) ; vide si le compte a une fiche (PRF6).';
COMMENT ON COLUMN client.role_wording IS
  'Role porte par la fiche, toujours Client ; reference role(wording) (PRF6).';
COMMENT ON COLUMN hunter.role_wording IS
  'Role porte par la fiche, toujours Hunter ; reference role(wording) (PRF6).';
COMMENT ON COLUMN real_estate_manager.role_wording IS
  'Role porte par la fiche, toujours Manager ; reference role(wording) (PRF6).';

COMMIT;
