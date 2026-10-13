-- =====================================================================
-- v2 → v3, après 38 — Le critère « mandats » noté par le taux de réussite
-- =====================================================================
--
-- POURQUOI ? ADR-048, Décision 5 (groupe, 2026-10-12) : le critère
--   « mandats signés » n'est plus noté par mandats × points_per_mandate,
--   mais par le taux ventes ÷ mandats. La note vaut
--   min(100 ; 100 × taux ÷ réglage) : il faut ce réglage en base, jamais
--   en dur (REGLES-CALCUL-REMUNERATION.md l. 47).
--
-- QUOI ? La colonne hunter_rate_parameters.mandate_success_rate_for_max_score,
--   NUMERIC(5,4) NOT NULL, et son COMMENT ON COLUMN. Les versions déjà
--   posées reçoivent 1.0000 (100 %), la valeur de départ choisie le
--   2026-10-12 ; le DEFAULT est retiré ensuite, comme dans docker/init-v3/01
--   (aucune autre colonne de la table n'en a). points_per_mandate reste :
--   le calcul ne le lit plus, mais une version déjà utilisée ne se réécrit pas.
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/39_taux-reussite-mandats.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière :
--   ALTER TABLE hunter_rate_parameters DROP COLUMN mandate_success_rate_for_max_score.
-- =====================================================================

BEGIN;

ALTER TABLE hunter_rate_parameters
    ADD COLUMN IF NOT EXISTS mandate_success_rate_for_max_score NUMERIC(5,4) NOT NULL DEFAULT 1.0000;
ALTER TABLE hunter_rate_parameters
    ALTER COLUMN mandate_success_rate_for_max_score DROP DEFAULT;

COMMENT ON COLUMN hunter_rate_parameters.mandate_success_rate_for_max_score IS
  'Taux de reussite des mandats (ventes / mandats) qui donne la note max du critere '
  'mandats, note = min(100 ; 100 x taux / reglage), 1.0000 = 100 % (ADR-048).';

COMMIT;
