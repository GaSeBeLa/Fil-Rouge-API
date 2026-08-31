-- ============================================================================
-- create_fil_rouge_immobilier.sql
-- Script de création du schéma cible "Fil_Rouge_Immobilier"
-- Régénéré depuis MPD_CIBLE_drawio.xml (version la plus à jour du projet)
-- ============================================================================
--
-- PROVENANCE : le tout premier script de création (MPD_cible_groupe.sql) a été
-- écrit et testé en direct sur PostgreSQL dans une session de travail antérieure
-- (choix SERIAL vs GENERATED ALWAYS AS IDENTITY, vérification des mots réservés
-- PostgreSQL, etc.). Ce fichier-ci est une régénération à jour, car le schéma a
-- évolué depuis (password/phone_number devenus NOT NULL, typology ajouté...).
--
-- 2 CORRECTIONS DE DIAGRAMME appliquées ici (bugs trouvés dans le .xml, pas des
-- choix de modélisation) :
--   1. Criteria.typology : le CHECK du diagramme teste "estate_type" au lieu de
--      "typology" (copier-coller). Corrigé pour tester la bonne colonne.
--   2. Estate.estate_type : parenthèse fermante manquante dans le CHECK.
--      Corrigée.
--
-- User.country_iso : la même erreur de copier-coller (CHECK testant "country"
-- au lieu de "country_iso") et un guillemet manquant après 'BE avaient été
-- repérés dans une version antérieure du diagramme, puis corrigés directement
-- par le groupe dans le diagramme source — rien à corriger ici pour ce champ.
--
-- CHOIX DE MODÉLISATION CONFIRMÉ PAR LE GROUPE (pas une erreur) :
--   Hunter / Client / RealEstateManager gardent un "id" auto-généré INDÉPENDANT
--   de "id_user", plutôt que d'utiliser id_user comme clé primaire directement.
--   Objectif : découpler la clé technique de ces tables de la façon dont
--   "user.id" est généré, pour rester portable en cas de changement de SGBD ou
--   de fusion de bases. id_user reste UNIQUE + NOT NULL pour continuer à
--   garantir la relation 1-1 avec "user" (une ligne Hunter = une seule personne,
--   jamais partagée). Toutes les FK du reste du schéma continuent de pointer
--   vers id_user (ex: hunter(id_user)) — possible car UNIQUE, pas obligatoirement PK.
--
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. USER — table racine, toutes les autres tables de personnes en dépendent
-- ----------------------------------------------------------------------------
CREATE TABLE "user" (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at    TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    first_name    VARCHAR(80) NOT NULL,
    last_name     VARCHAR(80) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password      VARCHAR(80) NOT NULL,
    phone_number  VARCHAR(20) NOT NULL,
    gender        VARCHAR(10) CHECK (gender IN ('male', 'female', 'other')),
    -- country_iso : liste ISO 3166-1 des pays visés par le README (France +
    -- projections d'expansion Espagne/Allemagne/UK/Irlande/BeNeLux/Italie/Suisse)
    country_iso   CHAR(2) CHECK (country_iso IN ('FR', 'ES', 'DE', 'GB', 'IE', 'BE', 'NL', 'LU', 'IT', 'CH'))
);

-- ----------------------------------------------------------------------------
-- 2. HUNTER, CLIENT, REAL_ESTATE_MANAGER — spécialisations de "user"
-- ----------------------------------------------------------------------------
-- "id" auto-généré = clé primaire technique, propre à chaque table (portable).
-- "id_user" = lien logique vers "user", UNIQUE + NOT NULL pour garder une
-- vraie relation 1-1 (une ligne Hunter/Client/RealEstateManager = une seule
-- personne). Les FK du reste du schéma continuent de pointer vers id_user.

CREATE TABLE hunter (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_user              INTEGER NOT NULL UNIQUE REFERENCES "user"(id) ON DELETE RESTRICT,
    company_name         VARCHAR(80),
    education_level      VARCHAR(20),
    is_cartet            BOOLEAN,
    certification_date   DATE,
    commission_rate      NUMERIC(4,2)
);

CREATE TABLE client (
    id                         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_user                    INTEGER NOT NULL UNIQUE REFERENCES "user"(id) ON DELETE RESTRICT,
    address                    VARCHAR(150),
    address_complement         VARCHAR(150),
    postal_code                VARCHAR(10),
    town                       VARCHAR(100),
    is_married                 BOOLEAN,
    is_civil_solidarity_pact   BOOLEAN,
    nb_children                SMALLINT,
    birth_date                 DATE
);

CREATE TABLE real_estate_manager (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_user        INTEGER NOT NULL UNIQUE REFERENCES "user"(id) ON DELETE RESTRICT,
    company_name   VARCHAR(80)
);

-- ----------------------------------------------------------------------------
-- 3. SEARCH_REQUEST — la demande de recherche du client
-- ----------------------------------------------------------------------------
CREATE TABLE search_request (
    id                      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at              TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    id_author               INTEGER NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    id_client               INTEGER NOT NULL REFERENCES client(id_user) ON DELETE RESTRICT,
    id_hunter               INTEGER REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_realestatemanager    INTEGER REFERENCES real_estate_manager(id_user) ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 4. CRITERIA — les critères de recherche structurés
-- ----------------------------------------------------------------------------
CREATE TABLE criteria (
    id                       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at               TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    change_reason            VARCHAR(255),
    estate_type              VARCHAR(50),
    -- Correction : CHECK testait "estate_type" au lieu de "typology" dans le diagramme
    typology                 VARCHAR(50) NOT NULL CHECK (typology IN (
                                  'Studio', 'T1 / F1', 'T1 bis / F1 bis', 'T2 / F2',
                                  'T2 bis / F2 bis', 'T3 / F3', 'T3 bis / F3 bis',
                                  'T4 / F4', 'T4 bis / F4 bis', 'T5 / F5',
                                  'T5 bis / F5 bis', 'T6+ / F6+'
                              )),
    budget_min               NUMERIC(6,1) NOT NULL CHECK (budget_min > 0),
    budget_max               NUMERIC(6,1) NOT NULL CHECK (budget_max > 0),
    is_new_build              BOOLEAN,
    needs_renovation          BOOLEAN,
    renovation_budget_min     NUMERIC(6,1) CHECK (renovation_budget_min >= 0),
    renovation_budget_max     NUMERIC(6,1) CHECK (renovation_budget_max >= 0),
    energy_kwh_m2_min         INTEGER CHECK (energy_kwh_m2_min > 0),
    energy_kwh_m2_max         INTEGER CHECK (energy_kwh_m2_max > 0),
    rooms_min                 SMALLINT,
    rooms_max                 SMALLINT,
    bedrooms_min              SMALLINT,
    bedrooms_max              SMALLINT,
    toilets_min               SMALLINT,
    toilets_max               SMALLINT,
    swimming_pool_min         SMALLINT,
    swimming_pool_max         SMALLINT,
    has_garden                BOOLEAN,
    nb_balcony_min            INTEGER CHECK (nb_balcony_min >= 0),
    nb_balcony_max            INTEGER CHECK (nb_balcony_max >= 0),
    nb_terrace_min            INTEGER CHECK (nb_terrace_min >= 0),
    nb_terrace_max            INTEGER CHECK (nb_terrace_max >= 0),
    is_climatised             BOOLEAN,
    surface_min               NUMERIC(6,2),
    surface_max               NUMERIC(6,2),
    land_surface_min          NUMERIC(8,2),
    land_surface_max          NUMERIC(8,2),
    has_separate_kitchen      BOOLEAN,
    has_cellar                BOOLEAN
    has_view                  BOOLEAN
    is_quiet                  BOOLEAN
    is_bright                 BOOLEAN
    has_garage                BOOLEAN,
    has_elevator              BOOLEAN,
    has_chimney               BOOLEAN,
    parking_spaces            SMALLINT,
    has_swimming_pool         BOOLEAN,
    id_author                 INTEGER NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    id_search_request         INTEGER NOT NULL REFERENCES search_request(id) ON DELETE RESTRICT,
    id_previous_version       INTEGER REFERENCES criteria(id) ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 5. MANDATE — le mandat de recherche confié à un chasseur
-- ----------------------------------------------------------------------------
CREATE TABLE mandate (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at           TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    reference            VARCHAR(20) NOT NULL UNIQUE,
    status               VARCHAR(20) NOT NULL CHECK (status IN ('active', 'completed', 'expired', 'renewed', 'canceled')),
    signature_date       DATE,
    signature_type       VARCHAR(20) CHECK (signature_type IN ('electronic', 'paper')),
    ends_at              DATE NOT NULL,
    is_client_signed     BOOLEAN NOT NULL DEFAULT FALSE,
    is_exclusive         BOOLEAN NOT NULL,
    id_hunter            INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_client            INTEGER NOT NULL REFERENCES client(id_user) ON DELETE RESTRICT,
    id_search_request    INTEGER NOT NULL REFERENCES search_request(id) ON DELETE RESTRICT,
    id_mandate_parent    INTEGER REFERENCES mandate(id) ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 6. ESTATE — les biens immobiliers (annonces)
-- ----------------------------------------------------------------------------
CREATE TABLE estate (
    id                      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at              TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    reference               VARCHAR(50) NOT NULL UNIQUE,
    -- Correction : parenthèse fermante manquante dans le CHECK du diagramme
    estate_type             VARCHAR(50) NOT NULL CHECK (estate_type IN (
                                 'Appartement', 'Maison', 'Studio', 'Loft', 'Villa',
                                 'Duplex', 'Terrain', 'Local commercial', 'Chalet', 'Château'
                             )),
    price                   NUMERIC(6,1) CHECK (price >= 0),
    construction_date       DATE,
    latitude                NUMERIC(9,6) CHECK (latitude BETWEEN -90 AND 90),
    longitude               NUMERIC(9,6) CHECK (longitude BETWEEN -180 AND 180),
    nb_floors               SMALLINT,
    nb_rooms                SMALLINT,
    nb_bedrooms             SMALLINT,
    nb_bathrooms            SMALLINT,
    nb_toilets              SMALLINT,
    nb_swimming_pool        SMALLINT,
    has_garden              BOOLEAN,
    nb_balcony              INTEGER CHECK (nb_balcony >= 0),
    nb_terrace              INTEGER CHECK (nb_terrace >= 0),
    is_climatised           BOOLEAN,
    energetic_score         INTEGER CHECK (energetic_score > 0),
    surface                 NUMERIC(7,2) NOT NULL CHECK (surface > 0),
    land_surface            NUMERIC(9,2) CHECK (land_surface >= 0),
    has_cellar              BOOLEAN
    has_view                BOOLEAN
    is_quiet                BOOLEAN
    is_bright               BOOLEAN
    has_garage              BOOLEAN,
    has_elevator            BOOLEAN,
    has_chimney             BOOLEAN,
    parking_spaces          SMALLINT,
    has_separate_kitchen    BOOLEAN,
    needs_renovation        BOOLEAN,
    town                    VARCHAR(100) NOT NULL,
    street                  VARCHAR(100),
    street_number           VARCHAR(10),
    postal_code             VARCHAR(10),
    information             TEXT CHECK (char_length(information) <= 2000)
);

-- ----------------------------------------------------------------------------
-- 7. ESTATE_PROPOSED — un bien proposé par un chasseur pour un mandat
-- ----------------------------------------------------------------------------
CREATE TABLE estate_proposed (
    id                    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at            TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    comment_hunter        TEXT CHECK (char_length(comment_hunter) <= 2000),
    comment_client        TEXT,
    amount_proposition    NUMERIC(6,1) CHECK (amount_proposition >= 0),
    is_accepted           BOOLEAN,
    id_hunter             INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_estate             INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    id_mandate            INTEGER NOT NULL REFERENCES mandate(id) ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 8. ESTATE_SEARCHREQUEST — table de jonction N:N + stockage des médias/avis
-- ----------------------------------------------------------------------------
CREATE TABLE estate_searchrequest (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at           TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    review_hunter        TEXT CHECK (char_length(review_hunter) <= 2000),
    media_url            TEXT,
    media_type           VARCHAR(10) NOT NULL CHECK (media_type IN ('audio', 'video')),
    id_estate            INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    id_search_request    INTEGER NOT NULL REFERENCES search_request(id) ON DELETE RESTRICT,
    id_hunter            INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 9. PICTURE — photos rattachées à un bien (table trouvée dans le diagramme,
--    initialement oubliée par erreur lors de la première génération)
-- ----------------------------------------------------------------------------
CREATE TABLE picture (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    url          TEXT,
    id_estate    INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT
);

COMMIT;
