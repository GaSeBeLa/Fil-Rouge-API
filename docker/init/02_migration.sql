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

-- 1. USERS
-- password  : NOT NULL côté cible, absent côté source -> placeholder explicite qui
--             empêche toute connexion tant que le mot de passe n'a pas été réinitialisé
-- phone_number : NOT NULL côté cible ; 3 clients sans tel (Petit, Andre, Lambert)
--                -> placeholder '0000000000', à corriger manuellement si besoin
-- phone_number : convertis au format international (+33) — le 0 initial du
--                numéro local français est retiré et remplacé par +33
-- country_iso : source 100% française (villes du dataset : Montpellier,
--               Nantes, Lyon...) -> 'FR' pour tout le monde, par déduction
--               documentée (aucune donnée de pays explicite côté source)
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (1, 'Marina', 'Roussel', 'm.roussel@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33611223344', NULL, 'FR', '2023-03-15'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (2, 'Thomas', 'Nguyen', 't.nguyen@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33622334455', NULL, 'FR', '2023-06-01'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (3, 'Inès', 'Delacroix', 'i.delacroix@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33633445566', NULL, 'FR', '2024-01-10'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (4, 'Marco', 'Baldini', 'm.baldini@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33644556677', NULL, 'FR', '2024-09-22'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (5, 'Awa', 'Kone', 'a.kone@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33655667788', NULL, 'FR', '2025-02-14'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (6, 'Lucas', 'Perrin', 'l.perrin@chassimmo.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33666778899', NULL, 'FR', '2025-11-03'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (7, 'Alice', 'Martin', 'alice.martin@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33701020304', NULL, 'FR', '2025-01-08'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (8, 'Karim', 'Benali', 'karim.benali@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33702030405', NULL, 'FR', '2025-02-19'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (9, 'Chloé', 'Dubois', 'chloe.dubois@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33703040506', NULL, 'FR', '2025-03-02'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (10, 'Jean', 'Petit', 'jean.petit@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '0000000000', NULL, 'FR', '2025-03-27'::date) ON CONFLICT (id) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (11, 'Lucia', 'Garcia', 'lucia.garcia@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33705060708', NULL, 'FR', '2025-04-11'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (12, 'Paul', 'Moreau', 'paul.moreau@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33706070809', NULL, 'FR', '2025-05-30'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (13, 'Emma', 'Lefevre', 'emma.lefevre@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33707080910', NULL, 'FR', '2025-06-15'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (14, 'Giulia', 'Rossi', 'giulia.rossi@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33708091011', NULL, 'FR', '2025-07-04'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (15, 'Hugo', 'Fournier', 'hugo.fournier@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33709101112', NULL, 'FR', '2025-08-21'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (16, 'Sofia', 'Andre', 'sofia.andre@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '0000000000', NULL, 'FR', '2025-09-09'::date) ON CONFLICT (id) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (17, 'Louis', 'Mercier', 'louis.mercier@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33711121314', NULL, 'FR', '2025-10-17'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (18, 'Léa', 'Blanc', 'lea.blanc@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33712131415', NULL, 'FR', '2025-11-25'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (19, 'Nina', 'Girard', 'nina.girard@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33713141516', NULL, 'FR', '2025-12-12'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (20, 'Adam', 'Bonnet', 'adam.bonnet@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33714151617', NULL, 'FR', '2026-01-06'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (21, 'Zoé', 'Dupont', 'zoe.dupont@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33715161718', NULL, 'FR', '2026-02-20'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (22, 'Théo', 'Lambert', 'theo.lambert@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '0000000000', NULL, 'FR', '2026-03-30'::date) ON CONFLICT (id) DO NOTHING; -- tel manquant source, placeholder
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (23, 'Manon', 'Roux', 'manon.roux@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33717181920', NULL, 'FR', '2026-05-15'::date) ON CONFLICT (id) DO NOTHING;
INSERT INTO "user" (id, first_name, last_name, email, password, phone_number, gender, country_iso, created_at) OVERRIDING SYSTEM VALUE VALUES (24, 'Ethan', 'Faure', 'ethan.faure@mail.fr', '$2b$12$MIGRATED_PLACEHOLDER_MUST_RESET', '+33718192021', NULL, 'FR', '2026-06-28'::date) ON CONFLICT (id) DO NOTHING;

-- 2. HUNTERS
-- company_name = NULL : la source n'a pas cette info, on n'invente pas de nom d'agence
-- is_carteT = NULL    : idem, la 'carte T' (habilitation légale) n'existe pas côté source
INSERT INTO hunter (id_user, company_name, commission_rate, is_carteT) VALUES (1, NULL, 2.50, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, company_name, commission_rate, is_carteT) VALUES (2, NULL, 3.00, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, company_name, commission_rate, is_carteT) VALUES (3, NULL, 2.75, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, company_name, commission_rate, is_carteT) VALUES (4, NULL, 2.50, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, company_name, commission_rate, is_carteT) VALUES (5, NULL, 3.25, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO hunter (id_user, company_name, commission_rate, is_carteT) VALUES (6, NULL, 2.00, NULL) ON CONFLICT (id_user) DO NOTHING;

-- 3. CLIENTS
-- address = NULL : on ne connaît pas la vraie adresse postale, mettre la ville dedans
--                  serait trompeur (ça ressemblerait à une donnée réelle qui ne l'est pas)
INSERT INTO client (id_user, town, address, postal_code) VALUES (7, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (8, 'Lyon', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (9, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (10, 'Nantes', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (11, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (12, 'Castelnau-le-Lez', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (13, 'Lyon', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (14, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (15, 'Sète', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (16, 'Lattes', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (17, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (18, 'Nantes', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (19, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (20, 'Lyon', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (21, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (22, 'Sète', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (23, 'Montpellier', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;
INSERT INTO client (id_user, town, address, postal_code) VALUES (24, 'Castelnau-le-Lez', NULL, NULL) ON CONFLICT (id_user) DO NOTHING;

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
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 1, 320.0, 320.0, NULL, NULL, 65, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 320000, 65m2 min, balcon, calme, DPE C max') ON CONFLICT DO NOTHING; -- typology=T3 / F3 (T3 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=320.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 2, 450.0, 450.0, NULL, NULL, 85, 'Appartement', 'T4 / F4', 'T4 Croix-Rousse, budget 450000, 85m2, terrasse ou jardin') ON CONFLICT DO NOTHING; -- typology=T4 / F4 (T4 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=450.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 3, 280.0, 280.0, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 280000, 45m2 min, lumineux, proche tram') ON CONFLICT DO NOTHING; -- typology=T2 / F2 (T2 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=280.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 4, 390.0, 390.0, NULL, NULL, NULL, 'Maison', 'T4 / F4', 'Maison Ile de Nantes, budget 390000, 3 chambres, petit exterieur') ON CONFLICT DO NOTHING; -- typology=T4 / F4 (3 chambres -> T4 (hypothèse chambres+1)), renovation_budget=NULL (source n'a pas l'info), budget=390.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 5, 550.0, 550.0, NULL, NULL, 90, 'Appartement', 'T4 / F4', 'T4 Port Marianne, budget 550000, 90m2, parking, ascenseur, vue') ON CONFLICT DO NOTHING; -- typology=T4 / F4 (T4 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=550.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 6, 240.0, 240.0, NULL, NULL, 80, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 240000, 80m2, jardin, travaux OK') ON CONFLICT DO NOTHING; -- typology=T4 / F4 (Maison/Villa sans T ni pieces/chambres -> hypothèse T4 familial), renovation_budget=NULL (source n'a pas l'info), budget=240.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 7, 610.0, 610.0, NULL, NULL, 100, 'Loft', 'T3 / F3', 'Loft Confluence, budget 610000, 100m2, standing, terrasse') ON CONFLICT DO NOTHING; -- typology=T3 / F3 (Aucune info T/chambres/pieces -> hypothèse T3 par défaut), renovation_budget=NULL (source n'a pas l'info), budget=610.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 8, 300.0, 300.0, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson ou Beaux-Arts, budget 300000, charme ancien, poutres') ON CONFLICT DO NOTHING; -- typology=T3 / F3 (T3 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=300.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 9, 260.0, 260.0, NULL, NULL, 60, 'Appartement', 'T3 / F3', 'T3 Sete centre, budget 260000, vue mer si possible, 60m2') ON CONFLICT DO NOTHING; -- typology=T3 / F3 (T3 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=260.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 10, 420.0, 420.0, NULL, NULL, NULL, 'Villa', 'T4 / F4', 'Villa Lattes, budget 420000, 4 pieces, piscine ou jardin sud') ON CONFLICT DO NOTHING; -- typology=T4 / F4 (4 pieces -> T4 (hypothèse)), renovation_budget=NULL (source n'a pas l'info), budget=420.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 11, 350.0, 350.0, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Port Marianne, budget 350000, neuf ou recent, balcon, parking') ON CONFLICT DO NOTHING; -- typology=T3 / F3 (T3 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=350.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (4, 12, 480.0, 480.0, NULL, NULL, NULL, 'Appartement', 'T4 / F4', 'Appartement Nantes, budget 480000, 4 pieces, dernier etage') ON CONFLICT DO NOTHING; -- typology=T4 / F4 (4 pieces -> T4 (hypothèse)), renovation_budget=NULL (source n'a pas l'info), budget=480.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (3, 14, 700.0, 700.0, NULL, NULL, 120, 'Appartement', 'T5 / F5', 'T5 Confluence, budget 700000, 120m2, prestations haut de gamme') ON CONFLICT DO NOTHING; -- typology=T5 / F5 (T5 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=700.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (1, 15, 310.0, 310.0, NULL, NULL, NULL, 'Appartement', 'T3 / F3', 'T3 Ecusson, budget 310000, ancien renove, cave appreciee') ON CONFLICT DO NOTHING; -- typology=T3 / F3 (T3 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=310.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (6, 16, 290.0, 290.0, NULL, NULL, NULL, 'Maison', 'T3 / F3', 'Maison Sete, budget 290000, 3 pieces, garage') ON CONFLICT DO NOTHING; -- typology=T3 / F3 (3 pieces -> T3 (hypothèse)), renovation_budget=NULL (source n'a pas l'info), budget=290.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (5, 17, 260.0, 260.0, NULL, NULL, 45, 'Appartement', 'T2 / F2', 'T2 Beaux-Arts, budget 260000, 45m2, balcon, DPE D max') ON CONFLICT DO NOTHING; -- typology=T2 / F2 (T2 trouvé dans description), renovation_budget=NULL (source n'a pas l'info), budget=260.0 K€ (source: description du mandat)
INSERT INTO criteria (id_author, id_search_request, budget_min, budget_max, renovation_budget_min, renovation_budget_max, surface_min, estate_type, typology, change_reason) VALUES (2, 18, 330.0, 330.0, NULL, NULL, 90, 'Maison', 'T4 / F4', 'Maison Castelnau, budget 330000, 90m2, 3 chambres, jardin') ON CONFLICT DO NOTHING; -- typology=T4 / F4 (3 chambres -> T4 (hypothèse chambres+1)), renovation_budget=NULL (source n'a pas l'info), budget=330.0 K€ (source: description du mandat)

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
SELECT setval(pg_get_serial_sequence('"user"', 'id'), COALESCE((SELECT MAX(id) FROM "user"), 0));
SELECT setval(pg_get_serial_sequence('search_request', 'id'), COALESCE((SELECT MAX(id) FROM search_request), 0));
SELECT setval(pg_get_serial_sequence('mandate', 'id'), COALESCE((SELECT MAX(id) FROM mandate), 0));
SELECT setval(pg_get_serial_sequence('criteria', 'id'), COALESCE((SELECT MAX(id) FROM criteria), 0));
-- Pas de setval pour client/hunter : leur clé primaire (id_user) vient de user.id,
-- ce ne sont pas des colonnes IDENTITY avec leur propre séquence.

-- 8. VERIF
SELECT 'user' as tbl, COUNT(*) FROM "user" UNION ALL SELECT 'hunter', COUNT(*) FROM hunter UNION ALL SELECT 'client', COUNT(*) FROM client UNION ALL SELECT 'search_request', COUNT(*) FROM search_request UNION ALL SELECT 'criteria', COUNT(*) FROM criteria UNION ALL SELECT 'mandate', COUNT(*) FROM mandate;
COMMIT;