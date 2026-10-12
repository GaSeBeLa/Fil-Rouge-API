-- =====================================================================
-- v2 → v3, après 30 — Un bien a deux coordonnées, ou aucune
-- =====================================================================
--
-- POURQUOI ? Audit P17 (réparation prête, vérifiée le 2026-10-12) : estate
--   acceptait une latitude sans longitude. Une seule coordonnée ne place
--   rien sur une carte.
--
-- QUOI ? chk_estate_coordinates_pair. Les autres cas de P17 (prix, typologie,
--   classe énergie) n'ont pas de règle écrite : non traités. Rien n'est
--   modifié : 2 556 biens repris, 0 coordonnée isolée (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/31_bien-coordonnees-par-paire.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : DROP CONSTRAINT.
-- =====================================================================

BEGIN;

ALTER TABLE estate DROP CONSTRAINT IF EXISTS chk_estate_coordinates_pair;
ALTER TABLE estate ADD CONSTRAINT chk_estate_coordinates_pair
    CHECK ((latitude IS NULL) = (longitude IS NULL));

COMMIT;
