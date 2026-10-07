-- =====================================================================
-- v2 → v3, LOT7 — Personnes : coordonnées, priorité, dates
-- =====================================================================
--
-- POURQUOI ? Sept cartes du registre md/questions-a-trancher-2026-10-02.md :
--
--   - Q-SCH-01, Q-SCH-18 : ck_client_address_all_or_nothing reste
--     tout-ou-rien ; les clients repris sans adresse reçoivent
--     address = 'non renseigné' et postal_code = '00000' (l'ALTER de
--     init-v2/02 qui l'assouplissait est défait) ;
--   - Q-PRO-08, Q-MIG-07 : un CHECK de format des téléphones sur client,
--     hunter et real_estate_manager, au format d'ADR-007 (indicatif
--     compris, regex E.164 souple) ; les '0000000000' deviennent
--     '+33000000000' ;
--   - Q-SCH-05 : estate_proposed.client_priority, de 1 à 5 (Q-JEF-18) ;
--   - Q-SCH-09 : created_at sur client, hunter, real_estate_manager, role ;
--   - Q-SCH-10 : hunter.is_cartet devient is_carte_t.
--
-- AVANT D'ACTIVER, compté le 2026-10-07 en base de dev : 4 téléphones
--   '0000000000' (3 clients + le manager placeholder), 0 autre numéro hors
--   format ; 18 clients sur 18 n'ont que la ville ; 0 offre. Une base qui
--   a eu d'autres données depuis est protégée ainsi :
--   - un téléphone hors format (autre que '0000000000') ne se devine pas :
--     la migration s'arrête avant ;
--   - un client qu'on ne peut compléter sans inventer une ville, ou dont
--     le pays refuse le code postal 00000 : la migration s'arrête avant.
--   Dans ces cas, tout est annulé (Q-JEF-26, aucune ancienne donnée
--   supprimée).
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   06_parametres.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/07_personnes.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Seuls les
--   téléphones '0000000000' et les adresses vides des clients sont
--   complétés ; aucune ligne n'est supprimée. Les lignes reprises
--   reçoivent created_at = date de la migration, comme le manager
--   placeholder de init-v3/02 (aucune date source).
-- =====================================================================

BEGIN;

-- Gardes : ce qui ne se complète pas sans inventer une donnée.
DO $$
DECLARE
    n_tel     INTEGER;
    n_adresse INTEGER;
BEGIN
    SELECT count(*) INTO n_tel FROM (
        SELECT phone_number FROM client
        UNION ALL SELECT phone_number FROM hunter
        UNION ALL SELECT phone_number FROM real_estate_manager) t
    WHERE phone_number <> '0000000000'
      AND phone_number !~ '^\+[1-9]([ -]?[0-9]){1,14}$';
    SELECT count(*) INTO n_adresse FROM client
    WHERE (address IS NULL AND town IS NULL AND postal_code IS NOT NULL)
       OR (postal_code IS NULL AND town IS NOT NULL
           AND (country_iso IS NULL OR country_iso NOT IN ('FR','ES','DE','IT')));
    IF n_tel > 0 OR n_adresse > 0 THEN
        RAISE EXCEPTION 'LOT7 : % téléphone(s) hors du format d''ADR-007 et % '
            'client(s) impossible(s) à compléter sans inventer une donnée. '
            'Les corriger avant de migrer (Q-PRO-08, Q-SCH-01, Q-SCH-18).',
            n_tel, n_adresse;
    END IF;
END $$;

-- Q-SCH-09 : created_at sur les quatre tables qui n'en avaient pas.
ALTER TABLE role ADD COLUMN IF NOT EXISTS
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc');
ALTER TABLE client ADD COLUMN IF NOT EXISTS
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc');
ALTER TABLE real_estate_manager ADD COLUMN IF NOT EXISTS
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc');
ALTER TABLE hunter ADD COLUMN IF NOT EXISTS
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc');

-- Q-SCH-10 : la carte T.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'hunter' AND column_name = 'is_cartet') THEN
        ALTER TABLE hunter RENAME COLUMN is_cartet TO is_carte_t;
    END IF;
END $$;

-- Q-MIG-07 : le numéro manquant, au format d'ADR-007.
UPDATE client              SET phone_number = '+33000000000' WHERE phone_number = '0000000000';
UPDATE hunter              SET phone_number = '+33000000000' WHERE phone_number = '0000000000';
UPDATE real_estate_manager SET phone_number = '+33000000000' WHERE phone_number = '0000000000';

-- Q-PRO-08 : le format d'ADR-007 (règle détaillée dans init-v3/01).
ALTER TABLE client DROP CONSTRAINT IF EXISTS ck_client_phone_number_format;
ALTER TABLE client ADD CONSTRAINT ck_client_phone_number_format
    CHECK (phone_number ~ '^\+[1-9]([ -]?[0-9]){1,14}$');
ALTER TABLE hunter DROP CONSTRAINT IF EXISTS ck_hunter_phone_number_format;
ALTER TABLE hunter ADD CONSTRAINT ck_hunter_phone_number_format
    CHECK (phone_number ~ '^\+[1-9]([ -]?[0-9]){1,14}$');
ALTER TABLE real_estate_manager DROP CONSTRAINT IF EXISTS ck_real_estate_manager_phone_number_format;
ALTER TABLE real_estate_manager ADD CONSTRAINT ck_real_estate_manager_phone_number_format
    CHECK (phone_number ~ '^\+[1-9]([ -]?[0-9]){1,14}$');

-- Q-SCH-01, Q-SCH-18 : compléter les adresses, puis remettre le tout-ou-rien.
-- La contrainte assouplie de v2 sort d'abord : elle refuserait une adresse
-- écrite avant son code postal.
ALTER TABLE client DROP CONSTRAINT IF EXISTS ck_client_address_all_or_nothing;
UPDATE client SET address     = 'non renseigné' WHERE address     IS NULL AND town IS NOT NULL;
UPDATE client SET postal_code = '00000'         WHERE postal_code IS NULL AND town IS NOT NULL;
ALTER TABLE client ADD CONSTRAINT ck_client_address_all_or_nothing
    CHECK ((address IS NULL     AND postal_code IS NULL     AND town IS NULL)
        OR (address IS NOT NULL AND postal_code IS NOT NULL AND town IS NOT NULL));

-- Q-SCH-05 : la priorité du client sur un bien proposé (CHECK en ligne,
-- nommé estate_proposed_client_priority_check, comme dans init-v3/01).
ALTER TABLE estate_proposed ADD COLUMN IF NOT EXISTS
    client_priority SMALLINT CHECK (client_priority BETWEEN 1 AND 5);

COMMIT;
