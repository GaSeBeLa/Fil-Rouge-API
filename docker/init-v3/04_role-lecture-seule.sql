-- =====================================================================
-- init-v3, LOT12 — Le rôle PostgreSQL en lecture seule
-- =====================================================================
--
-- POURQUOI ? Q14 du registre md/questions/questions-a-trancher.md, ligne
--   « Rôle en lecture seule » ; accord de Jeff sur Discord le 2026-10-07,
--   à condition de le justifier (docker/init-v3/README.md, « Rôle en
--   lecture seule — LOT12 »). Un compte qui lit toutes les tables et
--   n'écrit nulle part : pour une requête d'analyse ou un outil de
--   rapport, sans le mot de passe du superutilisateur.
--
-- QUOI ?
--   - fil_rouge_reader, créé une fois par serveur : un rôle vit dans le
--     cluster, partagé par toutes ses bases (dont celles du banc et de
--     test) ; sa création est donc idempotente ;
--   - mot de passe : POSTGRES_READER_PASSWORD, lu dans docker/.env et
--     passé au conteneur par docker-compose.yml. Vide ou absent : le rôle
--     existe mais ne peut pas se connecter (NOLOGIN) ;
--   - droits, base par base : CONNECT, USAGE sur le schéma public, SELECT
--     sur les tables présentes et sur les futures (ALTER DEFAULT
--     PRIVILEGES). Rien d'autre : ni INSERT, ni UPDATE, ni DELETE ;
--   - sauf "user".password : la table est rouverte colonne par colonne,
--     sans le mot de passe (rapport « Rôle lecteur et mots de passe »,
--     2026-10-08 : L1 A, L2 A). Retirer la seule colonne ne sert à rien
--     quand le droit a été donné sur toute la table (doc PostgreSQL,
--     REVOKE) : on retire la table, puis on rouvre les colonnes permises.
--     Liste écrite en dur : une colonne ajoutée à "user" reste fermée tant
--     qu'on ne l'ouvre pas ici et dans 18_role-lecture-seule-sans-mot-de-passe.sql.
--     Conséquence : SELECT * sur "user" est refusé au rôle.
--
-- Psql seulement (\getenv, \if, \gexec) : chargé par l'entrypoint de
-- l'image, par docker/create_test_db.sh et par docker/compare_v2_v3.sh.
-- Une base v2 existante reçoit le même par
-- docker/migrations/v2-vers-v3/12_role-lecture-seule.sql, puis la
-- fermeture du mot de passe par 18_role-lecture-seule-sans-mot-de-passe.sql.
-- =====================================================================

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

-- Le mot de passe reste fermé : ce GRANT doit rester après celui de la table.
REVOKE SELECT ON "user" FROM fil_rouge_reader;
GRANT SELECT (id, created_at, email, is_activated, id_role) ON "user" TO fil_rouge_reader;
