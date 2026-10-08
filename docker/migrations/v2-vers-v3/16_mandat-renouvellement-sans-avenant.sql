-- =====================================================================
-- v2 → v3, après le chantier LOT — Renouvellement : 'renewed' sur l'ancien
-- =====================================================================
--
-- POURQUOI ? Décision du groupe du 2026-10-08 (Gabriel, sur Discord), posée
--   dans docker/init-v3/01_create_fil_rouge_immobilier.sql, commit 6be4e56 :
--
--   - le statut 'renewed' est celui de l'ANCIEN mandat ; le nouveau pointe
--     vers le précédent par id_mandate_parent (cela remplace D8, ADR-010 et
--     ADR-013 : ADR à écrire) ;
--   - pas d'avenant : un mandat a au plus un successeur, d'où un UNIQUE sur
--     id_mandate_parent ;
--   - chk_renewed (« renewed ⇒ a un parent ») n'a plus de sens : il sort.
--
-- AVANT D'ACTIVER : une base qui a déjà deux mandats pointant vers le même
--   parent fait échouer le UNIQUE. La migration s'arrête avant, sans rien
--   deviner. Elle ne change AUCUN statut : un mandat 'renewed' qui a un
--   parent (ancien sens) est à relire à la main.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**. Une base neuve part
--   de docker/init-v3/. Le banc `bash docker/compare_v2_v3.sh` vérifie que
--   les deux chemins mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/16_mandat-renouvellement-sans-avenant.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Aucune ligne
--   n'est modifiée ni supprimée.
-- =====================================================================

BEGIN;

-- Garde : deux mandats qui ont le même parent.
DO $$
DECLARE
    n_doubles INTEGER;
BEGIN
    SELECT count(*) INTO n_doubles FROM (
        SELECT id_mandate_parent FROM mandate
        WHERE id_mandate_parent IS NOT NULL
        GROUP BY id_mandate_parent HAVING count(*) > 1
    ) d;
    IF n_doubles > 0 THEN
        RAISE EXCEPTION '% mandat(s) parent(s) ont plusieurs successeurs : '
            'pas d''avenant, corriger avant de migrer', n_doubles;
    END IF;
END $$;

ALTER TABLE mandate DROP CONSTRAINT IF EXISTS chk_renewed;

ALTER TABLE mandate DROP CONSTRAINT IF EXISTS mandate_id_mandate_parent_key;
ALTER TABLE mandate ADD CONSTRAINT mandate_id_mandate_parent_key
    UNIQUE (id_mandate_parent);

COMMIT;
