-- =====================================================================
-- v2 → v3, après ADR-054 — Le rôle en lecture seule ne lit pas les contacts
-- =====================================================================
--
-- POURQUOI ? ADR-054, question 5 : estate_contact porte le nom, le
--   téléphone et l'email d'un tiers, le vendeur. Une analyse n'en a pas
--   besoin (minimisation, RGPD) : fil_rouge_reader ne lit plus la table.
--   Choix de Sébastien, Discord, 2026-10-13.
--
-- POUR QUI ? Toute base où 40_contact-du-bien.sql a déjà joué. Une base
--   neuve a déjà le correctif : docker/init-v3/04_role-lecture-seule.sql.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/41_contact-ferme-au-lecteur.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord, rien n'est
--   effacé. Retour en arrière : GRANT SELECT ON estate_contact TO
--   fil_rouge_reader. Le rôle absent : la migration s'arrête avec un
--   message clair.
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fil_rouge_reader') THEN
        RAISE EXCEPTION 'Le rôle fil_rouge_reader n''existe pas. Jouer '
            '12_role-lecture-seule.sql avant cette migration.';
    END IF;
END $$;

REVOKE SELECT ON estate_contact FROM fil_rouge_reader;

COMMIT;
