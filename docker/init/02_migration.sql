-- ============================================================
-- migration_tabularis.sql
-- Migration Fil_Rouge_Depart -> Fil_Rouge_Immobilier
-- ============================================================
BEGIN;
-- Source : Fil_Rouge_Depart, Cible : public (ou Fil_Rouge_Immobilier)
SET search_path TO public, "Fil_Rouge_Depart";

-- NOTE secteurs : 10 lignes parsées mais NON MIGRÉES
-- Raison : la table secteurs n'existe plus dans le MPD cible (remplacée par town)
-- Données secteurs source : 10 lignes ignorées volontairement

-- Gender : NULL autorisé par défaut en Postgres (un CHECK ne rejette jamais NULL)

-- 0. ROLE
-- Table de référence des rôles (choix du groupe, 2026-09). id_role dans "user"
-- pointe ici : 1=client, 2=hunter, 3=real_estate_manager.
INSERT INTO role (id, libelle) OVERRIDING SYSTEM VALUE VALUES (1, 'client') ON CONFLICT (id) DO NOTHING;
INSERT INTO role (id, libelle) OVERRIDING SYSTEM VALUE VALUES (2, 'hunter') ON CONFLICT (id) DO NOTHING;
INSERT INTO role (id, libelle) OVERRIDING SYSTEM VALUE VALUES (3, 'real_estate_manager') ON CONFLICT (id) DO NOTHING;

-- 1. USERS
-- "user" est désormais minimaliste (choix du groupe, 2026-09) : id, email,
-- password, id_role, created_at. first_name/last_name/phone_number/gender/
-- country_iso sont migrés directement dans hunter/client ci-dessous.
-- password  : NOT NULL côté cible, absent côté source -> placeholder explicite qui
--             empêche toute connexion tant que le mot de passe n'a pas été réinitialisé
-- id_role   : 1-6 = hunters (id_role=2), 7-24 = clients (id_role=1)
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

-- 2. HUNTERS
-- first_name/last_name/phone_number/gender/country_iso : redescendus depuis "user"
-- company_name = NULL : la source n'a pas cette info, on n'invente pas de nom d'agence
-- is_carteT = NULL    : idem, la 'carte T' (habilitation légale) n'existe pas côté source
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, commission_rate, is_carteT) VALUES (1, 'Marina', 'Roussel', '+33611223344', NULL, 'FR', NULL, 2.50, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, commission_rate, is_carteT) VALUES (2, 'Thomas', 'Nguyen', '+33622334455', NULL, 'FR', NULL, 3.00, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, commission_rate, is_carteT) VALUES (3, 'Inès', 'Delacroix', '+33633445566', NULL, 'FR', NULL, 2.75, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, commission_rate, is_carteT) VALUES (4, 'Marco', 'Baldini', '+33644556677', NULL, 'FR', NULL, 2.50, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, commission_rate, is_carteT) VALUES (5, 'Awa', 'Kone', '+33655667788', NULL, 'FR', NULL, 3.25, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, first_name, last_name, phone_number, gender, country_iso, company_name, commission_rate, is_carteT) VALUES (6, 'Lucas', 'Perrin', '+33666778899', NULL, 'FR', NULL, 2.00, NULL) ON CONFLICT (id_user) DO NOTHING;

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
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (1, '2025-02-01'::date, 7, 7, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (2, '2025-03-10'::date, 8, 8, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (3, '2025-04-05'::date, 9, 9, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (4, '2025-05-20'::date, 10, 10, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (5, '2025-06-18'::date, 11, 11, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (6, '2025-07-22'::date, 12, 12, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (7, '2025-09-01'::date, 13, 13, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (8, '2025-09-15'::date, 14, 14, 2) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (9, '2025-10-02'::date, 15, 15, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (10, '2025-11-14'::date, 16, 16, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (11, '2026-01-05'::date, 17, 17, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (12, '2026-01-20'::date, 18, 18, 4) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (14, '2026-03-01'::date, 20, 20, 3) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (15, '2026-03-25'::date, 21, 21, 1) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (16, '2026-04-12'::date, 22, 22, 6) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (17, '2026-05-28'::date, 23, 23, 5) ON CONFLICT (id) DO NOTHING;
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter) OVERRIDING SYSTEM VALUE VALUES (18, '2026-07-01'::date, 24, 24, 2) ON CONFLICT (id) DO NOTHING;

-- 5. CRITERIA - id_author = chasseur_id (le chasseur traduit le besoin en critères)
-- budget_min/budget_max : NOT NULL, convertis en K€ (colonne cible NUMERIC(6,1))
-- renovation_budget_min/max : nullable côté cible -> NULL (info absente côté source)
-- typology : NOT NULL, liste fermée -> déduite via parse_typology() ci-dessus
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 1, 320.0, 320.0, NULL, NULL, 65, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 320000, 65m2 min, balcon, calme, DPE C max') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 2, 450.0, 450.0, NULL, NULL, 85, 'Appartement', 'T4 / F4', 'T4 Croix-Rousse, budget 450000, 85m2, terrasse ou jardin') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 3, 280.0, 280.0, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 280000, 45m2 min, lumineux, proche tram') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 4, 390.0, 390.0, NULL, NULL, NULL, 'Maison', 'T4 / F4', 'Maison Ile de Nantes, budget 390000, 3 chambres, petit exterieur') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 5, 550.0, 550.0, NULL, NULL, 90, 'Appartement', 'T4 / F4', 'T4 Port Marianne, budget 550000, 90m2, parking, ascenseur, vue') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 6, 240.0, 240.0, NULL, NULL, 80, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 240000, 80m2, jardin, travaux OK') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 7, 610.0, 610.0, NULL, NULL, 100, 'Loft', 'T3 / F3', 'Loft Confluence, budget 610000, 100m2, standing, terrasse') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 8, 300.0, 300.0, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson ou Beaux-Arts, budget 300000, charme ancien, poutres') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 9, 260.0, 260.0, NULL, NULL, 60, 'Appartement', 'T3 / F3', 'T3 Sete centre, budget 260000, vue mer si possible, 60m2') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 10, 420.0, 420.0, NULL, NULL, NULL, 'Villa', 'T4 / F4', 'Villa Lattes, budget 420000, 4 pieces, piscine ou jardin sud') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 11, 350.0, 350.0, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Port Marianne, budget 350000, neuf ou recent, balcon, parking') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 12, 480.0, 480.0, NULL, NULL, NULL, 'Appartement', 'T4 / F4', 'Appartement Nantes, budget 480000, 4 pieces, dernier etage') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 14, 700.0, 700.0, NULL, NULL, 120, 'Appartement', 'T5 / F5', 'T5 Confluence, budget 700000, 120m2, prestations haut de gamme') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 15, 310.0, 310.0, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 310000, ancien renove, cave appreciee') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 16, 290.0, 290.0, NULL, NULL, NULL, 'Maison', 'T3 / F3', 'Maison Sete, budget 290000, 3 pieces, garage') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 17, 260.0, 260.0, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 260000, 45m2, balcon, DPE D max') ON CONFLICT DO NOTHING;
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 18, 330.0, 330.0, NULL, NULL, 90, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 330000, 90m2, 3 chambres, jardin') ON CONFLICT DO NOTHING;

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
SELECT 'user' as tbl, COUNT(*) FROM "user" UNION ALL SELECT 'hunter', COUNT(*) FROM hunter UNION ALL SELECT 'client', COUNT(*) FROM client UNION ALL SELECT 'search_request', COUNT(*) FROM search_request UNION ALL SELECT 'criteria', COUNT(*) FROM criteria UNION ALL SELECT 'mandate', COUNT(*) FROM mandate;
COMMIT;
