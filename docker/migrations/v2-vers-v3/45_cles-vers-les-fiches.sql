-- =====================================================================
-- v2 → v3, chantier PRF — Les 11 clés étrangères vers les fiches visent
-- leur numéro (id), plus id_user
-- =====================================================================
--
-- POURQUOI ? Décision de Seb du 2026-10-15 (chantier PRF, maquette
--   https://claude.ai/artifact/YNT5ANwbWYKp6SERVvvn9K) : les colonnes
--   id_client, id_hunter et id_realestatemanager citent la fiche par sa
--   clé primaire, client(id), hunter(id), real_estate_manager(id). Jusqu'ici
--   elles citaient id_user, donc un numéro de compte. Les noms de colonnes
--   ne changent pas, leurs VALEURS si.
--
-- POUR QUI ? Toute base v2 migrée, et toute base v3 créée avant ce
--   chantier. Une base créée par init-v3 après le 2026-10-15 a déjà ces
--   clés (docker/init-v3/01 et 02) : le script le voit et ne fait rien.
--
-- QUOI ?
--   1) retire les 11 FK vers id_user, et les 5 FK composées qui portent
--      ces colonnes (sinon la conversion se heurte à elles) :
--      fk_mandate_request_same_client  -> search_request (id, id_client)
--      fk_mandate_parent_same_client   -> mandate (id, id_client)
--      fk_proposed_hunter_of_mandate   -> mandate (id, id_hunter)
--      fk_perf_mandate_same_hunter     -> mandate (id, id_hunter)
--      fk_perf_payment_same_hunter     -> payment (id, id_hunter)
--   2) convertit les valeurs : UPDATE … FROM <fiche>
--      WHERE <fiche>.id_user = <colonne> ; trg_mandate_exclusivity est
--      coupé le temps des deux UPDATE de mandate : en cours de conversion,
--      une ligne déjà passée à client.id = n croise une ligne encore à
--      user.id = n, d'un autre client, et le trigger y voit deux mandats
--      exclusifs du même client (U02). La conversion est une bijection
--      (id_user UNIQUE) : elle ne crée aucun chevauchement réel, et une
--      requête le vérifie juste après ;
--   3) recrée les 16 FK, mêmes noms, les 11 simples vers (id).
--
-- SOURCE : docker/init-v3/01_create_fil_rouge_immobilier.sql. Le banc
--   v2/v3 (API/tests/integration/test_banc_v2_v3.py) compare les deux
--   bases : il garde ce fichier et 01 alignés.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/45_cles-vers-les-fiches.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/45_cles-vers-les-fiches.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction ; rejouable : si search_request_id_client_fkey
--   vise déjà client(id), rien n'est touché. Retour en arrière : la
--   conversion inverse (WHERE <fiche>.id = <colonne>, SET … = id_user),
--   FK retirées puis recréées vers (id_user).
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = c.confkey[1]
        WHERE c.conname = 'search_request_id_client_fkey' AND a.attname = 'id'
    ) THEN
        RAISE NOTICE '45 : les FK visent déjà le numéro de fiche, rien à faire.';
        RETURN;
    END IF;

    -- 1) Retirer les 5 FK composées, puis les 11 FK simples.
    ALTER TABLE mandate            DROP CONSTRAINT fk_mandate_request_same_client;
    ALTER TABLE mandate            DROP CONSTRAINT fk_mandate_parent_same_client;
    ALTER TABLE estate_proposed    DROP CONSTRAINT fk_proposed_hunter_of_mandate;
    ALTER TABLE hunter_performance DROP CONSTRAINT fk_perf_mandate_same_hunter;
    ALTER TABLE hunter_performance DROP CONSTRAINT fk_perf_payment_same_hunter;

    ALTER TABLE hunter               DROP CONSTRAINT hunter_id_realestatemanager_fkey;
    ALTER TABLE search_request       DROP CONSTRAINT search_request_id_client_fkey;
    ALTER TABLE search_request       DROP CONSTRAINT search_request_id_hunter_fkey;
    ALTER TABLE search_request       DROP CONSTRAINT search_request_id_realestatemanager_fkey;
    ALTER TABLE mandate              DROP CONSTRAINT mandate_id_client_fkey;
    ALTER TABLE mandate              DROP CONSTRAINT mandate_id_hunter_fkey;
    ALTER TABLE estate_searchrequest DROP CONSTRAINT estate_searchrequest_id_hunter_fkey;
    ALTER TABLE estate_proposed      DROP CONSTRAINT estate_proposed_id_hunter_fkey;
    ALTER TABLE commission_scale     DROP CONSTRAINT commission_scale_id_hunter_fkey;
    ALTER TABLE payment              DROP CONSTRAINT payment_id_hunter_fkey;
    ALTER TABLE hunter_performance   DROP CONSTRAINT hunter_performance_id_hunter_fkey;

    -- 2) Convertir : numéro de compte -> numéro de fiche.
    UPDATE hunter h SET id_realestatemanager = m.id
      FROM real_estate_manager m WHERE m.id_user = h.id_realestatemanager;
    UPDATE search_request t SET id_client = c.id
      FROM client c WHERE c.id_user = t.id_client;
    UPDATE search_request t SET id_hunter = h.id
      FROM hunter h WHERE h.id_user = t.id_hunter;
    UPDATE search_request t SET id_realestatemanager = m.id
      FROM real_estate_manager m WHERE m.id_user = t.id_realestatemanager;
    ALTER TABLE mandate DISABLE TRIGGER trg_mandate_exclusivity;
    UPDATE mandate t SET id_client = c.id
      FROM client c WHERE c.id_user = t.id_client;
    UPDATE mandate t SET id_hunter = h.id
      FROM hunter h WHERE h.id_user = t.id_hunter;
    ALTER TABLE mandate ENABLE TRIGGER trg_mandate_exclusivity;
    -- Le trigger coupé n'a rien vérifié : on mesure. Deux mandats du même
    -- client qui se chevauchent malgré l'exclusivité, avec la condition de
    -- check_mandate_exclusivity() (01) : la migration s'arrête (ROLLBACK).
    IF EXISTS (
        SELECT 1 FROM mandate a JOIN mandate b
          ON a.id < b.id AND a.id_client = b.id_client
         WHERE a.status NOT IN ('canceled', 'completed', 'lost')
           AND b.status NOT IN ('canceled', 'completed', 'lost')
           AND (a.is_exclusive OR b.is_exclusive)
           AND a.signature_date IS NOT NULL AND a.ends_at IS NOT NULL
           AND b.signature_date IS NOT NULL AND b.ends_at IS NOT NULL
           AND NOT COALESCE(a.id = b.id_mandate_parent AND b.signature_date >= a.ends_at, FALSE)
           AND NOT COALESCE(b.id = a.id_mandate_parent AND a.signature_date >= b.ends_at, FALSE)
           AND daterange(a.signature_date, a.ends_at, '[]')
            && daterange(b.signature_date, b.ends_at, '[]')
    ) THEN
        RAISE EXCEPTION 'U02 : deux mandats exclusifs du meme client se chevauchent apres conversion'
            USING ERRCODE = '23514', CONSTRAINT = 'u02_mandate_exclusivity';
    END IF;
    UPDATE estate_searchrequest t SET id_hunter = h.id
      FROM hunter h WHERE h.id_user = t.id_hunter;
    UPDATE estate_proposed t SET id_hunter = h.id
      FROM hunter h WHERE h.id_user = t.id_hunter;
    UPDATE commission_scale t SET id_hunter = h.id
      FROM hunter h WHERE h.id_user = t.id_hunter;
    UPDATE payment t SET id_hunter = h.id
      FROM hunter h WHERE h.id_user = t.id_hunter;
    UPDATE hunter_performance t SET id_hunter = h.id
      FROM hunter h WHERE h.id_user = t.id_hunter;

    -- 3) Recréer les 11 FK simples vers (id), puis les 5 FK composées.
    ALTER TABLE hunter ADD CONSTRAINT hunter_id_realestatemanager_fkey
        FOREIGN KEY (id_realestatemanager) REFERENCES real_estate_manager(id) ON DELETE RESTRICT;
    ALTER TABLE search_request ADD CONSTRAINT search_request_id_client_fkey
        FOREIGN KEY (id_client) REFERENCES client(id) ON DELETE RESTRICT;
    ALTER TABLE search_request ADD CONSTRAINT search_request_id_hunter_fkey
        FOREIGN KEY (id_hunter) REFERENCES hunter(id) ON DELETE RESTRICT;
    ALTER TABLE search_request ADD CONSTRAINT search_request_id_realestatemanager_fkey
        FOREIGN KEY (id_realestatemanager) REFERENCES real_estate_manager(id) ON DELETE RESTRICT;
    ALTER TABLE mandate ADD CONSTRAINT mandate_id_client_fkey
        FOREIGN KEY (id_client) REFERENCES client(id) ON DELETE RESTRICT;
    ALTER TABLE mandate ADD CONSTRAINT mandate_id_hunter_fkey
        FOREIGN KEY (id_hunter) REFERENCES hunter(id) ON DELETE RESTRICT;
    ALTER TABLE estate_searchrequest ADD CONSTRAINT estate_searchrequest_id_hunter_fkey
        FOREIGN KEY (id_hunter) REFERENCES hunter(id) ON DELETE RESTRICT;
    ALTER TABLE estate_proposed ADD CONSTRAINT estate_proposed_id_hunter_fkey
        FOREIGN KEY (id_hunter) REFERENCES hunter(id) ON DELETE RESTRICT;
    ALTER TABLE commission_scale ADD CONSTRAINT commission_scale_id_hunter_fkey
        FOREIGN KEY (id_hunter) REFERENCES hunter(id) ON DELETE RESTRICT;
    ALTER TABLE payment ADD CONSTRAINT payment_id_hunter_fkey
        FOREIGN KEY (id_hunter) REFERENCES hunter(id) ON DELETE RESTRICT;
    ALTER TABLE hunter_performance ADD CONSTRAINT hunter_performance_id_hunter_fkey
        FOREIGN KEY (id_hunter) REFERENCES hunter(id) ON DELETE RESTRICT;

    ALTER TABLE mandate ADD CONSTRAINT fk_mandate_request_same_client
        FOREIGN KEY (id_search_request, id_client)
        REFERENCES search_request (id, id_client) ON DELETE RESTRICT;
    ALTER TABLE mandate ADD CONSTRAINT fk_mandate_parent_same_client
        FOREIGN KEY (id_mandate_parent, id_client)
        REFERENCES mandate (id, id_client) ON DELETE RESTRICT;
    ALTER TABLE estate_proposed ADD CONSTRAINT fk_proposed_hunter_of_mandate
        FOREIGN KEY (id_mandate, id_hunter)
        REFERENCES mandate (id, id_hunter) ON DELETE RESTRICT;
    ALTER TABLE hunter_performance ADD CONSTRAINT fk_perf_payment_same_hunter
        FOREIGN KEY (id_payment, id_hunter)
        REFERENCES payment (id, id_hunter) ON DELETE RESTRICT;
    ALTER TABLE hunter_performance ADD CONSTRAINT fk_perf_mandate_same_hunter
        FOREIGN KEY (id_mandate, id_hunter)
        REFERENCES mandate (id, id_hunter) ON DELETE RESTRICT;
END
$$;

-- Ce que les colonnes contiennent désormais (même texte que la fin de 01).
COMMENT ON COLUMN mandate.id_client IS
  'Reference client(id) — le numero de fiche, PAS un id de "user" (chantier PRF).';
COMMENT ON COLUMN mandate.id_hunter IS
  'Reference hunter(id) — le numero de fiche, PAS un id de "user" (chantier PRF).';
COMMENT ON COLUMN search_request.id_client IS
  'Reference client(id) — le numero de fiche, pas un id de "user".';
COMMENT ON COLUMN search_request.id_hunter IS
  'Reference hunter(id) — le numero de fiche, pas un id de "user".';
COMMENT ON COLUMN search_request.id_realestatemanager IS
  'Reference real_estate_manager(id) — le numero de fiche, pas un id de "user". Le manager qui traite la demande.';
COMMENT ON COLUMN hunter.id_realestatemanager IS
  'Reference real_estate_manager(id) — le numero de fiche, pas un id de "user". Le manager du chasseur (choix du groupe, 2026-09-22).';
COMMENT ON COLUMN payment.id_hunter IS
  'Reference hunter(id) — le numero de fiche, pas un id de "user".';
COMMENT ON COLUMN commission_scale.id_hunter IS
  'Reference hunter(id), le numero de fiche ; NULL = bareme par defaut, commun a tous.';
COMMENT ON COLUMN hunter_performance.id_hunter IS
  'Reference hunter(id) — le numero de fiche, pas un id de "user".';
COMMENT ON COLUMN estate_proposed.id_hunter IS
  'Reference hunter(id) — le numero de fiche, pas un id de "user".';
COMMENT ON COLUMN estate_searchrequest.id_hunter IS
  'Reference hunter(id) — le numero de fiche, pas un id de "user".';

COMMENT ON COLUMN hunter.id IS
  'Cle technique propre, conservee pour permettre une migration MongoDB. Les FK des autres tables pointent vers elle (chantier PRF).';
COMMENT ON COLUMN client.id IS
  'Cle technique propre, conservee pour permettre une migration MongoDB. Les FK des autres tables pointent vers elle (chantier PRF).';
COMMENT ON COLUMN real_estate_manager.id IS
  'Cle technique propre, conservee pour permettre une migration MongoDB. Les FK des autres tables pointent vers elle (chantier PRF).';

COMMIT;
