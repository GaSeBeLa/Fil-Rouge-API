-- =====================================================================
-- v2 → v3, après 28 — Le renouvellement ne contourne plus l'exclusivité
-- =====================================================================
--
-- POURQUOI ? ADR-053, P13 (choix du groupe du 2026-10-12) : le trigger
--   exemptait le parent et l'enfant d'un renouvellement sans regarder les
--   dates. Un mandat d'un autre chasseur, signé en mars, passait en plein
--   milieu d'un exclusif (janvier à juillet) s'il était déclaré
--   « renouvellement ».
--
-- QUOI ?
--   - check_mandate_exclusivity() : le parent et l'enfant ne s'exemptent que
--     si l'enfant est signé à l'échéance du parent (ADR-050, Décision 4 ;
--     00_…feature:40). Corps recopié à l'identique de init-v3/01 : le banc
--     compare son texte.
--   - chk_mandate_not_own_parent : un mandat n'est pas son propre parent.
--   - uq_mandate_id_client et fk_mandate_parent_same_client : le parent est
--     un mandat du même client.
--   Rien n'est modifié dans les données : aucun mandat repris n'a de parent
--   (compté le 2026-10-12).
--
-- POUR QUI ? Toute base v2 déjà migrée, après 19_mandat-clos-libere-le-client.sql.
--   Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/29_renouvellement-a-l-echeance.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : rejouer le corps
--   de la fonction de 19_mandat-clos-libere-le-client.sql, puis supprimer les
--   trois contraintes.
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
           -- son parent, seulement si NEW est signé à son échéance (P13)
           AND NOT COALESCE(m.id = NEW.id_mandate_parent
                            AND NEW.signature_date >= m.ends_at, FALSE)
           -- son enfant, seulement s'il est signé à l'échéance de NEW (P13)
           AND NOT COALESCE(m.id_mandate_parent = NEW.id
                            AND m.signature_date >= NEW.ends_at, FALSE)
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

ALTER TABLE mandate DROP CONSTRAINT IF EXISTS fk_mandate_parent_same_client;
ALTER TABLE mandate DROP CONSTRAINT IF EXISTS uq_mandate_id_client;
ALTER TABLE mandate DROP CONSTRAINT IF EXISTS chk_mandate_not_own_parent;

ALTER TABLE mandate ADD CONSTRAINT chk_mandate_not_own_parent CHECK (id_mandate_parent <> id);
ALTER TABLE mandate ADD CONSTRAINT uq_mandate_id_client UNIQUE (id, id_client);
ALTER TABLE mandate ADD CONSTRAINT fk_mandate_parent_same_client
    FOREIGN KEY (id_mandate_parent, id_client)
    REFERENCES mandate (id, id_client) ON DELETE RESTRICT;

COMMIT;
