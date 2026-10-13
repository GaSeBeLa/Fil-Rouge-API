-- =====================================================================
-- v2 → v3, après ADR-054 — « Particulier » : vrai ou faux, jamais vide
-- =====================================================================
--
-- POURQUOI ? ADR-054, questions 1 et 2 (Sébastien, Discord, 2026-10-13) :
--   seller_type ('private', 'agency' ou vide) devient is_private BOOLEAN
--   NOT NULL, la case « particulier » de l'annonce telle quelle. Le nom de
--   l'agence reste à côté : pour les 166 annonces « particulier » avec une
--   agence, on garde les deux, sans trancher.
--
-- POUR QUI ? Toute base où 40_contact-du-bien.sql a déjà joué. Une base
--   neuve a déjà la colonne : docker/init-v3/01_create_fil_rouge_immobilier.sql.
--
-- QUOI ?
--   1. is_private est ajoutée et remplie depuis seller_type pour les
--      contacts saisis à la main (id_author rempli) : 'private' → vrai,
--      sinon faux ;
--   2. seller_type est retirée, is_private passe NOT NULL ;
--   3. les contacts importés (id_author vide) sont retirés : seller_type
--      ne garde pas la case « particulier » des 166 contradictoires.
--      Le fichier 06, rejoué ensuite, les réimporte depuis le CSV.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/42_contact-particulier-vrai-ou-faux.sql
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < init-v3/06_populate_estate_contact.sql
--
-- SÛRETÉ : une transaction, rejouable : sans seller_type, la migration ne
--   fait rien. Les contacts saisis à la main sont gardés ; seuls les
--   importés sont retirés, puis réimportés par 06.
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'estate_contact' AND column_name = 'seller_type') THEN
        ALTER TABLE estate_contact ADD COLUMN is_private BOOLEAN;
        UPDATE estate_contact SET is_private = (seller_type IS NOT DISTINCT FROM 'private');
        DELETE FROM estate_contact WHERE id_author IS NULL;
        ALTER TABLE estate_contact DROP COLUMN seller_type;
        ALTER TABLE estate_contact ALTER COLUMN is_private SET NOT NULL;
    END IF;
END $$;

COMMIT;
