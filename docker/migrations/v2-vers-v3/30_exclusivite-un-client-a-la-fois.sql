-- =====================================================================
-- v2 → v3, après 29 — Deux mandats simultanés ne contournent plus l'exclusivité
-- =====================================================================
--
-- POURQUOI ? Audit P15 (réparation prête, vérifiée le 2026-10-12) :
--   trg_mandate_exclusivity ne voit pas la ligne non validée d'une autre
--   transaction. Deux exclusifs créés en même temps pour le même client
--   passaient tous les deux (testé avec deux sessions).
--
-- QUOI ? check_mandate_exclusivity() prend d'abord un verrou consultatif par
--   client, pg_advisory_xact_lock(NEW.id_client), libéré en fin de
--   transaction. La seconde transaction attend, puis voit la première et la
--   refuse. Limite : vrai en READ COMMITTED, le niveau de l'API. Corps recopié
--   à l'identique de init-v3/01 : le banc compare son texte. Rien n'est
--   modifié dans les données.
--
-- POUR QUI ? Toute base v2 déjà migrée, après 29_renouvellement-a-l-echeance.sql.
--   Une base neuve part de docker/init-v3/.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/30_exclusivite-un-client-a-la-fois.sql
--
-- SÛRETÉ : une transaction, rejouable. Retour en arrière : rejouer le corps
--   de la fonction de 29_renouvellement-a-l-echeance.sql.
-- =====================================================================

BEGIN;

CREATE OR REPLACE FUNCTION check_mandate_exclusivity() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    -- P15 : un client à la fois. Sans ce verrou, deux transactions
    -- simultanées ne voient pas la ligne de l'autre, et deux exclusifs
    -- passent. Libéré à la fin de la transaction.
    PERFORM pg_advisory_xact_lock(NEW.id_client);
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

COMMIT;
