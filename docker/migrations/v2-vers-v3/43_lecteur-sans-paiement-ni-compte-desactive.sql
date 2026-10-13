-- =====================================================================
-- v2 → v3, après ADR-027 — Le rôle en lecture seule ne lit ni les
-- paiements ni les comptes désactivés
-- =====================================================================
--
-- POURQUOI ? Le compte d'analyse fil_rouge_reader suit la cible du rôle
--   Reader de l'API (fiche DRO9, chantier « Droits : moindre privilège ») :
--   - payment : le montant et l'IBAN ne sont lus que par le chasseur
--     concerné et son manager (ADR-027, point 8) ;
--   - un compte désactivé : ses données personnelles ne sont plus lues que
--     par l'Admin (ADR-027, point 7 ; ADR-049). Une politique par ligne
--     (row level security) sur "user", client, hunter et
--     real_estate_manager ne montre au rôle que les comptes actifs.
--
-- POUR QUI ? Toute base où 12_role-lecture-seule.sql a déjà joué. Une base
--   neuve a déjà le correctif : docker/init-v3/04_role-lecture-seule.sql.
--
-- L'API N'EST PAS FILTRÉE : elle se connecte en postgres, propriétaire des
--   tables et superutilisateur (rolbypassrls), mesuré le 2026-10-13. Une
--   table sous politique ne montre rien à un rôle qui n'en a pas : seuls
--   postgres et fil_rouge_reader existent sur le serveur.
--
-- ⚠️ Les comptes migrés sont tous désactivés (sans mot de passe) : après
--   cette migration, fil_rouge_reader ne voit aucun profil tant qu'on n'en
--   active pas.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/43_lecteur-sans-paiement-ni-compte-desactive.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/43_lecteur-sans-paiement-ni-compte-desactive.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord, rien n'est
--   effacé. Retour en arrière : GRANT SELECT ON payment TO
--   fil_rouge_reader, puis, pour chacune des quatre tables,
--   DROP POLICY reader_active_accounts ON <table> et
--   ALTER TABLE <table> DISABLE ROW LEVEL SECURITY. Le rôle absent : la
--   migration s'arrête avec un message clair.
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fil_rouge_reader') THEN
        RAISE EXCEPTION 'Le rôle fil_rouge_reader n''existe pas. Jouer '
            '12_role-lecture-seule.sql avant cette migration.';
    END IF;
END $$;

REVOKE SELECT ON payment FROM fil_rouge_reader;

ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reader_active_accounts ON "user";
CREATE POLICY reader_active_accounts ON "user" FOR SELECT TO fil_rouge_reader
    USING (is_activated);

ALTER TABLE client ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reader_active_accounts ON client;
CREATE POLICY reader_active_accounts ON client FOR SELECT TO fil_rouge_reader
    USING (id_user IN (SELECT id FROM "user" WHERE is_activated));

ALTER TABLE hunter ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reader_active_accounts ON hunter;
CREATE POLICY reader_active_accounts ON hunter FOR SELECT TO fil_rouge_reader
    USING (id_user IN (SELECT id FROM "user" WHERE is_activated));

ALTER TABLE real_estate_manager ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reader_active_accounts ON real_estate_manager;
CREATE POLICY reader_active_accounts ON real_estate_manager FOR SELECT TO fil_rouge_reader
    USING (id_user IN (SELECT id FROM "user" WHERE is_activated));

COMMIT;
