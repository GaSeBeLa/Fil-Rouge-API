-- ============================================================================
-- 02_migration.sql — Migration Fil_Rouge_Depart -> Fil_Rouge_Immobilier
-- ADAPTÉ au schéma 19 tables (MPD 03, plus remuneration_parameters depuis
-- LOT6) et à la convention EUROS.
-- Testé : s'exécute sans erreur à la suite de 01_create_fil_rouge_immobilier.sql.
-- ============================================================================
--
-- CE QUI A CHANGÉ PAR RAPPORT À LA VERSION docker/init/02_migration.sql
-- Chaque point est justifié dans README.md de ce dossier.
--
--   1. role : colonne "libelle" -> "wording", et valeurs capitalisées
--      ('client' -> 'Client'…) car le CHECK du schéma cible n'accepte que
--      'Admin', 'Client', 'Hunter', 'Manager'. 3 lignes migrées, plus
--      'Admin' ajouté le 2026-09-22 : 4 lignes au total.
--   2. criteria : budget_min et budget_max convertis de K€ en EUROS (x 1000).
--      320.0 devient 320000.00. 17 lignes. budget_min est NULL depuis
--      LOT8 (point 9).
--   3. hunter : la colonne "commission_rate" n'existe plus dans le MPD 03
--      (la tarification vit désormais dans commission_scale et
--      parameters_fees). Retirée de l'INSERT, mais la valeur source est
--      CONSERVÉE en commentaire en fin de chaque ligne : rien n'est perdu.
--      6 lignes. Voir README point 3 : cette donnée n'a PAS été migrée vers
--      commission_scale, car son sens métier est ambigu (2,00 à 3,25 %
--      ressemble à un taux d'honoraires, pas à un taux de rémunération
--      chasseur qui va de 30 à 50 % dans le barème officiel).
--   4. hunter : "hire_date" est NOT NULL dans le schéma cible et absent de la
--      source. Repris de "user".created_at, seule date disponible. 6 lignes.
--      ⚠️ C'est une HYPOTHÈSE de migration, pas une donnée d'origine.
--   5. search_request : "status" est NOT NULL et absent de la source.
--      Insérées en 'confirmed', puis 'launched' dès qu'un mandat existe :
--      les 18 demandes (Q-MIG-03, tranché à LOT10 ; section 9).
--   6. hunter : "id_realestatemanager" est NOT NULL depuis le 2026-09-22
--      (MPD 03 4) et la source n'a AUCUN manager (deux rôles seulement :
--      client, chasseur). Un manager PLACEHOLDER est créé (user 25 + profil)
--      et les 6 chasseurs lui sont rattachés. Compte bloqué par le même
--      mot de passe placeholder que les 24 autres. Voir README §3.6.
--      ⚠️ HYPOTHÈSE de migration : ce manager n'existe pas dans la source.
--      Le seed devra le remplacer par de vrais managers.
--   7. sale : la clé id_parameters_fees (LOT6, Q-REM-13) n'a rien à
--      rattacher ici. Compté le 2026-10-07 : la source n'a aucune vente ni
--      aucune grille d'honoraires, et ce script n'en insère aucune.
--      remuneration_parameters et hunter_performance restent vides aussi.
--   8. LOT7 (2026-10-07) — valeurs factices documentées, la colonne restant
--      obligatoire (Q-JEF-26 : aucune donnée ancienne supprimée) :
--      - 18 clients sans adresse ni code postal : address = 'non renseigné',
--        postal_code = '00000'. ck_client_address_all_or_nothing reste
--        tout-ou-rien (Q-SCH-01, Q-SCH-18) : l'ALTER qui l'assouplissait ici
--        est retiré. La ville, fournie par la source, est gardée.
--      - 4 téléphones manquants (3 clients + le manager placeholder) :
--        '+33000000000', au format d'ADR-007 (Q-PRO-08, Q-MIG-07).
--      - la colonne de la carte T s'écrit is_carte_t (Q-SCH-10).
--   9. LOT8 (2026-10-07) — criteria :
--      - les 17 critères reçoivent le secteur de leur mandat : pays 'FR',
--        ville, code postal, quartier (district, NULL pour 2 secteurs)
--        (Q-MIG-08) ;
--      - budget_min à NULL, « inconnu » : il recopiait budget_max (Q-MIG-09).
--  10. LOT10 (2026-10-07) — reprise des anciens mandats, confirmée par Jeff
--      (Q-JEF-13) :
--      - mandat 13 rattaché à Nina Girard (user 19), avec sa demande et son
--        critère : 18 demandes, 18 critères, 18 mandats (Q-MIG-12) ;
--      - les 6 mandats « actif » échus au 25/07/2026 en 'expired' (Q-MIG-10) ;
--      - suspendu -> 'canceled', termine -> 'completed' (Q-MIG-13) ;
--      - demandes en 'launched' (Q-MIG-03, point 5).
--
-- ============================================================================

BEGIN;

-- Source : Fil_Rouge_Depart, Cible : public (ou Fil_Rouge_Immobilier)
SET search_path TO public, "Fil_Rouge_Depart";

-- NOTE secteurs : la table secteurs n'existe plus dans le MPD cible. Ses 10
-- lignes ne sont plus ignorées : chaque critère reçoit la ville, le code postal
-- et le quartier du secteur de son mandat (Q-MIG-08, LOT8 ; section 5).

-- Gender : NULL autorisé par défaut en Postgres (un CHECK ne rejette jamais NULL)

-- 0. ROLE
-- Table de référence des rôles (choix du groupe, 2026-09). id_role dans "user"
-- pointe ici : 1=client, 2=hunter, 3=real_estate_manager, 4=admin.
-- 'Admin' ajouté le 2026-09-22 : le CHECK de la table role l'autorisait depuis
-- l'origine, mais la ligne n'existait pas. Aucune table de profil ne lui est
-- rattachée (contrairement à client/hunter/real_estate_manager) : un admin
-- n'a pas de métier, seulement des droits. Aucun compte admin n'est créé ici,
-- tant que le hachage du mot de passe n'est pas en place (ADR-016, Argon2id).
INSERT INTO role (id, wording) OVERRIDING SYSTEM VALUE VALUES (1, 'Client') ON CONFLICT (id) DO NOTHING;
INSERT INTO role (id, wording) OVERRIDING SYSTEM VALUE VALUES (2, 'Hunter') ON CONFLICT (id) DO NOTHING;
INSERT INTO role (id, wording) OVERRIDING SYSTEM VALUE VALUES (3, 'Manager') ON CONFLICT (id) DO NOTHING;
INSERT INTO role (id, wording) OVERRIDING SYSTEM VALUE VALUES (4, 'Admin')   ON CONFLICT (id) DO NOTHING;
-- 'Reader' (Q14, LOT12) : consulte sans écrire ; aucun utilisateur ne l'a encore.
INSERT INTO role (id, wording) OVERRIDING SYSTEM VALUE VALUES (5, 'Reader')  ON CONFLICT (id) DO NOTHING;

-- 1. USERS
-- "user" est désormais minimaliste (choix du groupe, 2026-09) : id, email,
-- password, id_role, created_at. first_name/last_name/phone_number/gender/
-- country_iso sont migrés directement dans hunter/client ci-dessous.
-- password  : NOT NULL côté cible, absent côté source -> placeholder explicite qui
--             empêche toute connexion tant que le mot de passe n'a pas été réinitialisé
-- id_role   : 1-6 = hunters (id_role=2), 7-24 = clients (id_role=1),
--             25 = manager placeholder (id_role=3, voir 1 bis)
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (1, 'm.roussel@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 2, '2023-03-15'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (2, 't.nguyen@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 2, '2023-06-01'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (3, 'i.delacroix@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 2, '2024-01-10'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (4, 'm.baldini@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 2, '2024-09-22'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (5, 'a.kone@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 2, '2025-02-14'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (6, 'l.perrin@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 2, '2025-11-03'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (7, 'alice.martin@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-01-08'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (8, 'karim.benali@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-02-19'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (9, 'chloe.dubois@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-03-02'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (10, 'jean.petit@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-03-27'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (11, 'lucia.garcia@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-04-11'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (12, 'paul.moreau@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-05-30'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (13, 'emma.lefevre@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-06-15'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (14, 'giulia.rossi@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-07-04'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (15, 'hugo.fournier@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-08-21'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (16, 'sofia.andre@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-09-09'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (17, 'louis.mercier@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-10-17'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (18, 'lea.blanc@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-11-25'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (19, 'nina.girard@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2025-12-12'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (20, 'adam.bonnet@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2026-01-06'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (21, 'zoe.dupont@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2026-02-20'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (22, 'theo.lambert@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2026-03-30'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (23, 'manon.roux@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2026-05-15'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, email, password, id_role, created_at) OVERRIDING SYSTEM VALUE VALUES (24, 'ethan.faure@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 1, '2026-06-28'::date) ON CONFLICT (id) DO NOTHING;

-- 1 bis. MANAGER PLACEHOLDER (point 6 de l'en-tête, README §3.6)
-- hunter.id_realestatemanager est NOT NULL et la source n'a aucun manager.
-- Un seul compte, id_role = 3 (Manager), nom et téléphone volontairement
-- « bidon » pour qu'on ne le confonde jamais avec une personne réelle.
-- created_at = date de la migration (valeur par défaut) : aucune date source.
INSERT INTO "user" (id, email, password, id_role) OVERRIDING SYSTEM VALUE VALUES (25, 'manager.migration@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO real_estate_manager (id_user, first_name, last_name, phone_number, gender, country_iso, company_name) VALUES (25, 'Manager', 'Migration', '+33000000000', NULL, NULL, NULL) ON CONFLICT (id_user) DO NOTHING;  -- placeholder, pas une personne

-- 2. HUNTERS
-- first_name/last_name/phone_number/gender/country_iso : redescendus depuis "user"
-- company_name = NULL : la source n'a pas cette info, on n'invente pas de nom d'agence
-- is_carte_t = NULL    : idem, la 'carte T' (habilitation légale) n'existe pas côté source
-- id_realestatemanager = 25 : le manager placeholder ci-dessus (HYPOTHÈSE, point 6)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carte_t, hire_date, id_realestatemanager) VALUES (1, 'Marina', 'Roussel', '+33611223344', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 1), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.50 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carte_t, hire_date, id_realestatemanager) VALUES (2, 'Thomas', 'Nguyen', '+33622334455', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 2), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 3.00 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carte_t, hire_date, id_realestatemanager) VALUES (3, 'Inès', 'Delacroix', '+33633445566', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 3), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.75 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carte_t, hire_date, id_realestatemanager) VALUES (4, 'Marco', 'Baldini', '+33644556677', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 4), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.50 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carte_t, hire_date, id_realestatemanager) VALUES (5, 'Awa', 'Kone', '+33655667788', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 5), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 3.25 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carte_t, hire_date, id_realestatemanager) VALUES (6, 'Lucas', 'Perrin', '+33666778899', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 6), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.00 (voir README, point 3)

-- 3. CLIENTS
-- first_name/last_name/phone_number/gender/country_iso : redescendus depuis "user"
-- phone_number : NOT NULL côté cible ; 3 clients sans tel (Petit, Andre, Lambert)
--                -> placeholder '+33000000000', au format d'ADR-007 (Q-MIG-07),
--                   à corriger manuellement si besoin
-- address = 'non renseigné', postal_code = '00000' : la source n'a ni adresse ni
--                  code postal ; le tout-ou-rien les exige avec la ville (Q-SCH-01,
--                  Q-SCH-18). Mettre la ville dans l'adresse serait trompeur (ça
--                  ressemblerait à une donnée réelle qui ne l'est pas).
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (7, 'Alice', 'Martin', '+33701020304', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (8, 'Karim', 'Benali', '+33702030405', NULL, 'FR', 'Lyon', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (9, 'Chloé', 'Dubois', '+33703040506', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (10, 'Jean', 'Petit', '+33000000000', NULL, 'FR', 'Nantes', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (11, 'Lucia', 'Garcia', '+33705060708', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (12, 'Paul', 'Moreau', '+33706070809', NULL, 'FR', 'Castelnau-le-Lez', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (13, 'Emma', 'Lefevre', '+33707080910', NULL, 'FR', 'Lyon', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (14, 'Giulia', 'Rossi', '+33708091011', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (15, 'Hugo', 'Fournier', '+33709101112', NULL, 'FR', 'Sète', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (16, 'Sofia', 'Andre', '+33000000000', NULL, 'FR', 'Lattes', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (17, 'Louis', 'Mercier', '+33711121314', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (18, 'Léa', 'Blanc', '+33712131415', NULL, 'FR', 'Nantes', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (19, 'Nina', 'Girard', '+33713141516', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (20, 'Adam', 'Bonnet', '+33714151617', NULL, 'FR', 'Lyon', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (21, 'Zoé', 'Dupont', '+33715161718', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (22, 'Théo', 'Lambert', '+33000000000', NULL, 'FR', 'Sète', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (23, 'Manon', 'Roux', '+33717181920', NULL, 'FR', 'Montpellier', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (24, 'Ethan', 'Faure', '+33718192021', NULL, 'FR', 'Castelnau-le-Lez', 'non renseigné', '00000') ON CONFLICT (id_user) DO NOTHING;

-- Mandat 13 : la source vise le user 3, un chasseur. Son vrai client est
-- Nina Girard (user 19, déjà cliente) : confirmé par Jeff (Q-MIG-12,
-- Q-JEF-13 ; LOT10). Repris avec sa demande et son critère, sans compte en plus.

-- 4. SEARCH_REQUEST - id_author = client_id (le client est l'auteur de sa recherche)
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (1, '2025-02-01'::date, 7, 7, 1, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (2, '2025-03-10'::date, 8, 8, 3, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (3, '2025-04-05'::date, 9, 9, 1, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (4, '2025-05-20'::date, 10, 10, 4, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (5, '2025-06-18'::date, 11, 11, 2, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (6, '2025-07-22'::date, 12, 12, 5, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (7, '2025-09-01'::date, 13, 13, 3, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (8, '2025-09-15'::date, 14, 14, 2, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (9, '2025-10-02'::date, 15, 15, 6, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (10, '2025-11-14'::date, 16, 16, 5, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (11, '2026-01-05'::date, 17, 17, 1, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (12, '2026-01-20'::date, 18, 18, 4, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (13, '2026-02-10'::date, 19, 19, 2, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (14, '2026-03-01'::date, 20, 20, 3, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (15, '2026-03-25'::date, 21, 21, 1, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (16, '2026-04-12'::date, 22, 22, 6, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (17, '2026-05-28'::date, 23, 23, 5, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (18, '2026-07-01'::date, 24, 24, 2, 'confirmed') ON CONFLICT (id) DO NOTHING;

-- 5. CRITERIA - id_author = chasseur_id (le chasseur traduit le besoin en critères)
-- budget_max : en EUROS (INTEGER), seul montant donné par la source.
-- budget_min : NULL, « inconnu » (Q-MIG-09, LOT8) : la source n'a qu'un budget,
--   recopié jusqu'ici dans le minimum ; rien n'est inventé.
-- country_iso, town, postal_code, district : le secteur du mandat d'origine
--   (secteurs PgSQL.sql:41-51, mandats :135-159), pays 'FR' (Q-MIG-08, LOT8).
--   district vaut NULL pour Castelnau-le-Lez et Lattes, sans quartier à la source.
-- renovation_budget_min/max : nullable côté cible -> NULL (info absente côté source)
-- typology : facultative en v3 (vide permis), liste fermée -> déduite via
--   parse_typology() ci-dessus ; remplie pour les 18 critères
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 1, 'FR', 'Montpellier', '34000', 'Écusson', NULL, 320000.00, NULL, NULL, 65, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 320000, 65m2 min, balcon, calme, DPE C max') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 2, 'FR', 'Lyon', '69004', 'Croix-Rousse', NULL, 450000.00, NULL, NULL, 85, 'Appartement', 'T4 / F4', 'T4 Croix-Rousse, budget 450000, 85m2, terrasse ou jardin') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 3, 'FR', 'Montpellier', '34090', 'Beaux-Arts', NULL, 280000.00, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 280000, 45m2 min, lumineux, proche tram') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 4, 'FR', 'Nantes', '44200', 'Île de Nantes', NULL, 390000.00, NULL, NULL, NULL, 'Maison', 'T4 / F4', 'Maison Ile de Nantes, budget 390000, 3 chambres, petit exterieur') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 5, 'FR', 'Montpellier', '34000', 'Port Marianne', NULL, 550000.00, NULL, NULL, 90, 'Appartement', 'T4 / F4', 'T4 Port Marianne, budget 550000, 90m2, parking, ascenseur, vue') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 6, 'FR', 'Castelnau-le-Lez', '34170', NULL, NULL, 240000.00, NULL, NULL, 80, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 240000, 80m2, jardin, travaux OK') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 7, 'FR', 'Lyon', '69002', 'Confluence', NULL, 610000.00, NULL, NULL, 100, 'Loft', 'T3 / F3', 'Loft Confluence, budget 610000, 100m2, standing, terrasse') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 8, 'FR', 'Montpellier', '34000', 'Écusson', NULL, 300000.00, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson ou Beaux-Arts, budget 300000, charme ancien, poutres') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 9, 'FR', 'Sète', '34200', 'Centre', NULL, 260000.00, NULL, NULL, 60, 'Appartement', 'T3 / F3', 'T3 Sete centre, budget 260000, vue mer si possible, 60m2') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 10, 'FR', 'Lattes', '34970', NULL, NULL, 420000.00, NULL, NULL, NULL, 'Villa', 'T4 / F4', 'Villa Lattes, budget 420000, 4 pieces, piscine ou jardin sud') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 11, 'FR', 'Montpellier', '34000', 'Port Marianne', NULL, 350000.00, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Port Marianne, budget 350000, neuf ou recent, balcon, parking') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 12, 'FR', 'Nantes', '44200', 'Île de Nantes', NULL, 480000.00, NULL, NULL, NULL, 'Appartement', 'T4 / F4', 'Appartement Nantes, budget 480000, 4 pieces, dernier etage') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 14, 'FR', 'Lyon', '69002', 'Confluence', NULL, 700000.00, NULL, NULL, 120, 'Appartement', 'T5 / F5', 'T5 Confluence, budget 700000, 120m2, prestations haut de gamme') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 15, 'FR', 'Montpellier', '34000', 'Écusson', NULL, 310000.00, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 310000, ancien renove, cave appreciee') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 16, 'FR', 'Sète', '34200', 'Centre', NULL, 290000.00, NULL, NULL, NULL, 'Maison', 'T3 / F3', 'Maison Sete, budget 290000, 3 pieces, garage') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 17, 'FR', 'Montpellier', '34090', 'Beaux-Arts', NULL, 260000.00, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 260000, 45m2, balcon, DPE D max') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 18, 'FR', 'Castelnau-le-Lez', '34170', NULL, NULL, 330000.00, NULL, NULL, 90, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 330000, 90m2, 3 chambres, jardin') ON CONFLICT DO NOTHING;
-- Demande 13 (Nina Girard, LOT10) : même lecture du texte source ; secteur 4,
-- Figuerolles (PgSQL.sql:41-51). Inséré en dernier : id 18, comme dans
-- migrations/v2-vers-v3/10_reprise-mandats.sql.
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code, district, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 13, 'FR', 'Montpellier', '34070', 'Figuerolles', NULL, 220000.00, NULL, NULL, 40, 'Appartement', 'T2 / F2', 'T2 Figuerolles, budget 220000, premier achat, 40m2 min') ON CONFLICT DO NOTHING;

-- 6. MANDATE — statuts source traduits (Q-MIG-13, Jeff : Q-JEF-13 ; LOT10) :
--   actif -> 'active', termine -> 'completed', expire -> 'expired',
--   suspendu -> 'canceled' : pas de pause dans la cible, ni de nouvel état.
-- Les 6 mandats « actif » déjà finis à la date de l'audit, le 25/07/2026
-- (MAND-0004, 0007, 0009, 0010, 0011, 0012), sont repris en 'expired'
-- (Q-MIG-10, confirmé par Jeff). Date fixe : le résultat ne dépend pas du
-- jour du lancement. MAND-0013, 0014, 0015, finis depuis, restent 'active' :
-- les faire expirer revient à l'application.
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (1, 'MAND-0001', 'completed', '2025-02-01'::date, ('2025-02-01'::date + INTERVAL '6 months')::date, true, 1, 7, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (2, 'MAND-0002', 'expired', '2025-03-10'::date, ('2025-03-10'::date + INTERVAL '6 months')::date, false, 3, 8, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (3, 'MAND-0003', 'completed', '2025-04-05'::date, ('2025-04-05'::date + INTERVAL '6 months')::date, false, 1, 9, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (4, 'MAND-0004', 'expired', '2025-05-20'::date, ('2025-05-20'::date + INTERVAL '6 months')::date, true, 4, 10, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (5, 'MAND-0005', 'completed', '2025-06-18'::date, ('2025-06-18'::date + INTERVAL '6 months')::date, true, 2, 11, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (6, 'MAND-0006', 'expired', '2025-07-22'::date, ('2025-07-22'::date + INTERVAL '6 months')::date, false, 5, 12, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (7, 'MAND-0007', 'expired', '2025-09-01'::date, ('2025-09-01'::date + INTERVAL '6 months')::date, true, 3, 13, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (8, 'MAND-0008', 'canceled', '2025-09-15'::date, ('2025-09-15'::date + INTERVAL '6 months')::date, false, 2, 14, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (9, 'MAND-0009', 'expired', '2025-10-02'::date, ('2025-10-02'::date + INTERVAL '6 months')::date, true, 6, 15, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (10, 'MAND-0010', 'expired', '2025-11-14'::date, ('2025-11-14'::date + INTERVAL '6 months')::date, false, 5, 16, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (11, 'MAND-0011', 'expired', '2026-01-05'::date, ('2026-01-05'::date + INTERVAL '6 months')::date, true, 1, 17, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (12, 'MAND-0012', 'expired', '2026-01-20'::date, ('2026-01-20'::date + INTERVAL '6 months')::date, false, 4, 18, 12) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (13, 'MAND-0013', 'active', '2026-02-10'::date, ('2026-02-10'::date + INTERVAL '6 months')::date, false, 2, 19, 13) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (14, 'MAND-0014', 'active', '2026-03-01'::date, ('2026-03-01'::date + INTERVAL '6 months')::date, true, 3, 20, 14) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (15, 'MAND-0015', 'active', '2026-03-25'::date, ('2026-03-25'::date + INTERVAL '6 months')::date, false, 1, 21, 15) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (16, 'MAND-0016', 'canceled', '2026-04-12'::date, ('2026-04-12'::date + INTERVAL '6 months')::date, false, 6, 22, 16) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (17, 'MAND-0017', 'active', '2026-05-28'::date, ('2026-05-28'::date + INTERVAL '6 months')::date, true, 5, 23, 17) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (18, 'MAND-0018', 'active', '2026-07-01'::date, ('2026-07-01'::date + INTERVAL '6 months')::date, true, 2, 24, 18) ON CONFLICT (id) DO NOTHING;

-- 7. RESYNCHRO SÉQUENCES (indispensable après OVERRIDING SYSTEM VALUE)
SELECT setval(pg_get_serial_sequence('role', 'id'), COALESCE((SELECT MAX(id) FROM role), 0));
SELECT setval(pg_get_serial_sequence('"user"', 'id'), COALESCE((SELECT MAX(id) FROM "user"), 0));
SELECT setval(pg_get_serial_sequence('search_request', 'id'), COALESCE((SELECT MAX(id) FROM search_request), 0));
SELECT setval(pg_get_serial_sequence('mandate', 'id'), COALESCE((SELECT MAX(id) FROM mandate), 0));
SELECT setval(pg_get_serial_sequence('criteria', 'id'), COALESCE((SELECT MAX(id) FROM criteria), 0));
-- Pas de setval pour client/hunter : leur clé primaire (id_user) vient de user.id,
-- ce ne sont pas des colonnes IDENTITY avec leur propre séquence.

-- 8. VERIF
SELECT 'user' as tbl, COUNT(*) FROM "user" UNION ALL SELECT 'hunter', COUNT(*) FROM hunter UNION ALL SELECT 'client', COUNT(*) FROM client UNION ALL SELECT 'real_estate_manager', COUNT(*) FROM real_estate_manager UNION ALL SELECT 'search_request', COUNT(*) FROM search_request UNION ALL SELECT 'criteria', COUNT(*) FROM criteria UNION ALL SELECT 'mandate', COUNT(*) FROM mandate;

-- ----------------------------------------------------------------------------
-- 9. STATUT DES DEMANDES — déduit de l'existence d'un mandat (Q-MIG-03,
-- tranché à LOT10) : une demande sous mandat signé est « lancée ». Les 18
-- demandes en ont un. Pas de nouvel état pour une recherche finie (Jeff,
-- Q-JEF-13).
-- ----------------------------------------------------------------------------
UPDATE search_request sr SET status = 'launched'
 WHERE status = 'confirmed'
   AND EXISTS (SELECT 1 FROM mandate m WHERE m.id_search_request = sr.id);

COMMIT;
