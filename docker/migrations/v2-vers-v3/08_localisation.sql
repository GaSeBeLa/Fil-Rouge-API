-- =====================================================================
-- v2 → v3, LOT8 — Localisation : pays, codes postaux, secteurs
-- =====================================================================
--
-- POURQUOI ? Quatre cartes du registre md/questions-a-trancher-2026-10-02.md :
--
--   - Q-SCH-11 : le code postal des biens se contrôle par pays, comme sur
--     client et criteria. Les biens repris n'ont pas de pays : 'FR'
--     d'abord, puis le CHECK chk_estate_postal_code_format ;
--   - Q-SCH-12 : l'Eircode (Irlande) s'écrit sans espace, sur client et
--     criteria (confirmé par Jeff le 2026-10-07) ;
--   - Q-MIG-08 : les secteurs d'origine arrivent dans criteria (ville,
--     code postal, pays 'FR') ; une colonne district (quartier),
--     facultative, sur criteria et estate ;
--   - Q-MIG-09 : budget_min à NULL, « inconnu », sur les 17 critères
--     repris : la source n'avait qu'un budget, recopié dans le minimum.
--
-- AVANT D'ACTIVER, compté le 2026-10-07 en base de dev : 2 556 biens,
--   tous 'AN-…', 2 556 codes postaux à 5 chiffres, 0 pays renseigné ;
--   0 client et 0 critère en Irlande. Une base qui a eu d'autres données
--   depuis est protégée ainsi :
--   - un bien qui n'est pas repris du CSV ('AN-…'), avec un code postal
--     mais sans pays : on ne devine pas son pays, la migration s'arrête
--     avant ;
--   - un code postal qui ne respecte pas le format de son pays : l'ajout
--     du CHECK échoue, et tout est annulé (Q-JEF-26, aucune ancienne
--     donnée supprimée).
--   Un Eircode avec espace n'est pas une erreur : il perd son espace.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   07_personnes.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/08_localisation.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Ne sont
--   complétés que les biens 'AN-…' sans pays, les Eircode avec espace, et
--   les 17 critères repris (version d'origine, sans lieu) ; aucune ligne
--   n'est supprimée.
-- =====================================================================

BEGIN;

-- Q-SCH-11 : le pays des biens repris du CSV (tous français).
UPDATE estate SET country_iso = 'FR'
WHERE country_iso IS NULL AND reference LIKE 'AN-%';

-- Garde : un autre bien avec un code postal mais sans pays.
DO $$
DECLARE
    n_sans_pays INTEGER;
BEGIN
    SELECT count(*) INTO n_sans_pays FROM estate
    WHERE postal_code IS NOT NULL AND country_iso IS NULL;
    IF n_sans_pays > 0 THEN
        RAISE EXCEPTION 'LOT8 : % bien(s) avec un code postal mais sans pays. '
            'Renseigner leur pays avant de migrer (Q-SCH-11).', n_sans_pays;
    END IF;
END $$;

-- Q-SCH-11 : le format par pays (règle détaillée dans init-v3/01).
ALTER TABLE estate DROP CONSTRAINT IF EXISTS chk_estate_postal_code_format;
ALTER TABLE estate ADD CONSTRAINT chk_estate_postal_code_format
    CHECK (postal_code IS NULL OR CASE
        WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
        WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
        WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
        WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
        WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
        WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W)[0-9AC-FHKNPRTV-Y]{4}$'
        ELSE FALSE END);

-- Q-SCH-12 : l'Eircode sans espace. L'ancien CHECK sort d'abord : il
-- refuserait le code une fois l'espace retiré.
ALTER TABLE client DROP CONSTRAINT IF EXISTS ck_client_postal_code_format;
UPDATE client SET postal_code = replace(postal_code, ' ', '')
WHERE country_iso = 'IE' AND postal_code LIKE '% %';
ALTER TABLE client ADD CONSTRAINT ck_client_postal_code_format
    CHECK (postal_code IS NULL OR CASE
        WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
        WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
        WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
        WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
        WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
        WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W)[0-9AC-FHKNPRTV-Y]{4}$'
        ELSE FALSE END);

ALTER TABLE criteria DROP CONSTRAINT IF EXISTS chk_postal_code_format;
UPDATE criteria SET postal_code = replace(postal_code, ' ', '')
WHERE country_iso = 'IE' AND postal_code LIKE '% %';
ALTER TABLE criteria ADD CONSTRAINT chk_postal_code_format
    CHECK (postal_code IS NULL OR CASE
        WHEN country_iso IN ('FR','ES','DE','IT') THEN postal_code ~ '^[0-9]{5}$'
        WHEN country_iso IN ('BE','CH')           THEN postal_code ~ '^[1-9][0-9]{3}$'
        WHEN country_iso = 'LU'                   THEN postal_code ~ '^[0-9]{4}$'
        WHEN country_iso = 'NL'                   THEN postal_code ~ '^[1-9][0-9]{3} [A-Z]{2}$'
        WHEN country_iso = 'GB'                   THEN postal_code ~ '^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$'
        WHEN country_iso = 'IE'                   THEN postal_code ~ '^([AC-FHKNPRTV-Y][0-9]{2}|D6W)[0-9AC-FHKNPRTV-Y]{4}$'
        ELSE FALSE END);

-- Q-MIG-08 : le quartier, facultatif (CHECK en ligne, nommé
-- criteria_district_check et estate_district_check, comme dans init-v3/01).
ALTER TABLE criteria ADD COLUMN IF NOT EXISTS
    district VARCHAR(100) CHECK (district = btrim(district) AND district <> '');
ALTER TABLE estate ADD COLUMN IF NOT EXISTS
    district VARCHAR(100) CHECK (district = btrim(district) AND district <> '');

-- Q-MIG-08, Q-MIG-09 : le secteur du mandat d'origine (secteurs
-- PgSQL.sql:41-51, mandats :135-159 ; le mandat 13 n'a pas été repris),
-- et budget_min vidé là où il recopiait budget_max. Seule la version
-- d'origine d'un critère sans lieu est touchée : une seconde passe ne
-- trouve plus rien.
UPDATE criteria c
SET country_iso = 'FR',
    town        = s.town,
    postal_code = s.postal_code,
    district    = s.district,
    budget_min  = CASE WHEN c.budget_min = c.budget_max THEN NULL ELSE c.budget_min END
FROM (VALUES
    ( 1, 'Montpellier',      '34000', 'Écusson'),
    ( 2, 'Lyon',             '69004', 'Croix-Rousse'),
    ( 3, 'Montpellier',      '34090', 'Beaux-Arts'),
    ( 4, 'Nantes',           '44200', 'Île de Nantes'),
    ( 5, 'Montpellier',      '34000', 'Port Marianne'),
    ( 6, 'Castelnau-le-Lez', '34170', NULL),
    ( 7, 'Lyon',             '69002', 'Confluence'),
    ( 8, 'Montpellier',      '34000', 'Écusson'),
    ( 9, 'Sète',             '34200', 'Centre'),
    (10, 'Lattes',           '34970', NULL),
    (11, 'Montpellier',      '34000', 'Port Marianne'),
    (12, 'Nantes',           '44200', 'Île de Nantes'),
    (14, 'Lyon',             '69002', 'Confluence'),
    (15, 'Montpellier',      '34000', 'Écusson'),
    (16, 'Sète',             '34200', 'Centre'),
    (17, 'Montpellier',      '34090', 'Beaux-Arts'),
    (18, 'Castelnau-le-Lez', '34170', NULL)
) AS s (id_search_request, town, postal_code, district)
WHERE c.id_search_request = s.id_search_request
  AND c.id_previous_version IS NULL
  AND c.country_iso IS NULL AND c.town IS NULL AND c.postal_code IS NULL;

COMMIT;
