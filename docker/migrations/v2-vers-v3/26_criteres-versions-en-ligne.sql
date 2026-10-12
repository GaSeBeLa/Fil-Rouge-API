-- =====================================================================
-- v2 → v3, après 25 — Une version de critères pointe vers celle d'avant
-- =====================================================================
--
-- POURQUOI ? Audit P8 (réparation prête, vérifiée le 2026-10-12) :
--   criteria.id_previous_version acceptait une version d'une autre demande,
--   une bifurcation, une seconde version de départ et un lien vers soi. Le
--   Readme (l. 234) demande d'historiser les versions : une ligne, sans
--   branche.
--
-- QUOI ? uq_criteria_id_request (cible de la clé composite),
--   fk_criteria_previous_same_request, uq_criteria_one_successor,
--   chk_criteria_not_own_previous, et l'index unique partiel
--   uq_criteria_one_first_version. Aucune colonne ajoutée, rien de modifié :
--   18 critères repris, un par demande, aucun avec une version précédente
--   (compté le 2026-10-12). Limite : un cycle par UPDATE reste possible ;
--   l'API ne modifie pas une version.
--
-- POUR QUI ? Toute base v2 déjà migrée. Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/26_criteres-versions-en-ligne.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : supprimer les
--   quatre contraintes et l'index.
-- =====================================================================

BEGIN;

ALTER TABLE criteria DROP CONSTRAINT IF EXISTS fk_criteria_previous_same_request;
ALTER TABLE criteria DROP CONSTRAINT IF EXISTS uq_criteria_id_request;
ALTER TABLE criteria DROP CONSTRAINT IF EXISTS uq_criteria_one_successor;
ALTER TABLE criteria DROP CONSTRAINT IF EXISTS chk_criteria_not_own_previous;

ALTER TABLE criteria ADD CONSTRAINT uq_criteria_id_request UNIQUE (id, id_search_request);
ALTER TABLE criteria ADD CONSTRAINT fk_criteria_previous_same_request
    FOREIGN KEY (id_previous_version, id_search_request)
    REFERENCES criteria (id, id_search_request) ON DELETE RESTRICT;
ALTER TABLE criteria ADD CONSTRAINT uq_criteria_one_successor UNIQUE (id_previous_version);
ALTER TABLE criteria ADD CONSTRAINT chk_criteria_not_own_previous
    CHECK (id_previous_version <> id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_criteria_one_first_version
    ON criteria (id_search_request) WHERE id_previous_version IS NULL;

COMMIT;
