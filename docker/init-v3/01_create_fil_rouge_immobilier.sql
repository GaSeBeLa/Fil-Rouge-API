-- ============================================================================
-- 01_create_fil_rouge_immobilier.sql
-- Schéma cible "Fil_Rouge_Immobilier" — 19 tables
-- Généré depuis « MPD 03 4.drawio.xml » (2026-09-22) ; 19e table,
-- remuneration_parameters, ajoutée le 2026-10-07 (LOT6, Q-REM-05),
-- renommée hunter_rate_parameters le 2026-10-08 (G2)
--
-- VERSION FUSIONNÉE des deux scripts écrits en parallèle par le groupe.
-- Testé sur PostgreSQL 16 : création complète sur base vierge, sans erreur.
-- ============================================================================
--
-- ============================================================================
-- NOUVEAU LE 2026-09-22 — CHAQUE CHASSEUR A UN MANAGER
-- ============================================================================
--
--   hunter.id_realestatemanager, NOT NULL, FK vers real_estate_manager(id_user).
--   Relation Hunter (1,1) — RealEstateManager (0,n), libellée « Manages ».
--
--   D'OÙ ÇA VIENT : le sujet parle du « manager » d'un chasseur dans l'exemple
--   ENF-03 du CAHIER-DES-CHARGES-TECHNIQUE.md (l. 97) et dans
--   REGLES-CALCUL-REMUNERATION.md (l. 296, 763) : « accès limité au chasseur
--   concerné et à son manager ». ⚠️ C'est un EXEMPLE dans un modèle de
--   document, pas une exigence du client ; les .feature ne citent jamais de
--   manager, et les fixtures n'ont que deux rôles (client, chasseur).
--   C'est donc un CHOIX DU GROUPE, cohérent avec le rôle Manager déjà en base.
--   À acter en ADR sur Confluence.
--
--   CONSÉQUENCES :
--     - real_estate_manager est créée AVANT hunter (dépendance de FK).
--     - 02_migration.sql crée un manager placeholder pour les 6 chasseurs
--       migrés, car la source n'en a aucun (README §3.6).
--     - Base déjà créée : docker/migrations/2026-09-22_hunter_manager.sql.
--
--   À NOTER : search_request.id_realestatemanager (le manager qui traite la
--   demande) et hunter.id_realestatemanager (le manager du chasseur) sont deux
--   liens différents. Rien n'impose qu'ils coïncident sur une même demande.
-- ============================================================================
--
-- ============================================================================
-- CORRECTIONS DE DIAGRAMME (erreurs de saisie, pas des choix de modélisation)
-- À reporter dans le drawio pour que les deux restent alignés.
-- ============================================================================
--
--   1. criteria.chk_postal_code_format : une parenthèse fermante en trop
--      ("END))" -> "END)") ; sans cela le script ne s'exécute pas.
--   2. estate_proposed.chk_offer : la contrainte figure DEUX fois dans le
--      diagramme, sous le même nom. PostgreSQL refuse. Une seule est créée.
--   3. estate_searchrequest : colonne "id :" (deux-points parasite) -> "id" ;
--      virgule manquante entre chk_media et uq_estate_search.
--   4. mandate : virgule manquante entre chk_renewed et chk_status_signature.
--   5. Extension btree_gist absente du diagramme : sans elle, les contraintes
--      EXCLUDE qui mélangent « id_hunter WITH = » et une plage ne se créent pas.
--   6. criteria : le couple bathrooms_min/max était le seul des onze couples
--      min/max sans CHECK d'ordre. Omission comblée (chk_bathrooms).
--   7. search_request.status : VARCHAR(9) collait à 'confirmed' au caractère
--      près. Porté à VARCHAR(20), comme tous les autres statuts du schéma.
--   8. Code postal irlandais : client exigeait un ESPACE ("D02 X285"),
--      criteria l'interdisait ("D02X285"). Les deux tables décrivaient donc
--      le même pays de deux façons incompatibles. ✏️ HARMONISÉ SANS ESPACE
--      le 2026-10-07 (Q-SCH-12, confirmé par Jeff ; LOT8), sur client,
--      criteria et estate. GB et NL gardent leur espace.
--   9. criteria.budget_max : « NUMERIC (12.2) » dans MPD 03 4 (un point au
--      lieu d'une virgule). Lu comme INTEGER, comme tous les prix et budgets.
--
-- ============================================================================
-- ⚠️ CONVENTION D'UNITÉ MONÉTAIRE — CHANGEMENT MAJEUR, À LIRE EN ENTIER
-- ============================================================================
--
--   TOUS les montants sont en EUROS. Deux types (Q-REM-01, 2026-10-05) :
--     - INTEGER (euros entiers) : prix, budgets, bornes du barème, part fixe ;
--     - NUMERIC(12,2) (au centime) : honoraires sale.fees_amount et
--       rémunération payment.amount — le sujet impose l'arrondi au centime
--       (10_calcul_remuneration_chasseur.feature, l. 253 ; remuneration.py:188).
--   La convention « milliers d'euros » (K€, NUMERIC(6,1)) des versions
--   précédentes est ABANDONNÉE. Un bien à 354 700 € se stocke 354700.
--
--   POURQUOI — trois mesures sur les sources officielles, pas un avis :
--
--   1. NUMERIC(6,1) plafonne à 99 999,9. Or les fixtures officielles
--      (StarterPack/fixtures/PgSQL.sql) contiennent 37 valeurs sur 47
--      au-dessus de ce plafond, jusqu'à 700 000. La base refusait donc le
--      chargement des fixtures fournies (numeric field overflow).
--
--   2. Le barème officiel (user-stories/10_calcul_remuneration_chasseur.feature,
--      l. 22-27) a des bornes à l'EURO PRÈS :
--          0      -> 199999 : 30 %      500000 -> 749999 : 45 %
--          200000 -> 349999 : 35 %      750000 ->        : 50 %
--          350000 -> 499999 : 40 %
--      En K€ au dixième, 199999 € devient 199,999 -> arrondi 200,0 -> le bien
--      bascule à 35 % au lieu de 30 %. Le barème était faussé à chaque borne.
--      Vérifié après correction : 199999 donne bien 30 %, 200000 donne 35 %.
--
--   3. La règle de rémunération impose l'arrondi AU CENTIME (même fichier,
--      l. 253). Le dixième de K€ (= 100 €) l'interdisait.
--
--   Cette mesure tranche la décision D1 en faveur de l'EURO. La décision B
--   (K€) actée le 11/09/26 et marquée « à reconfirmer » est RÉFUTÉE par les
--   sources officielles.
--
--   CHARGEMENT DES DONNÉES — aucune conversion approximative n'est nécessaire :
--   normalised/annonces_normalised.csv porte déjà les deux colonnes,
--   « price » (K€, 62.5 -> 406.0) et « price_eur » (euros, 62495 -> 406042).
--   Le script de peuplement doit lire « price_eur ».
--   (Au passage : 62 495 € était stocké 62.5, soit 62 500 € — 5 € perdus.)
--
-- ============================================================================
-- CLÉS DES SOUS-TYPES — id ET id_user, LES DEUX (ne pas « simplifier »)
-- ============================================================================
--
--   client, hunter et real_estate_manager portent DEUX clés :
--     - id       : PK technique, GENERATED ALWAYS AS IDENTITY
--     - id_user  : FK vers "user", NOT NULL UNIQUE (relation 1-1)
--
--   CONTRAINTE PÉDAGOGIQUE IMPOSÉE : garder un identifiant technique propre à
--   chaque entité pour qu'une migration vers MongoDB reste possible. Ce n'est
--   pas une PK morte à retirer.
--
--   Les FK des autres tables pointent vers id_user, jamais vers id. Le nom de
--   colonne (id_client, id_hunter) est conservé tel quel pour rester aligné
--   sur le drawio, sur l'ancien script et sur les tests du groupe ; ce qu'il
--   contient réellement est documenté par COMMENT ON COLUMN en fin de script.
--
-- ============================================================================
-- CE QUI N'EST PAS ENCORE PROTÉGÉ — mesuré, pas supposé
-- ============================================================================
--
--   Le jeu de tests adverses écrit à partir des .feature donne, sur ce schéma :
--       2 réussites / 14 lacunes / 1 à trancher  (17 tests)
--   En activant les deux TODO de mandate (six mois + exclusivité) :
--       5 réussites / 11 lacunes / 1 à trancher
--   ✏️ Ces deux règles sont actives depuis le 2026-10-07 (LOT4, Q-MAN-01,
--   Q-MAN-02) ; le jeu de tests adverses n'a pas été rejoué depuis.
--
--   Autrement dit : un schéma seul ne protège PAS la plupart des règles
--   métier. Elles croisent plusieurs tables et demandent des triggers ou
--   l'API. Les TODO ci-dessous portent le SQL prêt à activer.
--
--   Décisions encore ouvertes : D2 (ancienneté). N2 (localisation) est
--   fermée le 2026-10-05 : elle reste sur criteria, un ADR remplace
--   ADR-009 (Q-SCH-02) ; les secteurs d'origine y arrivent, avec un
--   quartier facultatif (LOT8, Q-MIG-08). R21 (bornage du taux final 20-60 %)
--   est actif depuis le 2026-10-07 (LOT5, Q-REM-19, Jeff : Q-JEF-01).
--   D9 (deux scores le même jour) est fermée le 2026-10-07 : hunter_performance
--   devient un journal daté à la seconde (LOT6, Q-SCH-06). D6 (priorité du
--   client) est fermée le 2026-10-07 : estate_proposed.client_priority, de 1
--   à 5 (LOT7, Q-SCH-05, Jeff : Q-JEF-18).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;  -- requis par les contraintes EXCLUDE

BEGIN;


-- ============================================================================
-- 1. IDENTITÉ ET RÔLES
-- ============================================================================

CREATE TABLE role (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),  -- Q-SCH-09
    -- 'Reader' : lecture seule côté application (Q14, LOT12, accord de Jeff
    -- le 2026-10-07) ; son pendant PostgreSQL est dans 04_role-lecture-seule.sql.
    wording    VARCHAR(20) NOT NULL UNIQUE
            CHECK (wording IN ('Admin', 'Client', 'Hunter', 'Manager', 'Reader'))
);

-- "user" est un mot réservé PostgreSQL : il reste quoté partout.
CREATE TABLE "user" (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    email        VARCHAR(150) NOT NULL UNIQUE,
    password     VARCHAR(255) NOT NULL,
    is_activated BOOLEAN NOT NULL DEFAULT FALSE,
    id_role      INTEGER NOT NULL REFERENCES role(id) ON DELETE RESTRICT
);


-- ============================================================================
-- 2. SOUS-TYPES D'UTILISATEUR
-- ============================================================================
-- created_at sur client, hunter, real_estate_manager et role, comme sur les
-- autres tables (Q-SCH-09, 2026-10-07, LOT7).
--
-- TÉLÉPHONE (ADR-007, Q-PRO-08 ; LOT7) : un seul champ international,
-- indicatif compris (ex. +33612345678). ADR-007 demande une « regex E.164
-- souple » : un « + », puis 2 à 15 chiffres (borne E.164), le premier de 1
-- à 9, avec au plus un espace ou un tiret entre deux chiffres — les
-- « espaces, tirets » qu'ADR-007 veut tolérer. Le format national
-- 0612345678 est refusé. Les 4 numéros manquants de la reprise valent
-- +33000000000, accepté ici (Q-MIG-07, README §0).

CREATE TABLE client (
    id                       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at               TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),  -- Q-SCH-09
    id_user                  INTEGER NOT NULL UNIQUE
                             REFERENCES "user"(id) ON DELETE RESTRICT,
    first_name               VARCHAR(80) NOT NULL
                             CHECK (first_name = btrim(first_name) AND first_name <> ''),
    last_name                VARCHAR(80) NOT NULL
                             CHECK (last_name = btrim(last_name) AND last_name <> ''),
    country_iso              CHAR(2)
                             CHECK (country_iso IN ('FR','ES','DE','GB','IE','BE','NL','LU','IT','CH')),
    gender                   VARCHAR(10)
                             CHECK (gender IN ('male', 'female', 'other')),
    phone_number             VARCHAR(20) NOT NULL
                             CHECK (phone_number = btrim(phone_number) AND phone_number <> ''),
    address                  VARCHAR(150)
                             CHECK (address = btrim(address) AND address <> ''),
    address_complement       VARCHAR(150)
                             CHECK (address_complement = btrim(address_complement)
                                    AND address_complement <> ''),
    postal_code              VARCHAR(10)
                             CHECK (postal_code = btrim(postal_code) AND postal_code <> ''),
    town                     VARCHAR(100)
                             CHECK (town = btrim(town) AND town <> ''),
    is_married               BOOLEAN,
    is_civil_solidarity_pact BOOLEAN,
    nb_children              SMALLINT CHECK (nb_children >= 0),
    birth_date               DATE CHECK (birth_date <= CURRENT_DATE),

    CONSTRAINT ck_client_phone_number_format                     -- ADR-007, Q-PRO-08
        CHECK (phone_number ~ '^\+[1-9]([ -]?[0-9]){1,14}$'),
    CONSTRAINT ck_client_marital_status_exclusive
        CHECK (NOT (is_married AND is_civil_solidarity_pact)),
    -- Tout-ou-rien gardé (Q-SCH-01) : les 18 clients repris sans adresse
    -- reçoivent « non renseigné » et le code postal 00000 (Q-SCH-18, 02).
    CONSTRAINT ck_client_address_all_or_nothing
        CHECK ((address IS NULL     AND postal_code IS NULL     AND town IS NULL)
            OR (address IS NOT NULL AND postal_code IS NOT NULL AND town IS NOT NULL)),
    CONSTRAINT ck_client_postal_code_needs_country
        CHECK (postal_code IS NULL OR country_iso IS NOT NULL),
    -- Correction 8 : Eircode sans espace, comme criteria et estate (Q-SCH-12).
    CONSTRAINT ck_client_postal_code_format
        CHECK (postal_code IS NULL OR CASE
            WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
            WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
            WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
            WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
            WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
            WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W)[0-9AC-FHKNPRTV-Y]{4}$'
            ELSE FALSE END)
);

-- Créée avant hunter : hunter.id_realestatemanager la référence.
CREATE TABLE real_estate_manager (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),  -- Q-SCH-09
    id_user      INTEGER NOT NULL UNIQUE
                 REFERENCES "user"(id) ON DELETE RESTRICT,
    first_name   VARCHAR(80) NOT NULL
                 CHECK (first_name = btrim(first_name) AND first_name <> ''),
    last_name    VARCHAR(80) NOT NULL
                 CHECK (last_name = btrim(last_name) AND last_name <> ''),
    phone_number VARCHAR(20) NOT NULL
                 CHECK (phone_number = btrim(phone_number) AND phone_number <> ''),
    country_iso  CHAR(2)
                 CHECK (country_iso IN ('FR','ES','DE','GB','IE','BE','NL','LU','IT','CH')),
    gender       VARCHAR(10)
                 CHECK (gender IN ('male', 'female', 'other')),
    company_name VARCHAR(80)
                 CHECK (company_name = btrim(company_name) AND company_name <> ''),

    CONSTRAINT ck_real_estate_manager_phone_number_format        -- ADR-007, Q-PRO-08
        CHECK (phone_number ~ '^\+[1-9]([ -]?[0-9]){1,14}$')
);

CREATE TABLE hunter (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at           TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),  -- Q-SCH-09
    id_user              INTEGER NOT NULL UNIQUE
                         REFERENCES "user"(id) ON DELETE RESTRICT,
    first_name           VARCHAR(80) NOT NULL
                         CHECK (first_name = btrim(first_name) AND first_name <> ''),
    last_name            VARCHAR(80) NOT NULL
                         CHECK (last_name = btrim(last_name) AND last_name <> ''),
    phone_number         VARCHAR(20) NOT NULL
                         CHECK (phone_number = btrim(phone_number) AND phone_number <> ''),
    country_iso          CHAR(2)
                         CHECK (country_iso IN ('FR','ES','DE','GB','IE','BE','NL','LU','IT','CH')),
    gender               VARCHAR(10)
                         CHECK (gender IN ('male', 'female', 'other')),
    company_name         VARCHAR(80)
                         CHECK (company_name = btrim(company_name) AND company_name <> ''),
    hire_date            DATE NOT NULL CHECK (hire_date <= CURRENT_DATE),
    education_level      VARCHAR(20)
                         CHECK (education_level = btrim(education_level) AND education_level <> ''),
    -- La « carte T » (carte professionnelle d'agent immobilier). Le MPD
    -- l'écrivait is_carteT, replié par PostgreSQL ; renommée le 2026-10-07
    -- (Q-SCH-10, LOT7).
    is_carte_t           BOOLEAN,
    certification_date   DATE,
    -- Non quoté : PostgreSQL le replie en minuscules -> is_hunter_ai.
    is_hunter_ai         BOOLEAN,
    -- Le manager du chasseur (MPD 03 4, 2026-09-22). NOT NULL : un chasseur
    -- a toujours un manager. Voir l'en-tête « CHAQUE CHASSEUR A UN MANAGER ».
    id_realestatemanager INTEGER NOT NULL
                         REFERENCES real_estate_manager(id_user) ON DELETE RESTRICT,

    CONSTRAINT ck_hunter_phone_number_format                     -- ADR-007, Q-PRO-08
        CHECK (phone_number ~ '^\+[1-9]([ -]?[0-9]){1,14}$')
);


-- ============================================================================
-- 3. DEMANDE DE RECHERCHE ET CRITÈRES
-- ============================================================================

CREATE TABLE search_request (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at           TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    id_author            INTEGER NOT NULL
                         REFERENCES "user"(id) ON DELETE RESTRICT,
    id_client            INTEGER NOT NULL
                         REFERENCES client(id_user) ON DELETE RESTRICT,
    id_hunter            INTEGER
                         REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_realestatemanager INTEGER
                         REFERENCES real_estate_manager(id_user) ON DELETE RESTRICT,
    -- Correction 7 : VARCHAR(9) dans le MPD, au ras de 'confirmed'.
    status               VARCHAR(20) NOT NULL
                         CHECK (status IN ('confirmed', 'accepted', 'rejected', 'launched'))
);

-- Versionnée : chaque révision pointe vers la précédente (id_previous_version).
CREATE TABLE criteria (
    id                     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at             TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    change_reason          VARCHAR(255)
                           CHECK (change_reason = btrim(change_reason) AND change_reason <> ''),

    -- Localisation, en texte comme dans le MPD. N2 tranché le 2026-10-05 :
    -- elle reste ici, un ADR remplace ADR-009 (Q-SCH-02).
    country_iso            CHAR(2)
                           CHECK (country_iso IN ('FR','ES','DE','GB','IE','BE','NL','LU','IT','CH')),
    town                   VARCHAR(100)
                           CHECK (town = btrim(town) AND town <> ''),
    postal_code            VARCHAR(10),
    -- Quartier, facultatif comme dans les secteurs d'origine (Q-MIG-08).
    district               VARCHAR(100)
                           CHECK (district = btrim(district) AND district <> ''),

    estate_type            VARCHAR(50) NOT NULL
                           CHECK (estate_type IN ('Appartement', 'Maison', 'Studio', 'Loft',
                                                  'Villa', 'Duplex', 'Terrain', 'Local commercial',
                                                  'Chalet', 'Château')),
    typology               VARCHAR(50)
                           CHECK (typology IN ('Studio', 'T1 / F1', 'T1 bis / F1 bis',
                                               'T2 / F2', 'T2 bis / F2 bis', 'T3 / F3',
                                               'T3 bis / F3 bis', 'T4 / F4', 'T4 bis / F4 bis',
                                               'T5 / F5', 'T5 bis / F5 bis', 'T6+ / F6+')),

    -- Montants en EUROS (voir l'avertissement d'en-tête).
    budget_min             INTEGER CHECK (budget_min > 0),
    budget_max             INTEGER NOT NULL CHECK (budget_max > 0),

    floor                  VARCHAR(10)
                           CHECK (floor IN ('0','1','2','3','4','5','6','7','8','9',
                                            '10 and more','last floor')),
    is_new_build           BOOLEAN,
    needs_renovation       BOOLEAN,
    renovation_budget_min  INTEGER CHECK (renovation_budget_min >= 0),
    renovation_budget_max  INTEGER CHECK (renovation_budget_max >= 0),
    energy_class_max       CHAR(1) CHECK (energy_class_max IN ('A','B','C','D','E','F','G')),

    rooms_min              SMALLINT CHECK (rooms_min > 0),
    rooms_max              SMALLINT CHECK (rooms_max > 0),
    bedrooms_min           SMALLINT CHECK (bedrooms_min >= 0),
    bedrooms_max           SMALLINT CHECK (bedrooms_max >= 0),
    toilets_min            SMALLINT CHECK (toilets_min >= 0),
    toilets_max            SMALLINT CHECK (toilets_max >= 0),
    bathrooms_min          SMALLINT CHECK (bathrooms_min >= 0),
    bathrooms_max          SMALLINT CHECK (bathrooms_max >= 0),
    swimming_pool_min      SMALLINT CHECK (swimming_pool_min >= 0),
    swimming_pool_max      SMALLINT CHECK (swimming_pool_max >= 0),
    has_garden             BOOLEAN,
    nb_balcony_min         INTEGER CHECK (nb_balcony_min >= 0),
    nb_balcony_max         INTEGER CHECK (nb_balcony_max >= 0),
    nb_terrace_min         INTEGER CHECK (nb_terrace_min >= 0),
    nb_terrace_max         INTEGER CHECK (nb_terrace_max >= 0),
    is_climatised          BOOLEAN,
    surface_min            NUMERIC(7,2) CHECK (surface_min > 0),
    surface_max            NUMERIC(7,2) CHECK (surface_max > 0),
    land_surface_min       NUMERIC(9,2) CHECK (land_surface_min >= 0),
    land_surface_max       NUMERIC(9,2) CHECK (land_surface_max >= 0),
    has_separate_kitchen   BOOLEAN,
    has_cellar             BOOLEAN,
    has_view               BOOLEAN,
    is_quiet               BOOLEAN,
    is_bright              BOOLEAN,
    has_garage             BOOLEAN,
    has_elevator           BOOLEAN,
    has_chimney            BOOLEAN,
    parking_spaces         SMALLINT CHECK (parking_spaces >= 0),

    id_author              INTEGER NOT NULL
                           REFERENCES "user"(id) ON DELETE RESTRICT,
    id_search_request      INTEGER NOT NULL
                           REFERENCES search_request(id) ON DELETE RESTRICT,
    id_previous_version    INTEGER
                           REFERENCES criteria(id) ON DELETE RESTRICT,

    CONSTRAINT chk_budget           CHECK (budget_max >= budget_min),
    CONSTRAINT chk_renov_budget     CHECK (renovation_budget_max >= renovation_budget_min),
    CONSTRAINT chk_rooms            CHECK (rooms_max >= rooms_min),
    CONSTRAINT chk_bedrooms         CHECK (bedrooms_max >= bedrooms_min),
    CONSTRAINT chk_toilets          CHECK (toilets_max >= toilets_min),
    -- Correction 6 : seul couple min/max sans CHECK d'ordre dans le MPD.
    CONSTRAINT chk_bathrooms        CHECK (bathrooms_max >= bathrooms_min),
    CONSTRAINT chk_pool             CHECK (swimming_pool_max >= swimming_pool_min),
    CONSTRAINT chk_balcony          CHECK (nb_balcony_max >= nb_balcony_min),
    CONSTRAINT chk_terrace          CHECK (nb_terrace_max >= nb_terrace_min),
    CONSTRAINT chk_surface          CHECK (surface_max >= surface_min),
    CONSTRAINT chk_land_surface     CHECK (land_surface_max >= land_surface_min),
    CONSTRAINT chk_town_requires_country
        CHECK (town IS NULL OR country_iso IS NOT NULL),
    CONSTRAINT chk_criteria_district_needs_town
        CHECK (district IS NULL OR town IS NOT NULL),
    CONSTRAINT chk_postal_code_needs_country
        CHECK (postal_code IS NULL OR country_iso IS NOT NULL),
    -- Corrections 1 et 8 : parenthèse en trop retirée ; Eircode sans espace (Q-SCH-12).
    CONSTRAINT chk_postal_code_format
        CHECK (postal_code IS NULL OR CASE
            WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
            WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
            WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
            WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
            WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
            WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W)[0-9AC-FHKNPRTV-Y]{4}$'
            ELSE FALSE END)
);


-- ============================================================================
-- 4. MANDAT
-- ============================================================================

CREATE TABLE mandate (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at        TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    reference         VARCHAR(20) NOT NULL UNIQUE
                      CHECK (reference = btrim(reference) AND reference <> ''),
    -- 'lost' : vente perdue, personne n'est payé sur ce mandat — vendu hors
    -- agence (Q-REM-02, Jeff : « rien pour personne », Q-JEF-03) ou par un
    -- collègue sur l'autre mandat non exclusif (Q-REM-14). Un seul statut pour
    -- les deux cas (tranché le 2026-10-07, LOT3).
    status            VARCHAR(20) NOT NULL
                      CHECK (status IN ('active', 'completed', 'expired',
                                        'renewed', 'canceled', 'pending_signature',
                                        'lost')),
    -- Seule trace de la signature du client : is_client_signed est retiré,
    -- la date et le statut 'pending_signature' suffisent (Q-MAN-05, Q-MAN-09).
    signature_date    DATE,
    signature_type    VARCHAR(20) CHECK (signature_type IN ('electronic', 'paper')),
    -- Date de fin STOCKÉE : décision N1 du 11/09/26 (option A), qui écarte
    -- l'ADR-004 (durée calculée) au profit de l'ADR-018 (figer la date).
    -- Sa valeur est imposée par chk_mandate_six_months, plus bas.
    ends_at           DATE,
    is_exclusive      BOOLEAN NOT NULL,
    id_hunter         INTEGER NOT NULL
                      REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_client         INTEGER NOT NULL
                      REFERENCES client(id_user) ON DELETE RESTRICT,
    id_search_request INTEGER NOT NULL
                      REFERENCES search_request(id) ON DELETE RESTRICT,
    -- Renouvellement : le NOUVEAU mandat pointe vers le précédent, et lui seul.
    -- Pas d'avenant (décision du groupe, 2026-10-08) : un mandat a au plus un
    -- successeur, d'où le UNIQUE. Le statut 'renewed' est celui de l'ANCIEN
    -- mandat. Cela remplace D8, ADR-010 et ADR-013 (ADR à écrire) ; chk_renewed
    -- est retiré : l'ancien mandat n'a pas de parent à exiger.
    id_mandate_parent INTEGER UNIQUE REFERENCES mandate(id) ON DELETE RESTRICT,

    -- 'canceled' accepte un mandat jamais signé : un client peut renoncer
    -- avant de signer (Q-MAN-07). Les autres statuts restent stricts.
    CONSTRAINT chk_status_signature
        CHECK ((status = 'pending_signature' AND signature_date IS NULL)
            OR  status = 'canceled'
            OR (status NOT IN ('pending_signature', 'canceled')
                AND signature_date IS NOT NULL)),

    -- U05 : durée de validité de EXACTEMENT 6 mois (Q-MAN-01), à la place
    -- de l'ancien CHECK de ends_at, qui n'imposait que l'ordre des dates.
    -- Règle : 00_regles_metier_mandat_remuneration.feature:37, exemple l. 39
    -- (signature 2026-02-25 -> fin 2026-08-25). Fin de mois : le 31/08
    -- + 6 mois rend le 28 ou 29/02 — l'API devra calculer pareil (Q-MAN-01).
    CONSTRAINT chk_mandate_six_months
        CHECK ((signature_date IS NULL AND ends_at IS NULL)
            OR (signature_date IS NOT NULL
                AND ends_at = (signature_date + INTERVAL '6 months')::date))
);

-- ----------------------------------------------------------------------------
-- U02 / décision D7 — EXCLUSIVITÉ DU MANDAT (Q-MAN-02 ; activé le 2026-10-07, LOT4)
--
--   Règle : « aucun autre chasseur ne peut agir pour le compte d'Alice
--   pendant la durée du mandat » (00_regles_metier..., scénario @exclusif,
--   l. 20). Un mandat exclusif bloque donc TOUT autre mandat du même client,
--   qu'il soit exclusif OU NON. Mais deux mandats NON exclusifs peuvent
--   coexister (règle U03, scénario @non-exclusif l. 30).
--
--   ⚠️ UNE CONTRAINTE EXCLUDE NE SUFFIT PAS — mesuré, pas supposé :
--     - EXCLUDE ... WHERE (is_exclusive) : ne compare que les exclusifs entre
--       eux. Un mandat NON exclusif posé pendant un exclusif passe encore.
--     - EXCLUDE sans ce filtre : rejette aussi deux mandats non exclusifs,
--       ce que la règle U03 autorise explicitement. Testé : ce cas fait même
--       échouer la création d'un jeu de données pourtant légitime.
--   Un EXCLUDE ne sait pas exprimer « si l'UN DES DEUX est exclusif » :
--   son prédicat ne regarde qu'une ligne à la fois. Il faut un TRIGGER.
--
--   D7 tranchée (Q-MAN-02, Jeff : Q-JEF-06) : un mandat 'canceled' libère le
--   client TOUT DE SUITE — il ne bloque personne, et rien ne le bloque.
--   Même règle pour un mandat clos, 'completed' ou 'lost' (ADR-039,
--   Décision 5, confirmée par Sébastien le 2026-10-09) : la vente est faite
--   ou perdue, le mandat n'a plus rien à protéger. Migration :
--   docker/migrations/v2-vers-v3/19_mandat-clos-libere-le-client.sql.
--
--   Renouvellement (Q-MAN-02) : signé à l'échéance, il touche la date de fin
--   de son parent ('[]'). Le parent et l'enfant sont donc exclus l'un pour
--   l'autre, dans les deux sens : à la création de l'enfant, et à la mise à
--   jour du parent. IS DISTINCT FROM, jamais <> : sans parent, <> vaut NULL
--   et le trigger ne bloquerait plus rien.
--
--   L'ERRCODE 23514 est volontaire : il range le refus dans la classe 23
--   (violation d'intégrité), que le harnais de tests adverses reconnaît.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION check_mandate_exclusivity() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.signature_date IS NULL OR NEW.ends_at IS NULL
       OR NEW.status IN ('canceled', 'completed', 'lost') THEN
        RETURN NEW;                       -- pas encore signé, annulé ou clos
    END IF;
    IF EXISTS (
        SELECT 1 FROM mandate m
         WHERE m.id        <> NEW.id
           AND m.id_client  = NEW.id_client
           AND m.status NOT IN ('canceled', 'completed', 'lost')
           AND (m.is_exclusive OR NEW.is_exclusive)
           AND m.id IS DISTINCT FROM NEW.id_mandate_parent   -- son parent
           AND m.id_mandate_parent IS DISTINCT FROM NEW.id   -- ses enfants
           AND m.signature_date IS NOT NULL AND m.ends_at IS NOT NULL
           AND daterange(m.signature_date, m.ends_at, '[]')
            && daterange(NEW.signature_date, NEW.ends_at, '[]')
    ) THEN
        RAISE EXCEPTION
            'U02 : un mandat exclusif interdit tout autre mandat pour ce client sur la periode'
            USING ERRCODE = '23514', CONSTRAINT = 'u02_mandate_exclusivity';
    END IF;
    RETURN NEW;
END $fn$;

CREATE TRIGGER trg_mandate_exclusivity
    BEFORE INSERT OR UPDATE ON mandate
    FOR EACH ROW EXECUTE FUNCTION check_mandate_exclusivity();
-- ----------------------------------------------------------------------------


-- ============================================================================
-- 5. BIENS
-- ============================================================================

CREATE TABLE estate (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at           TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    reference            VARCHAR(50) NOT NULL UNIQUE
                         CHECK (reference = btrim(reference) AND reference <> ''),
    country_iso          CHAR(2)
                         CHECK (country_iso IN ('FR','ES','DE','GB','IE','BE','NL','LU','IT','CH')),
    estate_type          VARCHAR(50) NOT NULL
                         CHECK (estate_type IN ('Appartement', 'Maison', 'Studio', 'Loft',
                                                'Villa', 'Duplex', 'Terrain', 'Local commercial',
                                                'Chalet', 'Château')),
    -- Euros. Charger depuis annonces_normalised.csv colonne « price_eur ».
    price                INTEGER CHECK (price >= 0),
    construction_date    DATE,
    -- Lettre du DPE, recopiée de la colonne dpe du CSV : 1 623 biens repris,
    -- vide (NULL) pour les 933 sans lettre (Q-MIG-06, LOT9). Les quatre
    -- autres colonnes d'énergie restent vides, la source n'en a rien (Q-MIG-05).
    energy_class         CHAR(1) CHECK (energy_class IN ('A','B','C','D','E','F','G')),
    energy_class_scheme  VARCHAR(20),
    energy_class_date    DATE,
    energy_kwh_m2        INTEGER CHECK (energy_kwh_m2 > 0),
    energy_co2_m2        INTEGER CHECK (energy_co2_m2 > 0),
    latitude             NUMERIC(9,6) CHECK (latitude BETWEEN -90 AND 90),
    longitude            NUMERIC(9,6) CHECK (longitude BETWEEN -180 AND 180),
    floor                VARCHAR(10)
                         CHECK (floor IN ('0','1','2','3','4','5','6','7','8','9',
                                          '10 and more','last floor')),
    typology             VARCHAR(50)
                         CHECK (typology IN ('Studio', 'T1 / F1', 'T1 bis / F1 bis',
                                             'T2 / F2', 'T2 bis / F2 bis', 'T3 / F3',
                                             'T3 bis / F3 bis', 'T4 / F4', 'T4 bis / F4 bis',
                                             'T5 / F5', 'T5 bis / F5 bis', 'T6+ / F6+')),
    nb_rooms             SMALLINT CHECK (nb_rooms > 0),
    nb_bedrooms          SMALLINT CHECK (nb_bedrooms >= 0),
    nb_bathrooms         SMALLINT CHECK (nb_bathrooms >= 0),
    nb_toilets           SMALLINT CHECK (nb_toilets >= 0),
    nb_swimming_pool     SMALLINT CHECK (nb_swimming_pool >= 0),
    has_garden           BOOLEAN,
    nb_balcony           INTEGER CHECK (nb_balcony >= 0),
    nb_terrace           INTEGER CHECK (nb_terrace >= 0),
    is_climatised        BOOLEAN,
    surface              NUMERIC(7,2) NOT NULL CHECK (surface > 0),
    land_surface         NUMERIC(9,2) CHECK (land_surface >= 0),
    has_cellar           BOOLEAN,
    has_view             BOOLEAN,
    is_quiet             BOOLEAN,
    is_bright            BOOLEAN,
    has_garage           BOOLEAN,
    has_elevator         BOOLEAN,
    has_chimney          BOOLEAN,
    parking_spaces       SMALLINT CHECK (parking_spaces >= 0),
    has_separate_kitchen BOOLEAN,
    needs_renovation     BOOLEAN,
    town                 VARCHAR(100) NOT NULL
                         CHECK (town = btrim(town) AND town <> ''),
    street               VARCHAR(100)
                         CHECK (street = btrim(street) AND street <> ''),
    street_number        VARCHAR(10)
                         CHECK (street_number = btrim(street_number) AND street_number <> ''),
    postal_code          VARCHAR(10)
                         CHECK (postal_code = btrim(postal_code) AND postal_code <> ''),
    -- Quartier, facultatif (Q-MIG-08) : vide sur les 2 556 biens repris, le
    -- CSV source n'a que town, street et postal_code.
    district             VARCHAR(100)
                         CHECK (district = btrim(district) AND district <> ''),
    information          TEXT CHECK (char_length(information) <= 2000),
    -- Auteur d'un bien saisi à la main, chasseur ou manager ; vide (NULL) :
    -- bien importé (Q-ACC-09, Q-JEF-24 ; LOT9). Même forme que
    -- criteria.id_author : un auteur inconnu est refusé, le rôle se vérifie
    -- dans l'API.
    id_author            INTEGER
                         REFERENCES "user"(id) ON DELETE RESTRICT,

    -- Format du code postal par pays, même CASE que client et criteria
    -- (Q-SCH-11, LOT8). Un code postal sans pays tombe dans ELSE : refusé.
    CONSTRAINT chk_estate_postal_code_format
        CHECK (postal_code IS NULL OR CASE
            WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
            WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
            WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
            WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
            WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
            WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W)[0-9AC-FHKNPRTV-Y]{4}$'
            ELSE FALSE END)
);

CREATE TABLE picture (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    url        TEXT NOT NULL,
    id_estate  INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT
);


-- ============================================================================
-- 6. SÉLECTION ET PROPOSITION DE BIENS
-- ============================================================================

-- Biens retenus par le chasseur pour une demande (sélection quotidienne).
-- Correction 3 : la colonne s'appelait « id : » dans le diagramme, et la
-- virgule manquait entre les deux contraintes.
CREATE TABLE estate_searchrequest (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at        TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    review_hunter     TEXT CHECK (char_length(review_hunter) <= 2000),
    id_estate         INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    id_search_request INTEGER NOT NULL REFERENCES search_request(id) ON DELETE RESTRICT,
    id_hunter         INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,

    CONSTRAINT uq_estate_search UNIQUE (id_estate, id_search_request)
);

-- Médias (audio, vidéo) joints à la note d'avis du chasseur : plusieurs par
-- note (scénario 06 : « des commentaires audio et des vidéos »). Remplace les
-- colonnes media_url / media_type de estate_searchrequest, qui n'en
-- permettaient qu'un (décision du groupe, 2026-10-08).
CREATE TABLE review_media (
    id                       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at               TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    media_url                TEXT NOT NULL,
    media_type               VARCHAR(10) NOT NULL CHECK (media_type IN ('audio', 'video')),
    id_estate_searchrequest  INTEGER NOT NULL
                             REFERENCES estate_searchrequest(id) ON DELETE RESTRICT
);

-- Biens effectivement proposés au client, et suivi de l'offre.
CREATE TABLE estate_proposed (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at         TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    comment_hunter     TEXT CHECK (char_length(comment_hunter) <= 2000),
    comment_client     TEXT,
    -- Euros.
    amount_proposition INTEGER CHECK (amount_proposition >= 0),
    -- 'signed' : l'offre est signée (Q-SCH-04, ferme D5).
    proposition_status VARCHAR(20) NOT NULL
                       CHECK (proposition_status IN ('proposed', 'offer_pending',
                                                     'accepted', 'signed', 'rejected')),
    id_hunter          INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_estate          INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    id_mandate         INTEGER NOT NULL REFERENCES mandate(id) ON DELETE RESTRICT,

    -- Correction 2 : cette contrainte figurait EN DOUBLE dans le diagramme.
    -- Un bien seulement « proposé » n'a pas de montant ; dès qu'il quitte cet
    -- état, le montant devient obligatoire.
    CONSTRAINT chk_offer
        CHECK ((proposition_status =  'proposed' AND amount_proposition IS NULL)
            OR (proposition_status <> 'proposed' AND amount_proposition IS NOT NULL)),

    -- Décision D6 : priorité donnée par le client à un bien proposé, de 1 à
    -- 5 (Q-SCH-05, Jeff : Q-JEF-18 ; LOT7). Vide tant que le client n'a pas
    -- donné son avis.
    client_priority    SMALLINT CHECK (client_priority BETWEEN 1 AND 5)
);

-- Visites (décision D10 : la table manquait, le MPD 03 la crée).
CREATE TABLE visit (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    visit_date   DATE NOT NULL,
    visitor_type VARCHAR(10) NOT NULL CHECK (visitor_type IN ('hunter', 'client')),
    id_estate    INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    id_mandate   INTEGER NOT NULL REFERENCES mandate(id) ON DELETE RESTRICT

    -- TODO (déroulé 01 -> 02) — une visite ne peut pas précéder la signature
    --   du mandat. Testé : une visite datée 2025 sur un mandat signé en 2026
    --   est acceptée aujourd'hui. Croise deux tables.
    --   ➡️ Contrôlé par l'API (Q-MAN-06, tranché le 2026-10-05), avec un test
    --   d'intégration ; pas de trigger. Règle et test restent à écrire.
);


-- ============================================================================
-- 7. VENTE ET RÉMUNÉRATION
-- ============================================================================

-- Paramètres d'honoraires, historisés (montant fixe + pourcentage du prix).
-- Q-SCH-17 (2026-10-05) : une grille vaut jusqu'à la suivante, par
--   construction. Plus de date de fin, donc plus de trou ni de chevauchement
--   possible ; deux grilles ne démarrent pas le même jour. La grille d'une
--   vente = la dernière dont effective_from <= date de l'acte. Seul cas
--   restant : une vente avant la 1re grille, couvert par le seed (Q-REM-15).
--   Créée avant sale, qui la référence (Q-REM-13).
CREATE TABLE parameters_fees (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at     TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    -- « En vigueur à partir du » (Q-SCH-17 ; valid_from en v2).
    effective_from DATE NOT NULL,
    -- Euros entiers : la source officielle donne « 3000,00 », soit 3000.
    fixed_amount   INTEGER NOT NULL CHECK (fixed_amount > 0),
    rate           NUMERIC(5,4) NOT NULL CHECK (rate >= 0 AND rate <= 1),

    -- Q-SCH-17 : remplace l'EXCLUDE de v2 (excl_fees_no_overlap).
    CONSTRAINT uq_fees_effective_from UNIQUE (effective_from)
);

CREATE TABLE sale (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    signature_date  DATE NOT NULL,
    -- Euros. Prix d'acte : jusqu'à 800 000 dans les Gherkin officiels.
    purchase_amount INTEGER NOT NULL CHECK (purchase_amount > 0),
    -- Honoraires (l'assiette du calcul) : montant fixe + % du prix.
    fees_amount     NUMERIC(12,2) NOT NULL CHECK (fees_amount > 0),
    sale_origin     VARCHAR(20) NOT NULL
                    CHECK (sale_origin IN ('hunter', 'client_alone')),
    id_mandate      INTEGER NOT NULL UNIQUE REFERENCES mandate(id) ON DELETE RESTRICT,
    id_estate       INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    -- Q-REM-13 (2026-10-05) : la grille d'honoraires qui a donné fees_amount.
    --   Le montant reste figé ici ; la clé dit d'où il vient.
    --   TODO — que ce soit bien la grille en vigueur à la date de l'acte
    --   n'est pas vérifié : croise sale et parameters_fees -> API.
    id_parameters_fees INTEGER NOT NULL
                       REFERENCES parameters_fees(id) ON DELETE RESTRICT,

    CONSTRAINT chk_fees_lower_than_price CHECK (fees_amount < purchase_amount)

    -- TODO (déroulé 01 -> 03) — la vente doit tomber DANS la validité du
    --   mandat, et le mandat doit être signé. Testé : une vente datée 2025 sur
    --   un mandat signé en 2026, une vente en 2030 sur un mandat clos en 2026,
    --   et une vente sur un mandat 'pending_signature' sont toutes acceptées.
    --   Croise sale et mandate.
    --   ➡️ Contrôlé par l'API (Q-MAN-06, tranché le 2026-10-05), avec un test
    --   d'intégration ; pas de trigger. Règle et test restent à écrire.
    -- TODO (D3) — cas déjà tranché par les sources officielles : un acte signé
    --   APRÈS la fin du mandat peut ouvrir droit à rémunération sous condition
    --   (REGLES-CALCUL-REMUNERATION.md:98). La règle ci-dessus doit donc tenir
    --   compte de ce délai, et non refuser sèchement.
);

-- Barème de commission : tranches de prix -> taux de base.
-- id_hunter NULL = barème par défaut ; renseigné = barème propre au chasseur.
CREATE TABLE commission_scale (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at  TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    -- Euros : les tranches officielles montent à 750 000 et au-delà.
    amount_min  INTEGER NOT NULL CHECK (amount_min >= 0),
    amount_max  INTEGER CHECK (amount_max > amount_min),
    -- Q-SCH-15 (2026-10-05) : > 0, comme payment.base_rate. Avec le plancher,
    --   une tranche à 0 % paierait quand même 20 % (rem.py:264) : un taux nul
    --   n'a pas de sens.
    rate        NUMERIC(5,4) NOT NULL CHECK (rate > 0 AND rate <= 1),
    valid_from  DATE NOT NULL,
    valid_until DATE,
    id_hunter   INTEGER REFERENCES hunter(id_user) ON DELETE RESTRICT,

    CONSTRAINT chk_scale_amounts
        CHECK (amount_max IS NULL OR amount_max > amount_min),
    CONSTRAINT chk_scale_period
        CHECK (valid_until IS NULL OR valid_until > valid_from),
    -- Pas deux tranches qui se chevauchent pour un même chasseur.
    CONSTRAINT excl_scale_no_overlap
        EXCLUDE USING gist (
            id_hunter WITH =,
            numrange(amount_min, amount_max, '[]') WITH &&,
            daterange(valid_from, valid_until, '[]') WITH &&
        ),
    -- Idem pour le barème par défaut, que le précédent laisse passer (NULL
    -- n'est jamais égal à NULL, donc l'exclusion ne s'y applique pas).
    CONSTRAINT excl_scale_global
        EXCLUDE USING gist (
            numrange(amount_min, amount_max, '[]') WITH &&,
            daterange(valid_from, valid_until, '[]') WITH &&
        ) WHERE (id_hunter IS NULL)
);

-- Paramètres du calcul de rémunération, versionnés (Q-REM-05, 2026-10-02) :
--   le sujet veut « une table de paramètres, jamais en dur »
--   (REGLES-CALCUL-REMUNERATION.md l. 42-47). Une ligne = un jeu complet,
--   celui de ParametresPerformance et ParametresModulation (rem.py:92-116).
--   Les honoraires et le barème ont déjà leurs tables (parameters_fees,
--   commission_scale).
-- Nom (G2, 2026-10-08) : « réglages du taux du chasseur ». Ex-
--   remuneration_parameters, qui se confondait avec parameters_fees ; tout
--   ce qui suit fait passer du taux du barème au taux final.
-- Versions : comme parameters_fees (Q-SCH-17), une version vaut jusqu'à la
--   suivante — choisi le 2026-10-07 pour cette table, à la place du couple
--   valid_from / valid_until de la carte Q-REM-05.
-- Aucun CHECK sur les valeurs : ce sont des paramètres « à valider avec le
--   client » (l. 59) ; les graver refait l'erreur que Q-REM-05 corrige.
-- La grille de notes du taux de transformation (Q-JEF-05) n'est pas ici :
--   chantier API.
CREATE TABLE hunter_rate_parameters (
    id                      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at              TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    effective_from          DATE NOT NULL,
    -- Performance (rem.py:92-105) : les poids des 5 critères ...
    weight_delay            NUMERIC(5,4) NOT NULL,
    weight_exclusivity      NUMERIC(5,4) NOT NULL,
    weight_sales            NUMERIC(5,4) NOT NULL,
    weight_mandates         NUMERIC(5,4) NOT NULL,
    weight_visits           NUMERIC(5,4) NOT NULL,
    -- ... les paliers, borne haute incluse -> note, la dernière ouverte :
    --   [{"maximum": 12, "note": 100}, ..., {"maximum": null, "note": 0}]
    delay_tiers             JSONB NOT NULL,  -- en semaines
    visit_tiers             JSONB NOT NULL,
    -- ... les notes, les points et la fenêtre glissante.
    score_exclusive         NUMERIC(4,1) NOT NULL,
    score_non_exclusive     NUMERIC(4,1) NOT NULL,
    points_per_sale         NUMERIC(4,1) NOT NULL,
    points_per_mandate      NUMERIC(4,1) NOT NULL,
    window_months           INTEGER NOT NULL,
    -- Modulation (rem.py:108-116) : a = min(taux × années ; plafond),
    --   p = (S - pivot) / demi-amplitude × amplitude, r borné.
    seniority_rate_per_year NUMERIC(5,4) NOT NULL,
    seniority_cap           NUMERIC(5,4) NOT NULL,
    score_pivot             NUMERIC(4,1) NOT NULL,
    score_half_range        NUMERIC(4,1) NOT NULL,
    performance_amplitude   NUMERIC(5,4) NOT NULL,
    rate_floor              NUMERIC(5,4) NOT NULL,
    rate_ceiling            NUMERIC(5,4) NOT NULL,

    -- Deux versions ne démarrent pas le même jour (comme uq_fees_effective_from).
    CONSTRAINT uq_hunter_rate_effective_from UNIQUE (effective_from)
);

CREATE TABLE payment (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at          TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    -- Euros, arrondi au centime au demi supérieur (règle officielle).
    -- Vaut 0.00 sur une ligne de refus (ADR-024, décision D2 : « R = 0 »).
    amount              NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    -- 'refused' (ADR-024) : le droit à rémunération est fermé. La ligne
    --   porte son motif et aucun montant, ni taux, ni barème.
    -- Les étapes de la facture sont retirées : la facture est hors périmètre
    --   (Q-JEF-23, Q-REM-17 revue le 2026-10-07). Le paiement va de
    --   'announced' à 'scheduled', puis 'paid'.
    status              VARCHAR(20) NOT NULL
                        CHECK (status IN ('refused', 'announced',
                                          'scheduled', 'paid')),
    -- Q-REM-17 : une date par étape (user-stories/07, l. 10-34). Le chasseur
    --   est prévenu (announced_at), le virement est prévu pour un jour
    --   (scheduled_for), puis fait (paid_at).
    announced_at        TIMESTAMP,
    scheduled_for       DATE,
    paid_at             TIMESTAMP,
    -- Motif du droit refusé (ADR-024). Les deux valeurs viennent de
    --   l'énumération MotifRefus du sujet (REGLES-CALCUL-REMUNERATION.md
    --   l. 385), transposées en anglais conformément à ADR-002 :
    --     mandate_expired <- MANDAT_EXPIRE   « mandat échu à la date de l'acte »
    --     out_of_scope    <- HORS_DISPOSITIF « mandat non-exclusif et vente
    --                                           hors dispositif »
    refusal_reason      VARCHAR(30)
                        CHECK (refusal_reason IN ('mandate_expired',
                                                  'out_of_scope')),
    -- Taux de tranche issu du barème. NULL sur une ligne de refus (ADR-024) :
    --   un CHECK ne s'appliquant pas à un NULL, la borne reste inchangée.
    base_rate           NUMERIC(5,4) CHECK (base_rate > 0 AND base_rate <= 1),
    -- R21 — le taux final est borné entre 20 % et 60 % par la règle
    --   officielle (10_calcul_remuneration_chasseur.feature:201 ; exemples
    --   l. 236-250 : 65 % ramené à 60 %, 17,60 % remonté à 20 %). Actif
    --   depuis le 2026-10-07 (Q-REM-19, confirmé par Jeff : Q-JEF-01).
    --   ⚠️ 20 % et 60 % sont des paramètres « proposés, non imposés » (en-tête
    --   du Gherkin) : si Jeff les change, ce CHECK change aussi (Q-REM-05).
    final_rate          NUMERIC(5,4) CHECK (final_rate BETWEEN 0.20 AND 0.60),
    -- Majoration d'ancienneté, modulation de performance (décision D2).
    -- NULL toutes les deux sur une ligne de refus (ADR-024).
    -- Q-REM-05 : +10 % max et ±20 % sont des paramètres « à valider avec le
    --   client » (REGLES-CALCUL-REMUNERATION.md l. 59) ; ils vivent dans
    --   hunter_rate_parameters, plus dans ces CHECK (v2 : 0 à 0,10 et
    --   -0,20 à 0,20). Restent les bornes du domaine, choisies le 2026-10-07 :
    --     a >= 0 : a = min(taux × années ; plafond), jamais négatif (l. 199) ;
    --     p >= -1 : r = r0 × (1 + a + p) (l. 203), le facteur reste positif ;
    --     <= 1 : domaine d'un taux, comme base_rate.
    seniority_rate      NUMERIC(5,4) CHECK (seniority_rate BETWEEN 0 AND 1),
    performance_rate    NUMERIC(5,4) CHECK (performance_rate BETWEEN -1 AND 1),
    -- Q-REM-03 : le score qui a servi au calcul, figé à la date de l'acte
    --   (F10:275-287). hunter_performance.score est recalculé APRÈS le
    --   paiement : ce n'est pas le même. Même domaine que lui (0 à 100).
    --   NULL sur une ligne de refus (chk_refused).
    performance_score   NUMERIC(4,1) CHECK (performance_score BETWEEN 0 AND 100),
    -- Q-REM-04 : tous les termes du calcul — les 5 notes et les entrées
    --   (visites, ancienneté, ventes et mandats sur 12 mois) —, pour qu'un
    --   paiement se rejoue même si ces valeurs changent ensuite.
    calculation_details JSONB,
    id_sale             INTEGER NOT NULL UNIQUE REFERENCES sale(id) ON DELETE RESTRICT,
    id_hunter           INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    -- NULL sur une ligne de refus : un droit fermé ne désigne aucune tranche.
    id_commission_scale INTEGER REFERENCES commission_scale(id) ON DELETE RESTRICT,
    -- G1 (groupe, 2026-10-08) : la version des réglages du taux qui a servi
    --   au calcul, comme id_commission_scale pour la tranche et
    --   sale.id_parameters_fees pour les honoraires (Q-REM-13) : le paiement
    --   se rejoue sans chercher la version par date. NULL sur une
    --   ligne de refus (chk_refused). Que ce soit la version en vigueur à la
    --   date de l'acte : contrôlé par l'API, comme le barème (TODO plus bas).
    id_hunter_rate_parameters INTEGER REFERENCES hunter_rate_parameters(id) ON DELETE RESTRICT,

    CONSTRAINT chk_paid
        CHECK ((status =  'paid' AND paid_at IS NOT NULL)
            OR (status <> 'paid' AND paid_at IS NULL)),

    -- Q-REM-17 — comme chk_paid : la date se remplit quand l'étape est
    --   atteinte, et reste ensuite. Un refus n'est ni annoncé ni programmé.
    CONSTRAINT chk_announced
        CHECK ((status IN ('announced', 'scheduled', 'paid')
                AND announced_at IS NOT NULL)
            OR (status = 'refused' AND announced_at IS NULL)),
    CONSTRAINT chk_scheduled
        CHECK ((status IN ('scheduled', 'paid') AND scheduled_for IS NOT NULL)
            OR (status IN ('refused', 'announced') AND scheduled_for IS NULL)),

    -- ADR-024 — un refus et un paiement ne se ressemblent jamais à moitié.
    --   Ferme les deux erreurs qui coûteraient cher : un « refusé » portant
    --   des taux, donc lisible comme un paiement en attente ; et un paiement
    --   réel sans barème ni taux, donc inexplicable après coup.
    -- Q-REM-10 : final_rate est exigé hors refus — dès 'announced', le
    --   montant est annoncé, donc le taux est connu. Q-REM-03 : pas de score
    --   figé sur un refus.
    CONSTRAINT chk_refused
        CHECK ((status =  'refused'
                AND refusal_reason      IS NOT NULL
                AND amount              =  0
                AND base_rate           IS NULL
                AND seniority_rate      IS NULL
                AND performance_rate    IS NULL
                AND final_rate          IS NULL
                AND performance_score   IS NULL
                AND id_commission_scale IS NULL
                AND id_hunter_rate_parameters IS NULL)
            OR (status <> 'refused'
                AND refusal_reason      IS NULL
                AND base_rate           IS NOT NULL
                AND seniority_rate      IS NOT NULL
                AND performance_rate    IS NOT NULL
                AND final_rate          IS NOT NULL
                AND id_commission_scale IS NOT NULL
                AND id_hunter_rate_parameters IS NOT NULL))

    -- TODO (U01/U04, R01-R04, T17) — le droit à être payé n'est pas vérifié :
    --   testé, on peut aujourd'hui payer un chasseur qui n'est PAS celui du
    --   mandat de la vente, et rattacher le paiement à un barème qui n'était
    --   pas en vigueur à la date de l'acte. Croise payment, sale, mandate et
    --   commission_scale.
    --   ➡️ Contrôlé par l'API (Q-MAN-06, tranché le 2026-10-05), avec un test
    --   d'intégration ; pas de trigger. Règle et test restent à écrire.
    --   ADR-024 ne ferme PAS ce TODO : il enregistre le refus, il ne le
    --   calcule pas. Le calcul du droit reste à faire.
);

-- Score de performance du chasseur : un journal des notes (Q-SCH-06,
--   2026-10-05, ferme D9). Une note = une ligne datée à la seconde, sans
--   période ; la note actuelle = la dernière ligne du chasseur. Q-REM-06
--   recalcule la note à chaque vente : deux ventes le même jour doivent
--   passer, ce que les périodes de v2 (valid_from, valid_until, au jour près)
--   refusaient.
CREATE TABLE hunter_performance (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    score        NUMERIC(4,1) NOT NULL CHECK (score BETWEEN 0 AND 100),
    scored_at    TIMESTAMP NOT NULL,
    trigger_type VARCHAR(20) NOT NULL
                 CHECK (trigger_type IN ('initial', 'payment', 'mandate_expired')),
    id_hunter    INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_payment   INTEGER REFERENCES payment(id) ON DELETE RESTRICT,
    id_mandate   INTEGER REFERENCES mandate(id) ON DELETE RESTRICT,

    -- Chaque type de déclencheur impose sa source, et interdit l'autre.
    CONSTRAINT chk_perf_source
        CHECK ((trigger_type = 'payment'         AND id_payment IS NOT NULL AND id_mandate IS NULL)
            OR (trigger_type = 'mandate_expired' AND id_mandate IS NOT NULL AND id_payment IS NULL)
            OR (trigger_type = 'initial'         AND id_payment IS NULL     AND id_mandate IS NULL)),
    -- Q-SCH-06 : un paiement, ou un mandat échu, donne une note et une seule.
    CONSTRAINT uq_perf_payment UNIQUE (id_payment),
    CONSTRAINT uq_perf_mandate UNIQUE (id_mandate)
);

-- Q-SCH-06 : « la dernière note du chasseur » se lit par cet index.
CREATE INDEX idx_perf_hunter_scored_at
    ON hunter_performance (id_hunter, scored_at DESC);


-- ============================================================================
-- MÉTADONNÉES — lisibles par les clients SQL et les ORM
-- ============================================================================

-- Unité monétaire : tout est en euros.
COMMENT ON COLUMN criteria.budget_min IS
  'Budget minimum en EUROS, INTEGER. Ex: 250000 = 250 000 EUR.';
COMMENT ON COLUMN criteria.budget_max IS
  'Budget maximum en EUROS, INTEGER.';
COMMENT ON COLUMN criteria.renovation_budget_min IS
  'Budget travaux minimum en EUROS.';
COMMENT ON COLUMN criteria.renovation_budget_max IS
  'Budget travaux maximum en EUROS.';
COMMENT ON COLUMN estate.price IS
  'Prix affiche du bien en EUROS. Charger depuis annonces_normalised.csv colonne price_eur (PAS price, qui est en K€).';
COMMENT ON COLUMN estate_proposed.amount_proposition IS
  'Montant propose en EUROS.';
COMMENT ON COLUMN sale.purchase_amount IS
  'Prix d achat de l acte authentique en EUROS.';
COMMENT ON COLUMN sale.fees_amount IS
  'Honoraires (assiette de la remuneration) en EUROS, au centime.';
COMMENT ON COLUMN commission_scale.amount_min IS
  'Borne basse de la tranche en EUROS, bornee [min, max] (deux bornes incluses, Q-REM-01). Ex: 200000.';
COMMENT ON COLUMN commission_scale.amount_max IS
  'Borne haute (incluse) de la tranche en EUROS ; NULL = sans plafond. Ex: 349999.';
COMMENT ON COLUMN parameters_fees.fixed_amount IS
  'Part fixe des honoraires en EUROS. Source officielle : 3000,00.';
COMMENT ON COLUMN payment.amount IS
  'Montant verse au chasseur en EUROS, arrondi au centime au demi superieur.';
COMMENT ON COLUMN payment.refusal_reason IS
  'Motif du droit refuse (ADR-024) ; NULL si le droit est ouvert.';

-- Clés étrangères : ce que la colonne contient réellement.
COMMENT ON COLUMN mandate.id_client IS
  'Reference client(id_user) — donc un id de "user", PAS client.id.';
COMMENT ON COLUMN mandate.id_hunter IS
  'Reference hunter(id_user) — donc un id de "user", PAS hunter.id.';
COMMENT ON COLUMN search_request.id_client IS
  'Reference client(id_user) — donc un id de "user".';
COMMENT ON COLUMN search_request.id_hunter IS
  'Reference hunter(id_user) — donc un id de "user".';
COMMENT ON COLUMN search_request.id_realestatemanager IS
  'Reference real_estate_manager(id_user) — donc un id de "user". Le manager qui traite la demande.';
COMMENT ON COLUMN hunter.id_realestatemanager IS
  'Reference real_estate_manager(id_user) — donc un id de "user". Le manager du chasseur (choix du groupe, 2026-09-22).';
COMMENT ON COLUMN payment.id_hunter IS
  'Reference hunter(id_user) — donc un id de "user".';
COMMENT ON COLUMN commission_scale.id_hunter IS
  'Reference hunter(id_user) ; NULL = bareme par defaut, commun a tous.';
COMMENT ON COLUMN hunter_performance.id_hunter IS
  'Reference hunter(id_user) — donc un id de "user".';
COMMENT ON COLUMN estate_proposed.id_hunter IS
  'Reference hunter(id_user) — donc un id de "user".';
COMMENT ON COLUMN estate_searchrequest.id_hunter IS
  'Reference hunter(id_user) — donc un id de "user".';

COMMENT ON COLUMN hunter.id IS
  'Cle technique propre, conservee pour permettre une migration MongoDB. Les FK pointent vers id_user, pas vers elle.';
COMMENT ON COLUMN client.id IS
  'Cle technique propre, conservee pour permettre une migration MongoDB. Les FK pointent vers id_user, pas vers elle.';
COMMENT ON COLUMN real_estate_manager.id IS
  'Cle technique propre, conservee pour permettre une migration MongoDB. Les FK pointent vers id_user, pas vers elle.';

COMMIT;

-- ============================================================================
-- FIN — 19 tables, 258 colonnes (mesuré via information_schema le
-- 2026-10-07, après LOT9), 1 extension.
--
-- Pour activer ce schéma dans docker/docker-compose.yml, remplacer
--     ./init:/docker-entrypoint-initdb.d
-- par
--     ./init-v2:/docker-entrypoint-initdb.d
-- puis « docker compose down -v » : les scripts d'init ne rejouent que sur un
-- volume vide.
--
-- ⚠️ 02_migration.sql et 03_populate_estate.sql visent l'ANCIEN schéma en K€.
-- Ils ne sont pas repris ici et doivent être adaptés (lire « price_eur »).
-- ============================================================================
