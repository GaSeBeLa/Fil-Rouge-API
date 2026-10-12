-- =====================================================================
-- v2 → v3, après 36 — Le sens de floor écrit en base
-- =====================================================================
--
-- POURQUOI ? ADR-053, P18 (tranché par le groupe le 2026-10-12) : floor
--   est l'étage du logement, le sens de la source (colonne etage des
--   annonces). Rien ne le disait, et le nom laissait croire au nombre
--   d'étages du bien. Pas de colonne nb_floors : elle resterait vide.
--
-- QUOI ? Deux COMMENT ON COLUMN, sur estate.floor et criteria.floor.
--   Aucune donnée ni contrainte modifiée.
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/37_sens-de-floor.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : COMMENT ... IS NULL.
-- =====================================================================

BEGIN;

COMMENT ON COLUMN estate.floor IS
  'Etage du logement, sens de la source (colonne etage) : 0 = rez-de-chaussee, '
  'last floor = dernier etage. PAS le nombre d etages du bien (ADR-053, P18).';
COMMENT ON COLUMN criteria.floor IS
  'Etage du logement souhaite par le client, meme sens que estate.floor '
  '(ADR-053, P18).';

COMMIT;
