-- =====================================================================
-- v2 → v3, chantier SUG (SUG5) — la décision du client sur un bien proposé
-- =====================================================================
--
-- POURQUOI ? Le client dit s'il est intéressé par un bien proposé, ou
--   pourquoi il le refuse (vote M4 du 2026-11-03 ; ajouts de Gabriel,
--   § 8.1 de md/journal/2026-11-02-suggestion-de-biens.md).
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant SUG5. Une
--   base créée par init-v3 après SUG5 a déjà les colonnes (docker/init-v3/01) :
--   le script ne change rien.
--
-- QUOI ? Trois colonnes de estate_proposed :
--   - client_decision : 'pending' (défaut), 'interested', 'declined' ;
--   - client_decided_at : la date de la dernière décision ;
--   - decline_reason : le motif d'un refus, en liste fermée.
--   Puis trois CHECK : chk_decline_reason_if_declined,
--   chk_decided_at_once_decided, chk_offer_needs_interest (une offre
--   suppose un client 'interested'). Avant ce dernier, les lignes au-delà
--   de 'proposed' passent à 'interested', datées de leur created_at.
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql. Le banc v2/v3
--   (API/tests/integration/test_banc_v2_v3.py) compare les deux bases.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/51_decision-du-client.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/51_decision-du-client.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction ; rejouable (IF NOT EXISTS, et chaque CHECK
--   n'est posé que s'il manque). Retour en arrière : ALTER TABLE
--   estate_proposed DROP COLUMN decline_reason, DROP COLUMN
--   client_decided_at, DROP COLUMN client_decision (les CHECK partent avec).
-- =====================================================================

BEGIN;

ALTER TABLE estate_proposed
    ADD COLUMN IF NOT EXISTS client_decision VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (client_decision IN ('pending', 'interested', 'declined')),
    ADD COLUMN IF NOT EXISTS client_decided_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS decline_reason VARCHAR(20)
        CHECK (decline_reason IN ('too_expensive', 'too_far', 'too_small', 'wrong_type', 'other'));

-- Une offre déjà faite : le client était intéressé (§ 8.1, ⚠️ de Gabriel).
UPDATE estate_proposed
SET client_decision = 'interested', client_decided_at = COALESCE(client_decided_at, created_at)
WHERE proposition_status <> 'proposed' AND client_decision = 'pending';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_decline_reason_if_declined') THEN
        ALTER TABLE estate_proposed ADD CONSTRAINT chk_decline_reason_if_declined
            CHECK (decline_reason IS NULL OR client_decision = 'declined');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_decided_at_once_decided') THEN
        ALTER TABLE estate_proposed ADD CONSTRAINT chk_decided_at_once_decided
            CHECK (client_decision = 'pending' OR client_decided_at IS NOT NULL);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_offer_needs_interest') THEN
        ALTER TABLE estate_proposed ADD CONSTRAINT chk_offer_needs_interest
            CHECK (proposition_status = 'proposed' OR client_decision = 'interested');
    END IF;
END
$$;

COMMIT;
