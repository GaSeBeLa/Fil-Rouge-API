-- =====================================================================
-- v2 → v3 — le texte qui décrit une photo (picture.alt_text)
-- =====================================================================
--
-- POURQUOI ? Un lecteur d'écran lit le texte d'une image : sans lui, une
--   personne aveugle ne sait pas ce que montre la photo d'un bien (WCAG 2.2,
--   critère 1.1.1). Trou repéré par la note d'accessibilité PSH (dépôt
--   Fil-Rouge, livrables/5-transverse/note-accessibilite-psh.md,
--   2026-11-19). Choix A de Sébastien.
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant le
--   2026-11-19. Une base créée par init-v3 après a déjà la colonne
--   (docker/init-v3/01) : IF NOT EXISTS, le script ne change rien.
--
-- QUOI ? picture.alt_text : TEXT, facultatif, 300 caractères au plus.
--   Les photos déjà là restent sans texte.
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare les deux bases.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/53_photo-texte-alternatif.sql
--
-- =====================================================================

BEGIN;

ALTER TABLE picture
    ADD COLUMN IF NOT EXISTS alt_text TEXT CHECK (char_length(alt_text) <= 300);

COMMIT;
