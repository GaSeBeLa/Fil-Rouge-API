-- =====================================================================
-- Chaque chasseur a un manager — hunter.id_realestatemanager NOT NULL
-- =====================================================================
--
-- POURQUOI ? Le MPD 03 4 (2026-09-22) relie Hunter (1,1) à
--   RealEstateManager (0,n) : un chasseur a toujours un manager. La
--   colonne n'existait pas. Choix du groupe, appuyé sur l'exemple ENF-03
--   du sujet (« le chasseur concerné et son manager ») — un exemple de
--   rédaction, pas une exigence du client. À acter en ADR.
--
-- POUR QUI ? Seulement pour une base **déjà créée**. Si tu peux repartir
--   de zéro, ne lance pas ce script : fais plutôt, depuis docker/ :
--
--       docker compose down -v
--       docker compose up -d
--
--   01_create_fil_rouge_immobilier.sql et 02_migration.sql contiennent
--   déjà tout ce qui suit.
--
-- CE DOSSIER N'EST PAS MONTÉ par docker compose (seul init-v2/ l'est) :
--   ce fichier ne part jamais tout seul, il se lance à la main.
--
-- COMMENT ? Depuis docker/ :
--
--   docker exec -i fil_rouge_immobilier_db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/2026-09-22_hunter_manager.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord.
--
-- CE QUE CE SCRIPT INVENTE : un manager PLACEHOLDER (compte bloqué par le
--   même mot de passe placeholder que les 24 comptes migrés), car aucune
--   base existante n'a de manager. Tous les chasseurs sans manager lui
--   sont rattachés. ⚠️ HYPOTHÈSE de migration : ce n'est pas une personne.
--   Le seed devra le remplacer par de vrais managers.
--
-- Détail et justification : docker/init-v2/README.md §3.6
-- =====================================================================

BEGIN;

-- 1. Le manager placeholder : compte + profil ---------------------------
--    Pas d'id forcé : sur une base vivante, la séquence a pu avancer.
--    L'e-mail sert de clé de reprise, pour que le script soit rejouable.

INSERT INTO "user" (email, password, id_role)
SELECT 'manager.migration@chassimmo.fr',
       '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET',
       (SELECT id FROM role WHERE wording = 'Manager')
WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE email = 'manager.migration@chassimmo.fr');

INSERT INTO real_estate_manager (id_user, first_name, last_name, phone_number)
SELECT u.id, 'Manager', 'Migration', '0000000000'
FROM "user" u
WHERE u.email = 'manager.migration@chassimmo.fr'
ON CONFLICT (id_user) DO NOTHING;

-- 2. La colonne, d'abord nullable --------------------------------------
--    IF NOT EXISTS : au second passage, la colonne (et sa FK) est déjà là.

ALTER TABLE hunter
    ADD COLUMN IF NOT EXISTS id_realestatemanager INTEGER
        REFERENCES real_estate_manager(id_user) ON DELETE RESTRICT;

-- 3. Les chasseurs orphelins sont rattachés au placeholder -------------

UPDATE hunter
   SET id_realestatemanager = (SELECT id FROM "user"
                                WHERE email = 'manager.migration@chassimmo.fr')
 WHERE id_realestatemanager IS NULL;

-- 4. Puis NOT NULL, comme dans le MPD ----------------------------------

ALTER TABLE hunter ALTER COLUMN id_realestatemanager SET NOT NULL;

-- 5. Documentation de la colonne --------------------------------------

COMMENT ON COLUMN hunter.id_realestatemanager IS
  'Reference real_estate_manager(id_user) — donc un id de "user". Le manager du chasseur (choix du groupe, 2026-09-22).';

COMMIT;

-- =====================================================================
-- Vérifier après coup : zéro chasseur sans manager, et un seul
-- manager placeholder.
--
--   SELECT count(*) AS sans_manager
--   FROM hunter WHERE id_realestatemanager IS NULL;
--
--   SELECT u.id, u.email, r.wording, m.first_name, m.last_name,
--          (SELECT count(*) FROM hunter h WHERE h.id_realestatemanager = u.id) AS chasseurs
--   FROM "user" u
--   JOIN role r ON r.id = u.id_role
--   JOIN real_estate_manager m ON m.id_user = u.id;
-- =====================================================================
