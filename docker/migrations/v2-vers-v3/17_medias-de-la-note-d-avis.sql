-- =====================================================================
-- v2 → v3, après le chantier LOT — Plusieurs médias par note d'avis
-- =====================================================================
--
-- POURQUOI ? Le scénario 06 dit que le chasseur joint « des commentaires
--   audio et des vidéos » à sa note d'avis. Le schéma n'avait qu'un media_url
--   et un media_type par note (estate_searchrequest) : un seul média.
--   Décision du groupe du 2026-10-08 (option 2 : une table à part), posée dans
--   docker/init-v3/01_create_fil_rouge_immobilier.sql :
--
--   - nouvelle table review_media (une ligne = un média, relation 1-N) ;
--   - les colonnes media_url, media_type et la contrainte chk_media sortent
--     de estate_searchrequest.
--
-- AVANT D'ACTIVER : les médias déjà saisis sont COPIÉS dans review_media
--   avant de retirer les colonnes. Rien n'est perdu.
--   Compté le 2026-10-08 en base de dev : 0 note d'avis (donc 0 média).
--   Un media_url rempli sans media_type (ou l'inverse) est refusé par
--   chk_media : cette combinaison n'existe pas en base.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**. Une base neuve part
--   de docker/init-v3/. Le banc `bash docker/compare_v2_v3.sh` vérifie que
--   les deux chemins mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/17_medias-de-la-note-d-avis.sql
--
-- SÛRETÉ : une transaction. Rejouable : si les colonnes sont déjà parties,
--   la copie est sautée. Aucune ligne n'est supprimée.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS review_media (
    id                       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at               TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    media_url                TEXT NOT NULL,
    media_type               VARCHAR(10) NOT NULL CHECK (media_type IN ('audio', 'video')),
    id_estate_searchrequest  INTEGER NOT NULL
                             REFERENCES estate_searchrequest(id) ON DELETE RESTRICT
);

-- Copie des médias existants, une seule fois (colonnes encore là).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND table_name = 'estate_searchrequest'
                 AND column_name = 'media_url') THEN
        INSERT INTO review_media (media_url, media_type, id_estate_searchrequest)
        SELECT media_url, media_type, id FROM estate_searchrequest
        WHERE media_url IS NOT NULL AND media_type IS NOT NULL;
    END IF;
END $$;

ALTER TABLE estate_searchrequest DROP CONSTRAINT IF EXISTS chk_media;
ALTER TABLE estate_searchrequest
    DROP COLUMN IF EXISTS media_url,
    DROP COLUMN IF EXISTS media_type;

COMMIT;
