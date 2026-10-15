-- ============================================================================
-- 08_olap.sql — le schéma olap, en étoile (chantier FLX, fiche FLX5)
-- ============================================================================
--
-- Le modèle du sujet (StarterPack - BASE, documents utiles/OLAP.md) : une
-- table de faits, fait_ventes, et cinq dimensions. Décision de Seb du
-- 2026-10-15 (question flux-13, tranchée A) : l'étoile du sujet, dans un
-- schéma olap de la base fil_rouge_immobilier, sans aucune donnée qui
-- désigne une personne. Les noms de tables et de mesures sont ceux du
-- sujet, en français, pour que le schéma se lise à côté de OLAP.md.
--
-- Grain : une ligne de fait_ventes = une vente (une ligne de sale).
-- Rempli chaque nuit par le DAG olap_refresh (fiche FLX6) ; ici, les tables
-- naissent vides.
--
-- ----------------------------------------------------------------------------
-- D'OÙ VIENT CHAQUE MESURE — colonne olap -> colonne OLTP -> calcul
-- ----------------------------------------------------------------------------
--
--   montant_bien           <- sale.purchase_amount
--                             tel quel, euros entiers (INTEGER, règle 4)
--   honoraires             <- sale.fees_amount
--                             tel quel, au centime (NUMERIC(12,2))
--   commission_chasseur    <- payment.amount (payment.id_sale = sale.id)
--                             tel quel, au centime ; 0.00 sur un paiement
--                             refusé (ADR-024) ; NULL tant que la vente n'a
--                             pas encore de paiement
--   nb_visites_avant_achat <- visit, compté
--                             visites 'client' des mandats de la chaîne du
--                             mandat de la vente, datées au plus tard le jour
--                             de l'acte — la règle du calcul de rémunération
--                             (payment_calculation_service.py, ADR-048
--                             point 4, ADR-053)
--   delai_semaines         <- sale.signature_date et mandate.signature_date
--                             (date de l'acte - signature du mandat RACINE de
--                             la chaîne, ADR-050) / 7, arrondi vers le bas,
--                             comme l'exemple de OLAP.md ; NULL si cette
--                             signature manque
--   mandat_exclusif        <- mandate.is_exclusive (le mandat de la vente)
--
--   Aucune mesure sans source : les six du sujet ont la leur.
--
-- ----------------------------------------------------------------------------
-- LES DIMENSIONS — clé de substitution id, clé naturelle id_<table OLTP>
-- ----------------------------------------------------------------------------
--
--   dim_temps     un jour (le jour de l'acte, sale.signature_date)
--   dim_chasseur  un chasseur (hunter)  : année d'embauche, IA ou non, carte T, pays
--   dim_client    un client (client)    : année d'inscription, ville, pays
--   dim_bien      un bien (estate)      : type, typologie, surface, pièces, DPE,
--                                         année de construction, importé ou saisi
--   dim_secteur   un lieu (estate)      : pays, code postal, ville
--
--   RGPD (flux-13) : les dimensions des personnes n'ont que des numéros et
--   des attributs non identifiants. Aucun prénom, nom de famille, adresse
--   électronique, numéro d'appel, ni adresse postale, ni date de
--   naissance. Le bien n'a ni rue ni numéro de rue.
--
-- ----------------------------------------------------------------------------
-- CARDINALITÉS — chaque dimension (1,1) — (0,n) fait_ventes
-- ----------------------------------------------------------------------------
--
--   Une vente a un jour, un chasseur, un client, un bien et un secteur ;
--   chacun d'eux a zéro, une ou plusieurs ventes. Un bien n'est vendu
--   qu'une fois (sale.uq_sale_estate) : dim_bien (1,1) — (0,1) en pratique.
--
-- DROITS : le rôle fil_rouge_reader ne lit PAS olap. commission_chasseur
--   vient de payment, que la migration 43 lui a retiré ; lui ouvrir olap
--   rouvrirait ce montant. À trancher plus tard, s'il faut un lecteur.
--
-- Jumelle : docker/migrations/v2-vers-v3/49_schema-olap.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare tous les schémas.
-- ============================================================================

BEGIN;

CREATE SCHEMA olap;

CREATE TABLE olap.dim_temps (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    jour             DATE NOT NULL UNIQUE,
    annee            SMALLINT NOT NULL,
    trimestre        SMALLINT NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mois             SMALLINT NOT NULL CHECK (mois BETWEEN 1 AND 12),
    semaine_iso      SMALLINT NOT NULL CHECK (semaine_iso BETWEEN 1 AND 53),
    jour_semaine_iso SMALLINT NOT NULL CHECK (jour_semaine_iso BETWEEN 1 AND 7)
);

CREATE TABLE olap.dim_chasseur (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_hunter      INTEGER NOT NULL UNIQUE,   -- hunter.id
    annee_embauche SMALLINT NOT NULL,         -- année de hunter.hire_date
    est_ia         BOOLEAN,                   -- hunter.is_hunter_ai
    a_carte_t      BOOLEAN,                   -- hunter.is_carte_t
    pays           CHAR(2)                    -- hunter.country_iso
);

CREATE TABLE olap.dim_client (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_client         INTEGER NOT NULL UNIQUE,  -- client.id
    annee_inscription SMALLINT NOT NULL,        -- année de client.created_at
    ville             VARCHAR(100) NOT NULL,    -- client.town
    pays              CHAR(2) NOT NULL          -- client.country_iso
);

CREATE TABLE olap.dim_bien (
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

CREATE TABLE olap.dim_secteur (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pays        CHAR(2),                  -- estate.country_iso
    code_postal VARCHAR(10),              -- estate.postal_code
    ville       VARCHAR(100) NOT NULL,    -- estate.town
    -- Un lieu, une ligne ; un pays ou un code postal vide compte comme une
    -- valeur (NULLS NOT DISTINCT, PostgreSQL 15 et plus).
    CONSTRAINT uq_dim_secteur_lieu UNIQUE NULLS NOT DISTINCT (pays, code_postal, ville)
);

CREATE TABLE olap.fait_ventes (
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
