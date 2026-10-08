-- =====================================================================
-- v2 → v3, après le chantier LOT — Compte activé, quartier et ville
-- =====================================================================
--
-- POURQUOI ? Deux règles posées le 2026-10-07 dans
--   docker/init-v3/01_create_fil_rouge_immobilier.sql (commits 88ab154 et
--   8024210, CaBaSS), sans migration : le banc les voyait d'un seul côté.
--
--   - user.is_activated : NOT NULL DEFAULT FALSE. Il acceptait le vide, sans
--     valeur par défaut (relevé au registre, Q-ACC-08). Un compte non dit
--     activé ne l'est pas ;
--   - criteria.chk_criteria_district_needs_town : un quartier exige une
--     ville, comme une ville exige un pays (chk_town_requires_country).
--     Oublié à LOT8, qui a ajouté district (Q-MIG-08).
--
-- AVANT D'ACTIVER, compté le 2026-10-08 en base de dev : 25 comptes, tous
--   avec is_activated vide (NULL) ; 0 critère avec un quartier sans ville.
--   Une base qui a eu d'autres données depuis est protégée ainsi :
--   - un is_activated vide devient FALSE : c'est la valeur que prend un
--     compte créé sans la dire, en base neuve comme ici ;
--   - un critère avec un quartier sans ville : on ne devine pas la ville,
--     la migration s'arrête avant.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   12_role-lecture-seule.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/13_compte-active-et-quartier.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Seuls les
--   is_activated vides changent ; aucune ligne n'est supprimée.
-- =====================================================================

BEGIN;

-- Garde : un quartier sans ville.
DO $$
DECLARE
    n_sans_ville INTEGER;
BEGIN
    SELECT count(*) INTO n_sans_ville FROM criteria
    WHERE district IS NOT NULL AND town IS NULL;
    IF n_sans_ville > 0 THEN
        RAISE EXCEPTION '% critère(s) avec un quartier sans ville : '
            'compléter la ville avant de migrer', n_sans_ville;
    END IF;
END $$;

-- Compte activé : le vide devient FALSE, puis la règle.
UPDATE "user" SET is_activated = FALSE WHERE is_activated IS NULL;
ALTER TABLE "user"
    ALTER COLUMN is_activated SET DEFAULT FALSE,
    ALTER COLUMN is_activated SET NOT NULL;

-- Un quartier exige une ville.
ALTER TABLE criteria DROP CONSTRAINT IF EXISTS chk_criteria_district_needs_town;
ALTER TABLE criteria ADD CONSTRAINT chk_criteria_district_needs_town
    CHECK (district IS NULL OR town IS NOT NULL);

COMMIT;
