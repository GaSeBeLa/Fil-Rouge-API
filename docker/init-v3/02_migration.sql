-- ============================================================================
-- 02_migration.sql — Migration Fil_Rouge_Depart -> Fil_Rouge_Immobilier
-- ADAPTÉ au schéma 18 tables (MPD 03) et à la convention EUROS.
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
--      320.0 devient 320000.00. 17 lignes.
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
--      Valeur 'confirmed' (état d'entrée neutre). 17 lignes.
--      ⚠️ HYPOTHÈSE. Voir README point 5 pour l'alternative ('launched'
--      lorsqu'un mandat existe), fournie en UPDATE commenté en fin de script.
--   6. hunter : "id_realestatemanager" est NOT NULL depuis le 2026-09-22
--      (MPD 03 4) et la source n'a AUCUN manager (deux rôles seulement :
--      client, chasseur). Un manager PLACEHOLDER est créé (user 25 + profil)
--      et les 6 chasseurs lui sont rattachés. Compte bloqué par le même
--      mot de passe placeholder que les 24 autres. Voir README §3.6.
--      ⚠️ HYPOTHÈSE de migration : ce manager n'existe pas dans la source.
--      Le seed devra le remplacer par de vrais managers.
--
-- ============================================================================
-- ⚠️ CORRECTION DE CONTRAINTE DU SCHÉMA — À VALIDER PAR LE GROUPE
-- ============================================================================
--
--   Les 18 clients de la source ont une VILLE mais pas d'adresse de rue ni de
--   code postal. La contrainte ck_client_address_all_or_nothing du script 01
--   exige que address, postal_code et town soient TOUS renseignés ou TOUS
--   nuls : elle rejette donc les 18 clients.
--
--   Or connaître la ville d'un client sans son adresse complète est un cas
--   normal. La règle juste est l'implication dans UN SEUL SENS : une adresse
--   de rue n'a de sens qu'accompagnée d'un code postal et d'une ville ;
--   l'inverse n'est pas vrai.
--
--   L'ALTER ci-dessous applique cette règle. Il est ici, et non dans le 01,
--   pour rester VISIBLE tant que le groupe n'a pas tranché. Une fois validé,
--   le reporter dans 01 et supprimer ces deux lignes.
--
--   Alternative si le groupe préfère garder la contrainte d'origine :
--   commenter l'ALTER et vider town pour les 18 clients — mais c'est une
--   PERTE d'information, alors que la source la fournit.
-- ============================================================================

BEGIN;

ALTER TABLE client DROP CONSTRAINT ck_client_address_all_or_nothing;
ALTER TABLE client ADD CONSTRAINT ck_client_address_all_or_nothing
    CHECK (address IS NULL OR (postal_code IS NOT NULL AND town IS NOT NULL));
-- Source : Fil_Rouge_Depart, Cible : public (ou Fil_Rouge_Immobilier)
SET search_path TO public, "Fil_Rouge_Depart";

-- NOTE secteurs : 10 lignes parsées mais NON MIGRÉES
-- Raison : la table secteurs n'existe plus dans le MPD cible (remplacée par town)
-- Données secteurs source : 10 lignes ignorées volontairement

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
INSERT INTO real_estate_manager (id_user, first_name, last_name, phone_number, gender, country_iso, company_name) VALUES (25, 'Manager', 'Migration', '0000000000', NULL, NULL, NULL) ON CONFLICT (id_user) DO NOTHING;  -- placeholder, pas une personne

-- 2. HUNTERS
-- first_name/last_name/phone_number/gender/country_iso : redescendus depuis "user"
-- company_name = NULL : la source n'a pas cette info, on n'invente pas de nom d'agence
-- is_carteT = NULL    : idem, la 'carte T' (habilitation légale) n'existe pas côté source
-- id_realestatemanager = 25 : le manager placeholder ci-dessus (HYPOTHÈSE, point 6)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carteT, hire_date, id_realestatemanager) VALUES (1, 'Marina', 'Roussel', '+33611223344', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 1), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.50 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carteT, hire_date, id_realestatemanager) VALUES (2, 'Thomas', 'Nguyen', '+33622334455', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 2), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 3.00 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carteT, hire_date, id_realestatemanager) VALUES (3, 'Inès', 'Delacroix', '+33633445566', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 3), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.75 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carteT, hire_date, id_realestatemanager) VALUES (4, 'Marco', 'Baldini', '+33644556677', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 4), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.50 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carteT, hire_date, id_realestatemanager) VALUES (5, 'Awa', 'Kone', '+33655667788', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 5), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 3.25 (voir README, point 3)
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, is_carteT, hire_date, id_realestatemanager) VALUES (6, 'Lucas', 'Perrin', '+33666778899', NULL, 'FR', NULL, NULL, (SELECT created_at::date FROM "user" WHERE id = 6), 25) ON CONFLICT (id_user) DO NOTHING;  -- commission_rate source = 2.00 (voir README, point 3)

-- 3. CLIENTS
-- first_name/last_name/phone_number/gender/country_iso : redescendus depuis "user"
-- phone_number : NOT NULL côté cible ; 3 clients sans tel (Petit, Andre, Lambert)
--                -> placeholder '0000000000', à corriger manuellement si besoin
-- address = NULL : on ne connaît pas la vraie adresse postale, mettre la ville dedans
--                  serait trompeur (ça ressemblerait à une donnée réelle qui ne l'est pas)
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (7, 'Alice', 'Martin', '+33701020304', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (8, 'Karim', 'Benali', '+33702030405', NULL, 'FR', 'Lyon', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (9, 'Chloé', 'Dubois', '+33703040506', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (10, 'Jean', 'Petit', '0000000000', NULL, 'FR', 'Nantes', NULL, NULL) ON CONFLICT (id_user) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (11, 'Lucia', 'Garcia', '+33705060708', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (12, 'Paul', 'Moreau', '+33706070809', NULL, 'FR', 'Castelnau-le-Lez', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (13, 'Emma', 'Lefevre', '+33707080910', NULL, 'FR', 'Lyon', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (14, 'Giulia', 'Rossi', '+33708091011', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (15, 'Hugo', 'Fournier', '+33709101112', NULL, 'FR', 'Sète', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (16, 'Sofia', 'Andre', '0000000000', NULL, 'FR', 'Lattes', NULL, NULL) ON CONFLICT (id_user) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (17, 'Louis', 'Mercier', '+33711121314', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (18, 'Léa', 'Blanc', '+33712131415', NULL, 'FR', 'Nantes', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (19, 'Nina', 'Girard', '+33713141516', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (20, 'Adam', 'Bonnet', '+33714151617', NULL, 'FR', 'Lyon', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (21, 'Zoé', 'Dupont', '+33715161718', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (22, 'Théo', 'Lambert', '0000000000', NULL, 'FR', 'Sète', NULL, NULL) ON CONFLICT (id_user) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (23, 'Manon', 'Roux', '+33717181920', NULL, 'FR', 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, first_name, last_name, phone_number, gender, country_iso, town, address, postal_code) VALUES (24, 'Ethan', 'Faure', '+33718192021', NULL, 'FR', 'Castelnau-le-Lez', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;

-- SKIP mandat 13 INVALIDE (client_id=3 est un chasseur)

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
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (14, '2026-03-01'::date, 20, 20, 3, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (15, '2026-03-25'::date, 21, 21, 1, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (16, '2026-04-12'::date, 22, 22, 6, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (17, '2026-05-28'::date, 23, 23, 5, 'confirmed') ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status) OVERRIDING SYSTEM VALUE VALUES (18, '2026-07-01'::date, 24, 24, 2, 'confirmed') ON CONFLICT (id) DO NOTHING;

-- 5. CRITERIA - id_author = chasseur_id (le chasseur traduit le besoin en critères)
-- budget_min/budget_max : NOT NULL, convertis en K€ (colonne cible NUMERIC(6,1))
-- renovation_budget_min/max : nullable côté cible -> NULL (info absente côté source)
-- typology : NOT NULL, liste fermée -> déduite via parse_typology() ci-dessus
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 1, 320000.00, 320000.00, NULL, NULL, 65, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 320000, 65m2 min, balcon, calme, DPE C max') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 2, 450000.00, 450000.00, NULL, NULL, 85, 'Appartement', 'T4 / F4', 'T4 Croix-Rousse, budget 450000, 85m2, terrasse ou jardin') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 3, 280000.00, 280000.00, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 280000, 45m2 min, lumineux, proche tram') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 4, 390000.00, 390000.00, NULL, NULL, NULL, 'Maison', 'T4 / F4', 'Maison Ile de Nantes, budget 390000, 3 chambres, petit exterieur') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 5, 550000.00, 550000.00, NULL, NULL, 90, 'Appartement', 'T4 / F4', 'T4 Port Marianne, budget 550000, 90m2, parking, ascenseur, vue') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 6, 240000.00, 240000.00, NULL, NULL, 80, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 240000, 80m2, jardin, travaux OK') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 7, 610000.00, 610000.00, NULL, NULL, 100, 'Loft', 'T3 / F3', 'Loft Confluence, budget 610000, 100m2, standing, terrasse') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 8, 300000.00, 300000.00, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson ou Beaux-Arts, budget 300000, charme ancien, poutres') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 9, 260000.00, 260000.00, NULL, NULL, 60, 'Appartement', 'T3 / F3', 'T3 Sete centre, budget 260000, vue mer si possible, 60m2') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 10, 420000.00, 420000.00, NULL, NULL, NULL, 'Villa', 'T4 / F4', 'Villa Lattes, budget 420000, 4 pieces, piscine ou jardin sud') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 11, 350000.00, 350000.00, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Port Marianne, budget 350000, neuf ou recent, balcon, parking') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 12, 480000.00, 480000.00, NULL, NULL, NULL, 'Appartement', 'T4 / F4', 'Appartement Nantes, budget 480000, 4 pieces, dernier etage') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 14, 700000.00, 700000.00, NULL, NULL, 120, 'Appartement', 'T5 / F5', 'T5 Confluence, budget 700000, 120m2, prestations haut de gamme') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 15, 310000.00, 310000.00, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 310000, ancien renove, cave appreciee') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 16, 290000.00, 290000.00, NULL, NULL, NULL, 'Maison', 'T3 / F3', 'Maison Sete, budget 290000, 3 pieces, garage') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 17, 260000.00, 260000.00, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 260000, 45m2, balcon, DPE D max') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 18, 330000.00, 330000.00, NULL, NULL, 90, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 330000, 90m2, 3 chambres, jardin') ON CONFLICT DO NOTHING;

-- 6. MANDATE
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (1, 'MAND-0001', 'completed', '2025-02-01'::date, ('2025-02-01'::date + INTERVAL '6 months')::date, true, true, 1, 7, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (2, 'MAND-0002', 'expired', '2025-03-10'::date, ('2025-03-10'::date + INTERVAL '6 months')::date, false, true, 3, 8, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (3, 'MAND-0003', 'completed', '2025-04-05'::date, ('2025-04-05'::date + INTERVAL '6 months')::date, false, true, 1, 9, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (4, 'MAND-0004', 'active', '2025-05-20'::date, ('2025-05-20'::date + INTERVAL '6 months')::date, true, true, 4, 10, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (5, 'MAND-0005', 'completed', '2025-06-18'::date, ('2025-06-18'::date + INTERVAL '6 months')::date, true, true, 2, 11, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (6, 'MAND-0006', 'expired', '2025-07-22'::date, ('2025-07-22'::date + INTERVAL '6 months')::date, false, true, 5, 12, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (7, 'MAND-0007', 'active', '2025-09-01'::date, ('2025-09-01'::date + INTERVAL '6 months')::date, true, true, 3, 13, 7) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (8, 'MAND-0008', 'canceled', '2025-09-15'::date, ('2025-09-15'::date + INTERVAL '6 months')::date, false, false, 2, 14, 8) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (9, 'MAND-0009', 'active', '2025-10-02'::date, ('2025-10-02'::date + INTERVAL '6 months')::date, true, true, 6, 15, 9) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (10, 'MAND-0010', 'active', '2025-11-14'::date, ('2025-11-14'::date + INTERVAL '6 months')::date, false, true, 5, 16, 10) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (11, 'MAND-0011', 'active', '2026-01-05'::date, ('2026-01-05'::date + INTERVAL '6 months')::date, true, true, 1, 17, 11) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (12, 'MAND-0012', 'active', '2026-01-20'::date, ('2026-01-20'::date + INTERVAL '6 months')::date, false, true, 4, 18, 12) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (14, 'MAND-0014', 'active', '2026-03-01'::date, ('2026-03-01'::date + INTERVAL '6 months')::date, true, true, 3, 20, 14) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (15, 'MAND-0015', 'active', '2026-03-25'::date, ('2026-03-25'::date + INTERVAL '6 months')::date, false, true, 1, 21, 15) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (16, 'MAND-0016', 'canceled', '2026-04-12'::date, ('2026-04-12'::date + INTERVAL '6 months')::date, false, false, 6, 22, 16) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (17, 'MAND-0017', 'active', '2026-05-28'::date, ('2026-05-28'::date + INTERVAL '6 months')::date, true, true, 5, 23, 17) ON CONFLICT (id) DO NOTHING;
INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive, is_client_signed, id_hunter, id_client, id_search_request) OVERRIDING SYSTEM VALUE VALUES (18, 'MAND-0018', 'active', '2026-07-01'::date, ('2026-07-01'::date + INTERVAL '6 months')::date, true, true, 2, 24, 18) ON CONFLICT (id) DO NOTHING;

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
-- OPTION (point 5 du README) — statut déduit de l'existence d'un mandat.
-- Décommenter si le groupe juge qu'une demande sous mandat est « lancée ».
-- ----------------------------------------------------------------------------
-- UPDATE search_request sr SET status = 'launched'
--  WHERE EXISTS (SELECT 1 FROM mandate m WHERE m.id_search_request = sr.id);

COMMIT;
