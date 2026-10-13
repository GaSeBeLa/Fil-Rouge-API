-- =====================================================================
-- v2 → v3, après le chantier API — Le contact du vendeur d'un bien
-- =====================================================================
--
-- POURQUOI ? Le CSV des annonces donne, pour un bien, le nom, le
--   téléphone, l'email et l'agence du vendeur. normalised.py les nettoie,
--   mais aucune colonne ne les recevait : tout était perdu à l'import.
--   Décision du groupe du 2026-10-13 (ADR-054, option B : une table à
--   part, cachée au client), posée dans
--   docker/init-v3/01_create_fil_rouge_immobilier.sql :
--
--   - nouvelle table estate_contact (0 ou 1 ligne par bien) ;
--   - ses données viennent de docker/init-v3/06_populate_estate_contact.sql.
--
-- POUR QUI ? Seulement pour une base **déjà créée**. Une base neuve part
--   de docker/init-v3/, qui crée la table et la remplit. Le banc
--   `bash docker/compare_v2_v3.sh` vérifie que les deux chemins mènent au
--   même schéma.
--
-- COMMENT ? Depuis docker/, la table, puis ses données :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/40_contact-du-bien.sql
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < init-v3/06_populate_estate_contact.sql
--
-- SÛRETÉ : une transaction. Rejouable : la table n'est créée que si elle
--   manque. Aucune ligne existante n'est touchée.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS estate_contact (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    seller_type  VARCHAR(10) CHECK (seller_type IN ('private', 'agency')),
    agency_name  VARCHAR(100)
                 CHECK (agency_name = btrim(agency_name) AND agency_name <> ''),
    contact_name VARCHAR(100)
                 CHECK (contact_name = btrim(contact_name) AND contact_name <> ''),
    phone_number VARCHAR(20)
                 CHECK (phone_number ~ '^\+[1-9]([ -]?[0-9]){1,14}$'),
    email        VARCHAR(150)
                 CHECK (email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
    id_estate    INTEGER NOT NULL UNIQUE REFERENCES estate(id) ON DELETE RESTRICT,
    id_author    INTEGER REFERENCES "user"(id) ON DELETE RESTRICT,

    CONSTRAINT ck_estate_contact_not_empty
        CHECK (agency_name IS NOT NULL OR contact_name IS NOT NULL
            OR phone_number IS NOT NULL OR email IS NOT NULL)
);

COMMIT;
