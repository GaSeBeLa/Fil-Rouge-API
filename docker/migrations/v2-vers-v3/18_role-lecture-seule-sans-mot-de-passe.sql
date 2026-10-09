-- =====================================================================
-- v2 → v3, après LOT12 — Le rôle en lecture seule ne lit plus le mot de passe
-- =====================================================================
--
-- POURQUOI ? Rapport « Rôle lecteur et mots de passe » du 2026-10-08 :
--   fil_rouge_reader lisait toute la table "user", colonne password comprise
--   (6 colonnes sur 6), alors que ADR-027 veut un lecteur sans le mot de
--   passe. Choix du groupe : L1 A (droits par colonne), L2 A (liste écrite
--   en dur), L3 A (cette migration pour les bases déjà créées).
--
-- POUR QUI ? Toute base où 12_role-lecture-seule.sql a déjà joué. Une base
--   neuve a déjà le correctif : docker/init-v3/04_role-lecture-seule.sql.
--
-- QUOI ? Le droit est retiré sur la table, puis redonné sur les cinq
--   colonnes permises. Retirer la seule colonne password ne marcherait pas
--   (doc PostgreSQL, REVOKE : sans effet si le droit couvre la table).
--   Une colonne ajoutée plus tard à "user" reste fermée : l'ouvrir ici et
--   dans 04_role-lecture-seule.sql.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/18_role-lecture-seule-sans-mot-de-passe.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord, rien n'est
--   effacé. Retour en arrière : GRANT SELECT ON "user" TO fil_rouge_reader.
--   Le rôle absent : la migration s'arrête avec un message clair.
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fil_rouge_reader') THEN
        RAISE EXCEPTION 'Le rôle fil_rouge_reader n''existe pas. Jouer '
            '12_role-lecture-seule.sql avant cette migration.';
    END IF;
END $$;

REVOKE SELECT ON "user" FROM fil_rouge_reader;
GRANT SELECT (id, created_at, email, is_activated, id_role) ON "user" TO fil_rouge_reader;

COMMIT;
