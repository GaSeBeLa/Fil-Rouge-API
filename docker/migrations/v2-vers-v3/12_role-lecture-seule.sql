-- =====================================================================
-- v2 → v3, LOT12 — Ajouter le rôle en lecture seule
-- =====================================================================
--
-- POURQUOI ? Q14 du registre md/questions/questions-a-trancher.md, ligne
--   « Rôle en lecture seule » ; accord de Jeff sur Discord le 2026-10-07.
--   Les deux rôles, justifiés dans docker/init-v3/README.md :
--   - côté application : la valeur 'Reader' dans role (id 5) ;
--   - côté PostgreSQL : fil_rouge_reader, SELECT seulement — même texte
--     que docker/init-v3/04_role-lecture-seule.sql.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   10_reprise-mandats.sql (LOT11 n'a pas de migration). Une base neuve
--   part de docker/init-v3/. Le banc `bash docker/compare_v2_v3.sh`
--   vérifie que les deux chemins mènent au même schéma.
--
-- COMMENT ? Depuis docker/, après avoir ajouté POSTGRES_READER_PASSWORD
--   à docker/.env puis relancé `docker compose up -d` (le conteneur doit
--   voir la variable) :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/12_role-lecture-seule.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. L'id 5 de role
--   déjà pris par une autre valeur : la migration s'arrête avant.
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM role WHERE id = 5 AND wording <> 'Reader') THEN
        RAISE EXCEPTION 'LOT12 : l''id 5 de role est déjà pris par une autre '
            'valeur. Vérifier avant de migrer (Q14).';
    END IF;
END $$;

-- Côté application : la valeur 'Reader'.
ALTER TABLE role DROP CONSTRAINT IF EXISTS role_wording_check;
ALTER TABLE role ADD CONSTRAINT role_wording_check
    CHECK (wording IN ('Admin', 'Client', 'Hunter', 'Manager', 'Reader'));

INSERT INTO role (id, wording) OVERRIDING SYSTEM VALUE VALUES (5, 'Reader')
ON CONFLICT (id) DO NOTHING;

-- Côté PostgreSQL : même texte que docker/init-v3/04_role-lecture-seule.sql.
\getenv reader_password POSTGRES_READER_PASSWORD

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fil_rouge_reader') THEN
        CREATE ROLE fil_rouge_reader NOLOGIN;
    END IF;
END $$;

\if :{?reader_password}
    SELECT :'reader_password' <> '' AS reader_has_password \gset
\else
    \set reader_has_password false
\endif
\if :reader_has_password
    SELECT format('ALTER ROLE fil_rouge_reader LOGIN PASSWORD %L', :'reader_password') \gexec
\else
    ALTER ROLE fil_rouge_reader NOLOGIN;
\endif

SELECT format('GRANT CONNECT ON DATABASE %I TO fil_rouge_reader', current_database()) \gexec
GRANT USAGE ON SCHEMA public TO fil_rouge_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO fil_rouge_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO fil_rouge_reader;

COMMIT;
