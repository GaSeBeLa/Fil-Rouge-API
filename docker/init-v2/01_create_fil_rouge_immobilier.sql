-- ============================================================================
-- 01_create_fil_rouge_immobilier.sql
-- Schéma cible "Fil_Rouge_Immobilier" — 18 tables
-- Généré depuis « MPD 03 .drawio.xml » (2026-09-21)
--
-- VERSION FUSIONNÉE des deux scripts écrits en parallèle par le groupe.
-- Testé sur PostgreSQL 16 : création complète sur base vierge, sans erreur.
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
--      le même pays de deux façons incompatibles. HARMONISÉ AVEC L'ESPACE,
--      qui est le format officiel Eircode. ⚠️ À VALIDER par le groupe : si la
--      saisie se fait sans espace, c'est client qu'il faut aligner, pas criteria.
--
-- ============================================================================
-- ⚠️ CONVENTION D'UNITÉ MONÉTAIRE — CHANGEMENT MAJEUR, À LIRE EN ENTIER
-- ============================================================================
--
--   TOUS les montants sont en EUROS, type NUMERIC(12,2).
--   La convention « milliers d'euros » (K€, NUMERIC(6,1)) des versions
--   précédentes est ABANDONNÉE. Un bien à 354 700 € se stocke 354700.00.
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
--
--   Autrement dit : un schéma seul ne protège PAS la plupart des règles
--   métier. Elles croisent plusieurs tables et demandent des triggers ou
--   l'API. Les TODO ci-dessous portent le SQL prêt à activer.
--
--   Décisions encore ouvertes : D2 (ancienneté), D6 (priorité du client),
--   D7 (mandat annulé), D9 (deux scores le même jour), N2 (localisation :
--   ADR-009 place la localisation sur search_request, le MPD la met sur
--   criteria, ADR-021 ne tranche pas), R21 (bornage du taux final 20-60 %).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;  -- requis par les contraintes EXCLUDE

BEGIN;


-- ============================================================================
-- 1. IDENTITÉ ET RÔLES
-- ============================================================================

CREATE TABLE role (
    id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wording VARCHAR(20) NOT NULL UNIQUE
            CHECK (wording IN ('Admin', 'Client', 'Hunter', 'Manager'))
);

-- "user" est un mot réservé PostgreSQL : il reste quoté partout.
CREATE TABLE "user" (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    email        VARCHAR(150) NOT NULL UNIQUE,
    password     VARCHAR(255) NOT NULL,
    is_activated BOOLEAN,
    id_role      INTEGER NOT NULL REFERENCES role(id) ON DELETE RESTRICT
);


-- ============================================================================
-- 2. SOUS-TYPES D'UTILISATEUR
-- ============================================================================
-- TODO (cohérence) : client, hunter, real_estate_manager et role sont les
-- seules tables du schéma sans created_at. Omission du MPD ou choix ? À acter.

CREATE TABLE client (
    id                       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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

    CONSTRAINT ck_client_marital_status_exclusive
        CHECK (NOT (is_married AND is_civil_solidarity_pact)),
    CONSTRAINT ck_client_address_all_or_nothing
        CHECK ((address IS NULL     AND postal_code IS NULL     AND town IS NULL)
            OR (address IS NOT NULL AND postal_code IS NOT NULL AND town IS NOT NULL)),
    CONSTRAINT ck_client_postal_code_needs_country
        CHECK (postal_code IS NULL OR country_iso IS NOT NULL),
    -- Correction 8 : format IE avec espace, identique à criteria.
    CONSTRAINT ck_client_postal_code_format
        CHECK (postal_code IS NULL OR CASE
            WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
            WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
            WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
            WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
            WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
            WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W) [0-9AC-FHKNPRTV-Y]{4}$'
            ELSE FALSE END)
);

CREATE TABLE hunter (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_user            INTEGER NOT NULL UNIQUE
                       REFERENCES "user"(id) ON DELETE RESTRICT,
    first_name         VARCHAR(80) NOT NULL
                       CHECK (first_name = btrim(first_name) AND first_name <> ''),
    last_name          VARCHAR(80) NOT NULL
                       CHECK (last_name = btrim(last_name) AND last_name <> ''),
    phone_number       VARCHAR(20) NOT NULL
                       CHECK (phone_number = btrim(phone_number) AND phone_number <> ''),
    country_iso        CHAR(2)
                       CHECK (country_iso IN ('FR','ES','DE','GB','IE','BE','NL','LU','IT','CH')),
    gender             VARCHAR(10)
                       CHECK (gender IN ('male', 'female', 'other')),
    company_name       VARCHAR(80)
                       CHECK (company_name = btrim(company_name) AND company_name <> ''),
    hire_date          DATE NOT NULL CHECK (hire_date <= CURRENT_DATE),
    education_level    VARCHAR(20)
                       CHECK (education_level = btrim(education_level) AND education_level <> ''),
    -- Nom repris tel quel du MPD. Désigne vraisemblablement la « carte T »
    -- (carte professionnelle d'agent immobilier) : is_carte_t serait plus
    -- clair, mais le renommage toucherait l'API — à acter avant de bouger.
    is_cartet          BOOLEAN,
    certification_date DATE,
    -- Non quoté : PostgreSQL le replie en minuscules -> is_hunter_ai.
    is_hunter_ai       BOOLEAN
);

CREATE TABLE real_estate_manager (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
                 CHECK (company_name = btrim(company_name) AND company_name <> '')
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

    -- Localisation. TODO (N2) : l'ADR-009 (accepté) place la localisation sur
    -- search_request via des FK id_town / id_area ; le MPD la met ici en texte ;
    -- l'ADR-021 ne tranche pas. Le schéma suit le MPD. À arbitrer.
    country_iso            CHAR(2)
                           CHECK (country_iso IN ('FR','ES','DE','GB','IE','BE','NL','LU','IT','CH')),
    town                   VARCHAR(100)
                           CHECK (town = btrim(town) AND town <> ''),
    postal_code            VARCHAR(10),

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
    budget_min             NUMERIC(12,2) CHECK (budget_min > 0),
    budget_max             NUMERIC(12,2) NOT NULL CHECK (budget_max > 0),

    floor                  VARCHAR(10)
                           CHECK (floor IN ('0','1','2','3','4','5','6','7','8','9',
                                            '10 and more','last floor')),
    is_new_build           BOOLEAN,
    needs_renovation       BOOLEAN,
    renovation_budget_min  NUMERIC(12,2) CHECK (renovation_budget_min >= 0),
    renovation_budget_max  NUMERIC(12,2) CHECK (renovation_budget_max >= 0),
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
    CONSTRAINT chk_postal_code_needs_country
        CHECK (postal_code IS NULL OR country_iso IS NOT NULL),
    -- Corrections 1 et 8 : parenthèse en trop retirée, format IE avec espace.
    CONSTRAINT chk_postal_code_format
        CHECK (postal_code IS NULL OR CASE
            WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
            WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
            WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
            WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
            WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
            WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W) [0-9AC-FHKNPRTV-Y]{4}$'
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
    status            VARCHAR(20) NOT NULL
                      CHECK (status IN ('active', 'completed', 'expired',
                                        'renewed', 'canceled', 'pending_signature')),
    signature_date    DATE,
    signature_type    VARCHAR(20) CHECK (signature_type IN ('electronic', 'paper')),
    -- Date de fin STOCKÉE : décision N1 du 11/09/26 (option A), qui écarte
    -- l'ADR-004 (durée calculée) au profit de l'ADR-018 (figer la date).
    ends_at           DATE
                      CHECK ((signature_date IS NULL     AND ends_at IS NULL)
                          OR (signature_date IS NOT NULL AND ends_at > signature_date)),
    is_client_signed  BOOLEAN NOT NULL DEFAULT FALSE,
    is_exclusive      BOOLEAN NOT NULL,
    id_hunter         INTEGER NOT NULL
                      REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_client         INTEGER NOT NULL
                      REFERENCES client(id_user) ON DELETE RESTRICT,
    id_search_request INTEGER NOT NULL
                      REFERENCES search_request(id) ON DELETE RESTRICT,
    -- Relation réflexive : renouvellements (ADR-010) ET avenants (ADR-013).
    id_mandate_parent INTEGER REFERENCES mandate(id) ON DELETE RESTRICT,

    -- Correction 4 : la virgule manquait ici dans le diagramme.
    -- ADR-010 + ADR-013 : 'renewed' désigne le NOUVEAU mandat (décision D8).
    CONSTRAINT chk_renewed
        CHECK (status <> 'renewed' OR id_mandate_parent IS NOT NULL),
    CONSTRAINT chk_status_signature
        CHECK ((status =  'pending_signature' AND signature_date IS NULL)
            OR (status <> 'pending_signature' AND signature_date IS NOT NULL))

    -- ------------------------------------------------------------------
    -- TODO (U05) — durée de validité de EXACTEMENT 6 mois
    --   Le CHECK de ends_at ci-dessus n'impose que l'ordre des dates : un
    --   mandat peut durer 10 ans ou 1 jour (les deux cas sont acceptés, testé).
    --   Règle : 00_regles_metier_mandat_remuneration.feature:37, exemple l. 39
    --   (signature 2026-02-25 -> fin 2026-08-25).
    --   Pour activer : retirer le CHECK de ends_at et poser à la place
    -- , CONSTRAINT chk_mandate_six_months
    --     CHECK ((signature_date IS NULL AND ends_at IS NULL)
    --         OR (signature_date IS NOT NULL
    --             AND ends_at = (signature_date + INTERVAL '6 months')::date))
    --   Vérifié : fait passer 2 tests adverses de LACUNE à ok.
    -- ------------------------------------------------------------------
);

-- ----------------------------------------------------------------------------
-- TODO (U02 / décision D7) — EXCLUSIVITÉ DU MANDAT
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
--   Décision D7 à trancher avant d'activer : un mandat 'canceled' libère-t-il
--   le client tout de suite (garder la ligne status <> 'canceled'), ou
--   bloque-t-il jusqu'à ends_at (la retirer) ?
--
--   L'ERRCODE 23514 est volontaire : il range le refus dans la classe 23
--   (violation d'intégrité), que le harnais de tests adverses reconnaît.
--
-- CREATE OR REPLACE FUNCTION check_mandate_exclusivity() RETURNS trigger
-- LANGUAGE plpgsql AS $fn$
-- BEGIN
--     IF NEW.signature_date IS NULL OR NEW.ends_at IS NULL THEN
--         RETURN NEW;                       -- mandat pas encore signé
--     END IF;
--     IF EXISTS (
--         SELECT 1 FROM mandate m
--          WHERE m.id        <> NEW.id
--            AND m.id_client  = NEW.id_client
--            AND m.status    <> 'canceled'
--            AND (m.is_exclusive OR NEW.is_exclusive)
--            AND m.signature_date IS NOT NULL AND m.ends_at IS NOT NULL
--            AND daterange(m.signature_date, m.ends_at, '[]')
--             && daterange(NEW.signature_date, NEW.ends_at, '[]')
--     ) THEN
--         RAISE EXCEPTION
--             'U02 : un mandat exclusif interdit tout autre mandat pour ce client sur la periode'
--             USING ERRCODE = '23514', CONSTRAINT = 'u02_mandate_exclusivity';
--     END IF;
--     RETURN NEW;
-- END $fn$;
--
-- CREATE TRIGGER trg_mandate_exclusivity
--     BEFORE INSERT OR UPDATE ON mandate
--     FOR EACH ROW EXECUTE FUNCTION check_mandate_exclusivity();
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
    price                NUMERIC(12,2) CHECK (price >= 0),
    construction_date    DATE,
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
    -- TODO (cohérence) : client et criteria valident le format du code postal
    -- par pays, pas estate. Volontaire (données scrapées, moins fiables) ou
    -- oubli ? À acter avant de dupliquer le CASE ici.
    postal_code          VARCHAR(10)
                         CHECK (postal_code = btrim(postal_code) AND postal_code <> ''),
    information          TEXT CHECK (char_length(information) <= 2000)
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
    media_url         TEXT,
    media_type        VARCHAR(10) CHECK (media_type IN ('audio', 'video')),
    id_estate         INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    id_search_request INTEGER NOT NULL REFERENCES search_request(id) ON DELETE RESTRICT,
    id_hunter         INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,

    CONSTRAINT chk_media
        CHECK ((media_url IS NULL     AND media_type IS NULL)
            OR (media_url IS NOT NULL AND media_type IS NOT NULL)),
    CONSTRAINT uq_estate_search UNIQUE (id_estate, id_search_request)
);

-- Biens effectivement proposés au client, et suivi de l'offre.
CREATE TABLE estate_proposed (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at         TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    comment_hunter     TEXT CHECK (char_length(comment_hunter) <= 2000),
    comment_client     TEXT,
    -- Euros.
    amount_proposition NUMERIC(12,2) CHECK (amount_proposition >= 0),
    proposition_status VARCHAR(20) NOT NULL
                       CHECK (proposition_status IN ('proposed', 'offer_pending',
                                                     'accepted', 'rejected')),
    id_hunter          INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_estate          INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    id_mandate         INTEGER NOT NULL REFERENCES mandate(id) ON DELETE RESTRICT,

    -- Correction 2 : cette contrainte figurait EN DOUBLE dans le diagramme.
    -- Un bien seulement « proposé » n'a pas de montant ; dès qu'il quitte cet
    -- état, le montant devient obligatoire.
    CONSTRAINT chk_offer
        CHECK ((proposition_status =  'proposed' AND amount_proposition IS NULL)
            OR (proposition_status <> 'proposed' AND amount_proposition IS NOT NULL))

    -- TODO (décision D6) — priorité donnée par le client à un bien proposé.
    --   L'échelle n'est pas tranchée (1 à 5 ? haute/moyenne/basse ?), donc la
    --   colonne manque au schéma. Une fois décidé :
    -- , client_priority SMALLINT CHECK (client_priority BETWEEN 1 AND 5)
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
    --   est acceptée aujourd'hui. Croise deux tables -> trigger ou API.
);


-- ============================================================================
-- 7. VENTE ET RÉMUNÉRATION
-- ============================================================================

CREATE TABLE sale (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    signature_date  DATE NOT NULL,
    -- Euros. Prix d'acte : jusqu'à 800 000 dans les Gherkin officiels.
    purchase_amount NUMERIC(12,2) NOT NULL CHECK (purchase_amount > 0),
    -- Honoraires (l'assiette du calcul) : montant fixe + % du prix.
    fees_amount     NUMERIC(12,2) NOT NULL CHECK (fees_amount > 0),
    sale_origin     VARCHAR(20) NOT NULL
                    CHECK (sale_origin IN ('hunter', 'client_alone')),
    id_mandate      INTEGER NOT NULL UNIQUE REFERENCES mandate(id) ON DELETE RESTRICT,
    id_estate       INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,

    CONSTRAINT chk_fees_lower_than_price CHECK (fees_amount < purchase_amount)

    -- TODO (déroulé 01 -> 03) — la vente doit tomber DANS la validité du
    --   mandat, et le mandat doit être signé. Testé : une vente datée 2025 sur
    --   un mandat signé en 2026, une vente en 2030 sur un mandat clos en 2026,
    --   et une vente sur un mandat 'pending_signature' sont toutes acceptées.
    --   Croise sale et mandate -> trigger ou API.
    -- TODO (D3) — cas déjà tranché par les sources officielles : un acte signé
    --   APRÈS la fin du mandat peut ouvrir droit à rémunération sous condition
    --   (REGLES-CALCUL-REMUNERATION.md:98). La règle ci-dessus doit donc tenir
    --   compte de ce délai, et non refuser sèchement.
);

-- Paramètres d'honoraires, historisés (montant fixe + pourcentage du prix).
CREATE TABLE parameters_fees (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    valid_from   DATE NOT NULL,
    valid_until  DATE,
    -- Euros, au centime : la source officielle donne « 3000,00 ».
    fixed_amount NUMERIC(12,2) NOT NULL CHECK (fixed_amount > 0),
    rate         NUMERIC(5,4) NOT NULL CHECK (rate >= 0 AND rate <= 1),

    CONSTRAINT excl_fees_no_overlap
        EXCLUDE USING gist (daterange(valid_from, valid_until, '[]') WITH &&)
);

-- Barème de commission : tranches de prix -> taux de base.
-- id_hunter NULL = barème par défaut ; renseigné = barème propre au chasseur.
CREATE TABLE commission_scale (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at  TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    -- Euros : les tranches officielles montent à 750 000 et au-delà.
    amount_min  NUMERIC(12,2) NOT NULL CHECK (amount_min >= 0),
    amount_max  NUMERIC(12,2) CHECK (amount_max > amount_min),
    rate        NUMERIC(5,4) NOT NULL CHECK (rate >= 0 AND rate <= 1),
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
            numrange(amount_min, amount_max, '[)') WITH &&,
            daterange(valid_from, valid_until, '[]') WITH &&
        ),
    -- Idem pour le barème par défaut, que le précédent laisse passer (NULL
    -- n'est jamais égal à NULL, donc l'exclusion ne s'y applique pas).
    CONSTRAINT excl_scale_global
        EXCLUDE USING gist (
            numrange(amount_min, amount_max, '[)') WITH &&,
            daterange(valid_from, valid_until, '[]') WITH &&
        ) WHERE (id_hunter IS NULL)
);

CREATE TABLE payment (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at          TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    -- Euros, arrondi au centime au demi supérieur (règle officielle).
    amount              NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    status              VARCHAR(20) NOT NULL
                        CHECK (status IN ('announced', 'invoice_submitted',
                                          'verified', 'scheduled', 'paid')),
    paid_at             TIMESTAMP,
    -- Taux de tranche issu du barème.
    base_rate           NUMERIC(5,4) NOT NULL CHECK (base_rate > 0 AND base_rate <= 1),
    -- TODO (R21) — le taux final est borné entre 20 % et 60 % par la règle
    --   officielle (10_calcul_remuneration_chasseur.feature:201 ; exemples
    --   l. 236-250 : 65 % ramené à 60 %, 17,60 % remonté à 20 %).
    --   Le CHECK ci-dessous accepte tout entre 0 et 1. À remplacer par :
    --       CHECK (final_rate BETWEEN 0.20 AND 0.60)
    --   L'en-tête du Gherkin précise que ces bornes sont des paramètres
    --   « proposés, non imposés » : d'où la prudence, mais la règle de bornage,
    --   elle, est bien métier.
    final_rate          NUMERIC(5,4) CHECK (final_rate > 0 AND final_rate <= 1),
    -- Majoration d'ancienneté, modulation de performance (décision D2).
    seniority_rate      NUMERIC(5,4) NOT NULL CHECK (seniority_rate BETWEEN 0 AND 0.10),
    performance_rate    NUMERIC(5,4) NOT NULL CHECK (performance_rate BETWEEN -0.20 AND 0.20),
    id_sale             INTEGER NOT NULL UNIQUE REFERENCES sale(id) ON DELETE RESTRICT,
    id_hunter           INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_commission_scale INTEGER NOT NULL REFERENCES commission_scale(id) ON DELETE RESTRICT,

    CONSTRAINT chk_paid
        CHECK ((status =  'paid' AND paid_at IS NOT NULL)
            OR (status <> 'paid' AND paid_at IS NULL))

    -- TODO (U01/U04, R01-R04, T17) — le droit à être payé n'est pas vérifié :
    --   testé, on peut aujourd'hui payer un chasseur qui n'est PAS celui du
    --   mandat de la vente, et rattacher le paiement à un barème qui n'était
    --   pas en vigueur à la date de l'acte. Croise payment, sale, mandate et
    --   commission_scale -> trigger à la création du paiement, ou API.
);

-- Score de performance du chasseur, historisé par période.
CREATE TABLE hunter_performance (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    score        NUMERIC(4,1) NOT NULL CHECK (score BETWEEN 0 AND 100),
    valid_from   DATE NOT NULL,
    valid_until  DATE,
    trigger_type VARCHAR(20) NOT NULL
                 CHECK (trigger_type IN ('initial', 'payment', 'mandate_expired')),
    id_hunter    INTEGER NOT NULL REFERENCES hunter(id_user) ON DELETE RESTRICT,
    id_payment   INTEGER REFERENCES payment(id) ON DELETE RESTRICT,
    id_mandate   INTEGER REFERENCES mandate(id) ON DELETE RESTRICT,

    CONSTRAINT chk_perf_period
        CHECK (valid_until IS NULL OR valid_until > valid_from),
    -- Chaque type de déclencheur impose sa source, et interdit l'autre.
    CONSTRAINT chk_perf_source
        CHECK ((trigger_type = 'payment'         AND id_payment IS NOT NULL AND id_mandate IS NULL)
            OR (trigger_type = 'mandate_expired' AND id_mandate IS NOT NULL AND id_payment IS NULL)
            OR (trigger_type = 'initial'         AND id_payment IS NULL     AND id_mandate IS NULL)),
    -- TODO (décision D9) — les bornes sont inclusives '[]', donc deux scores
    --   d'un même chasseur le MÊME JOUR sont refusés : il faut au moins un
    --   jour d'écart. Si le métier veut l'autoriser, passer en '[)'.
    CONSTRAINT excl_perf_no_overlap
        EXCLUDE USING gist (
            id_hunter WITH =,
            daterange(valid_from, valid_until, '[]') WITH &&
        )
);


-- ============================================================================
-- MÉTADONNÉES — lisibles par les clients SQL et les ORM
-- ============================================================================

-- Unité monétaire : tout est en euros.
COMMENT ON COLUMN criteria.budget_min IS
  'Budget minimum en EUROS, NUMERIC(12,2). Ex: 250000.00 = 250 000 EUR.';
COMMENT ON COLUMN criteria.budget_max IS
  'Budget maximum en EUROS, NUMERIC(12,2).';
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
  'Borne basse de la tranche en EUROS, bornee [min, max[. Ex: 200000.00.';
COMMENT ON COLUMN commission_scale.amount_max IS
  'Borne haute (exclue) de la tranche en EUROS ; NULL = sans plafond.';
COMMENT ON COLUMN parameters_fees.fixed_amount IS
  'Part fixe des honoraires en EUROS. Source officielle : 3000,00.';
COMMENT ON COLUMN payment.amount IS
  'Montant verse au chasseur en EUROS, arrondi au centime au demi superieur.';

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
  'Reference real_estate_manager(id_user) — donc un id de "user".';
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
-- FIN — 18 tables, 224 colonnes, 1 extension.
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
