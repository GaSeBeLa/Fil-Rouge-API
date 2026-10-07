-- =====================================================================
-- v2 → v3, LOT4 — Mandat : six mois exacts et exclusivité
-- =====================================================================
--
-- POURQUOI ? Deux règles du sujet, écrites en commentaire dans init-v2/01
--   depuis septembre, jamais branchées (registre
--   md/questions/questions-a-trancher.md) :
--
--   - U05 : un mandat dure EXACTEMENT 6 mois (Q-MAN-01). Le CHECK de
--     ends_at n'imposait que l'ordre des dates ;
--   - U02 : un mandat exclusif interdit tout autre mandat du même client sur
--     la période (Q-MAN-02). Le trigger est corrigé avant d'être activé :
--     le parent et l'enfant d'un renouvellement sont exclus l'un pour
--     l'autre ; un mandat 'canceled' libère le client tout de suite (D7,
--     Jeff : Q-JEF-06).
--
-- AVANT D'ACTIVER, compté le 2026-10-07 sur les 17 mandats repris :
--   0 violent les 6 mois, 0 paire viole l'exclusivité. Une base où des
--   mandats ont été ajoutés depuis doit refaire ce compte : l'ALTER ou le
--   trigger refuseraient alors les lignes fautives.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   03_mandat-statuts.sql. Une base neuve part de docker/init-v3/. Le banc
--   `bash docker/compare_v2_v3.sh` vérifie que les deux chemins mènent au
--   même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/04_mandat-duree-exclusivite.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Aucune ligne
--   n'est modifiée.
-- =====================================================================

BEGIN;

-- Q-MAN-01 : « exactement 6 mois » à la place du CHECK de ends_at
-- (CHECK en ligne de init-v2/01, nommé mandate_check par PostgreSQL).
ALTER TABLE mandate DROP CONSTRAINT IF EXISTS mandate_check;
ALTER TABLE mandate DROP CONSTRAINT IF EXISTS chk_mandate_six_months;
ALTER TABLE mandate ADD CONSTRAINT chk_mandate_six_months
    CHECK ((signature_date IS NULL AND ends_at IS NULL)
        OR (signature_date IS NOT NULL
            AND ends_at = (signature_date + INTERVAL '6 months')::date));

-- Q-MAN-02 : le trigger d'exclusivité, corrigé puis activé. Corps recopié
-- à l'identique de init-v3/01 : le banc compare son texte.
CREATE OR REPLACE FUNCTION check_mandate_exclusivity() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.signature_date IS NULL OR NEW.ends_at IS NULL
       OR NEW.status = 'canceled' THEN
        RETURN NEW;                       -- pas encore signé, ou annulé
    END IF;
    IF EXISTS (
        SELECT 1 FROM mandate m
         WHERE m.id        <> NEW.id
           AND m.id_client  = NEW.id_client
           AND m.status    <> 'canceled'
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

DROP TRIGGER IF EXISTS trg_mandate_exclusivity ON mandate;
CREATE TRIGGER trg_mandate_exclusivity
    BEFORE INSERT OR UPDATE ON mandate
    FOR EACH ROW EXECUTE FUNCTION check_mandate_exclusivity();

COMMIT;
