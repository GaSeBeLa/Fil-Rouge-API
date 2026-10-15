-- =====================================================================
-- v2 → v3, chantier FLX (FLX5) — le schéma olap, en étoile
-- =====================================================================
--
-- POURQUOI ? Le sujet demande une base d'analyse à côté de l'OLTP
--   (documents utiles/OLAP.md) : une table de faits, fait_ventes, et cinq
--   dimensions. Question flux-13, tranchée A par Seb le 2026-10-15.
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant FLX5. Une
--   base créée par init-v3 après FLX5 a déjà le schéma
--   (docker/init-v3/08_olap.sql) : le script ne fait rien.
--
-- QUOI ? Le schéma olap et ses 6 tables, vides : le DAG olap_refresh les
--   remplit (FLX6). D'où vient chaque mesure, et la règle RGPD : en-tête
--   de docker/init-v3/08_olap.sql. Le rôle fil_rouge_reader ne lit pas
--   olap (la commission vient de payment, fermé par la migration 43).
--
-- SOURCE : docker/init-v3/08_olap.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare les deux bases.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/49_schema-olap.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/49_schema-olap.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction ; rejouable. Retour en arrière :
--   DROP SCHEMA olap CASCADE (les faits sont perdus ; FLX6 les recalcule).
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS olap;

CREATE TABLE IF NOT EXISTS olap.dim_temps (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    jour             DATE NOT NULL UNIQUE,
    annee            SMALLINT NOT NULL,
    trimestre        SMALLINT NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mois             SMALLINT NOT NULL CHECK (mois BETWEEN 1 AND 12),
    semaine_iso      SMALLINT NOT NULL CHECK (semaine_iso BETWEEN 1 AND 53),
    jour_semaine_iso SMALLINT NOT NULL CHECK (jour_semaine_iso BETWEEN 1 AND 7)
);

CREATE TABLE IF NOT EXISTS olap.dim_chasseur (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_hunter      INTEGER NOT NULL UNIQUE,   -- hunter.id
    annee_embauche SMALLINT NOT NULL,         -- année de hunter.hire_date
    est_ia         BOOLEAN,                   -- hunter.is_hunter_ai
    a_carte_t      BOOLEAN,                   -- hunter.is_carte_t
    pays           CHAR(2)                    -- hunter.country_iso
);

CREATE TABLE IF NOT EXISTS olap.dim_client (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_client         INTEGER NOT NULL UNIQUE,  -- client.id
    annee_inscription SMALLINT NOT NULL,        -- année de client.created_at
    ville             VARCHAR(100) NOT NULL,    -- client.town
    pays              CHAR(2) NOT NULL          -- client.country_iso
);

CREATE TABLE IF NOT EXISTS olap.dim_bien (
    id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_estate          INTEGER NOT NULL UNIQUE,  -- estate.id
    type_bien          VARCHAR(50) NOT NULL,     -- estate.estate_type
    typologie          VARCHAR(50),              -- estate.typology
    surface            NUMERIC(7,2) NOT NULL,    -- estate.surface
    nb_pieces          SMALLINT,                 -- estate.nb_rooms
    classe_energie     CHAR(1),                  -- estate.energy_class
    annee_construction SMALLINT,                 -- année de estate.construction_date
    est_importe        BOOLEAN NOT NULL          -- estate.id_author IS NULL (ADR-047)
);

CREATE TABLE IF NOT EXISTS olap.dim_secteur (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pays        CHAR(2),                  -- estate.country_iso
    code_postal VARCHAR(10),              -- estate.postal_code
    ville       VARCHAR(100) NOT NULL,    -- estate.town
    -- Un lieu, une ligne ; un pays ou un code postal vide compte comme une
    -- valeur (NULLS NOT DISTINCT, PostgreSQL 15 et plus).
    CONSTRAINT uq_dim_secteur_lieu UNIQUE NULLS NOT DISTINCT (pays, code_postal, ville)
);

CREATE TABLE IF NOT EXISTS olap.fait_ventes (
    id                     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_sale                INTEGER NOT NULL UNIQUE,  -- sale.id, clé naturelle : un rejeu ne double rien
    fk_temps               INTEGER NOT NULL REFERENCES olap.dim_temps(id) ON DELETE RESTRICT,
    fk_chasseur            INTEGER NOT NULL REFERENCES olap.dim_chasseur(id) ON DELETE RESTRICT,
    fk_client              INTEGER NOT NULL REFERENCES olap.dim_client(id) ON DELETE RESTRICT,
    fk_bien                INTEGER NOT NULL REFERENCES olap.dim_bien(id) ON DELETE RESTRICT,
    fk_secteur             INTEGER NOT NULL REFERENCES olap.dim_secteur(id) ON DELETE RESTRICT,
    montant_bien           INTEGER NOT NULL CHECK (montant_bien > 0),
    honoraires             NUMERIC(12,2) NOT NULL CHECK (honoraires > 0),
    commission_chasseur    NUMERIC(12,2) CHECK (commission_chasseur >= 0),
    nb_visites_avant_achat INTEGER NOT NULL CHECK (nb_visites_avant_achat >= 0),
    delai_semaines         INTEGER CHECK (delai_semaines >= 0),
    mandat_exclusif        BOOLEAN NOT NULL
);

COMMIT;
