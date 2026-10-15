-- =====================================================================
-- v2 → v3, chantier FLX (FLX4) — la table estate_price_history
-- =====================================================================
--
-- POURQUOI ? L'import d'annonces d'Airflow (DAG annonces_import) met à
--   jour estate.price quand une annonce revient avec un autre prix. Pour
--   ne pas perdre l'ancien, une ligne par bien et par jour vu (question
--   flux-12b, tranchée A par Seb le 2026-10-15 ; colonnes du MPD de
--   Gabriel, Discord, 2026-10-15).
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant FLX4. Une
--   base créée par init-v3 après FLX4 a déjà la table (docker/init-v3/01) :
--   le script ne fait rien.
--
-- QUOI ? CREATE TABLE IF NOT EXISTS estate_price_history, vide. Le rôle
--   fil_rouge_reader la lit par les droits par défaut de init-v3/04
--   (ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES).
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare les deux bases.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/48_historique-des-prix.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/48_historique-des-prix.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction ; rejouable. Retour en arrière :
--   DROP TABLE estate_price_history (l'historique est perdu).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS estate_price_history (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    id_estate  INTEGER NOT NULL REFERENCES estate(id) ON DELETE RESTRICT,
    price      INTEGER NOT NULL CHECK (price >= 0),
    seen_at    DATE NOT NULL,
    CONSTRAINT uq_estate_price_history_estate_seen UNIQUE (id_estate, seen_at)
);

COMMIT;
