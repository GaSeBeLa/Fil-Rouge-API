-- =====================================================================
-- v2 → v3, LOT3 — Mandat : statuts de fin et signature ; offre signée
-- =====================================================================
--
-- POURQUOI ? Quatre décisions du registre
--   (md/questions/questions-a-trancher.md) :
--
--   - 'lost' : statut de fin d'un mandat dont la vente est perdue, vendu
--     hors agence (Q-REM-02 ; Jeff : « rien pour personne », Q-JEF-03) ou
--     par un collègue sur l'autre mandat non exclusif (Q-REM-14). Un seul
--     statut pour les deux cas, tranché le 2026-10-07 ;
--   - is_client_signed retiré : la date de signature et le statut
--     'pending_signature' suffisent (Q-MAN-05, Q-MAN-09). MAND-0008 et
--     MAND-0016 (case à non, date remplie) n'ont plus rien à corriger ;
--   - chk_status_signature : 'canceled' permis sans date de signature,
--     un client peut renoncer avant de signer (Q-MAN-07) ;
--   - proposition_status accepte 'signed' (Q-SCH-04, ferme D5).
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**. Une base neuve
--   part de docker/init-v3/, qui contient déjà ces changements. Le banc
--   `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/03_mandat-statuts.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Aucune ligne
--   n'est modifiée ; seule la colonne is_client_signed disparaît.
-- =====================================================================

BEGIN;

-- Q-REM-02, Q-REM-14 : statut de fin 'lost'. Même ordre et même nom que
-- le CHECK de init-v3/01 (nom donné par PostgreSQL au CHECK en ligne).
ALTER TABLE mandate DROP CONSTRAINT IF EXISTS mandate_status_check;
ALTER TABLE mandate ADD CONSTRAINT mandate_status_check
    CHECK (status IN ('active', 'completed', 'expired',
                      'renewed', 'canceled', 'pending_signature',
                      'lost'));

-- Q-MAN-05, Q-MAN-09 : la date et le statut suffisent.
ALTER TABLE mandate DROP COLUMN IF EXISTS is_client_signed;

-- Q-MAN-07 : 'canceled' accepte un mandat jamais signé.
ALTER TABLE mandate DROP CONSTRAINT IF EXISTS chk_status_signature;
ALTER TABLE mandate ADD CONSTRAINT chk_status_signature
    CHECK ((status = 'pending_signature' AND signature_date IS NULL)
        OR  status = 'canceled'
        OR (status NOT IN ('pending_signature', 'canceled')
            AND signature_date IS NOT NULL));

-- Q-SCH-04 : l'offre signée.
ALTER TABLE estate_proposed DROP CONSTRAINT IF EXISTS estate_proposed_proposition_status_check;
ALTER TABLE estate_proposed ADD CONSTRAINT estate_proposed_proposition_status_check
    CHECK (proposition_status IN ('proposed', 'offer_pending',
                                  'accepted', 'signed', 'rejected'));

COMMIT;
