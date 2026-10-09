-- =====================================================================
-- v2 → v3, après 18 — Un mandat clos libère le client
-- =====================================================================
--
-- POURQUOI ? ADR-039, Décision 5, confirmée par Sébastien le 2026-10-09
--   (D1a du rapport ADR du 8 octobre) : un mandat 'completed' (vente faite)
--   ou 'lost' (vente perdue) libère le client tout de suite, comme un mandat
--   'canceled'. Le trigger d'exclusivité n'ignorait que 'canceled'.
--
-- QUOI ? Le corps de check_mandate_exclusivity() : les trois statuts 'canceled',
--   'completed' et 'lost' ne bloquent plus personne, et rien ne les bloque.
--   La règle ne fait que se relâcher : aucune ligne qui passe aujourd'hui ne
--   peut être refusée demain. Rien n'est effacé ni modifié dans les données.
--   Corps recopié à l'identique de init-v3/01 : le banc compare son texte.
--
-- POUR QUI ? Toute base v2 déjà migrée, après 04_mandat-duree-exclusivite.sql.
--   Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/19_mandat-clos-libere-le-client.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : rejouer le corps de
--   04_mandat-duree-exclusivite.sql (fonction check_mandate_exclusivity).
-- =====================================================================

BEGIN;

CREATE OR REPLACE FUNCTION check_mandate_exclusivity() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.signature_date IS NULL OR NEW.ends_at IS NULL
       OR NEW.status IN ('canceled', 'completed', 'lost') THEN
        RETURN NEW;                       -- pas encore signé, annulé ou clos
    END IF;
    IF EXISTS (
        SELECT 1 FROM mandate m
         WHERE m.id        <> NEW.id
           AND m.id_client  = NEW.id_client
           AND m.status NOT IN ('canceled', 'completed', 'lost')
           AND (m.is_exclusive OR NEW.is_exclusive)
           AND m.id IS DISTINCT FROM NEW.id_mandate_parent   -- son parent
           AND m.id_mandate_parent IS DISTINCT FROM NEW.id   -- ses enfants
           AND m.signature_date IS NOT NULL AND m.ends_at IS NOT NULL
           AND daterange(m.signature_date, m.ends_at, '[]')
            && daterange(NEW.signature_date, NEW.ends_at, '[]')
    ) THEN
        RAISE EXCEPTION
            'U02 : un mandat exclusif interdit tout autre mandat pour ce client sur la periode'
            USING ERRCODE = '23514', CONSTRAINT = 'u02_mandate_exclusivity';
    END IF;
    RETURN NEW;
END $fn$;

COMMIT;
