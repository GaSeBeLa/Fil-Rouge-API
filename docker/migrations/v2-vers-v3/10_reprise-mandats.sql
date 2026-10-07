-- =====================================================================
-- v2 → v3, LOT10 — Reprendre les anciens mandats
-- =====================================================================
--
-- POURQUOI ? Quatre cartes du registre md/questions/questions-a-trancher.md,
-- toutes confirmées par Jeff (Q-JEF-13) :
--
--   - Q-MIG-10 : les 6 mandats « actif » déjà finis à la date de l'audit,
--     le 25/07/2026 (MAND-0004, 0007, 0009, 0010, 0011, 0012), passent en
--     'expired'. Date fixe : le résultat ne dépend pas du jour du lancement ;
--   - Q-MIG-12 : le mandat 13, écarté par v2 (son client était un chasseur),
--     se rattache à Nina Girard (user 19, déjà cliente), avec sa demande et
--     son critère tirés de la ligne source ; pas de compte en plus ;
--   - Q-MIG-13 : suspendu -> 'canceled', termine -> 'completed' : déjà ainsi
--     dans v2, rien à changer ici (écrit dans init-v3/02 et son README) ;
--   - Q-MIG-03 : une demande sous mandat passe en 'launched' (tranché à
--     LOT10) ; pas de nouvel état.
--
-- AVANT D'ACTIVER, compté le 2026-10-07 : 17 demandes, toutes en
--   'confirmed' ; 17 critères ; 17 mandats, dont les 6 ci-dessus en
--   'active' ; Nina Girard a une fiche client et aucune demande. Une base
--   qui a eu d'autres données depuis est protégée ainsi :
--   - Nina Girard absente des clients, ou les ids 13 de search_request et
--     de mandate déjà pris par autre chose : la migration s'arrête avant ;
--   - un mandat parmi les 6 qui n'est plus 'active' (déjà traité, ou
--     changé à la main) n'est pas touché.
--
-- POUR QUI ? Seulement pour une base v2 **déjà créée**, après
--   09_biens.sql. Une base neuve part de docker/init-v3/.
--   Le banc `bash docker/compare_v2_v3.sh` vérifie que les deux chemins
--   mènent au même schéma.
--
-- COMMENT ? Depuis docker/ :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/10_reprise-mandats.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord. Aucune ligne
--   n'est supprimée ; une seconde passe ne trouve plus rien à faire.
-- =====================================================================

BEGIN;

-- Garde : Nina Girard est cliente, et les ids 13 sont libres ou déjà à elle.
DO $$
DECLARE
    n_nina    INTEGER;
    n_conflit INTEGER;
BEGIN
    SELECT count(*) INTO n_nina FROM client c
    JOIN "user" u ON u.id = c.id_user
    WHERE c.id_user = 19 AND u.email = 'nina.girard@mail.fr';
    SELECT (SELECT count(*) FROM search_request WHERE id = 13 AND id_client <> 19)
         + (SELECT count(*) FROM mandate        WHERE id = 13 AND id_client <> 19)
      INTO n_conflit;
    IF n_nina <> 1 OR n_conflit > 0 THEN
        RAISE EXCEPTION 'LOT10 : Nina Girard introuvable comme cliente (% fiche) '
            'ou id 13 déjà pris par un autre client (% ligne). Vérifier avant '
            'de migrer (Q-MIG-12).', n_nina, n_conflit;
    END IF;
END $$;

-- Q-MIG-12 : le mandat 13 de Nina Girard, avec sa demande et son critère.
INSERT INTO search_request (id, created_at, id_author, id_client, id_hunter, status)
OVERRIDING SYSTEM VALUE
VALUES (13, '2026-02-10'::date, 19, 19, 2, 'confirmed')
ON CONFLICT (id) DO NOTHING;

-- Critère : même lecture du texte source que les 17 autres ; secteur 4,
-- Figuerolles (PgSQL.sql:41-51). Il prend l'id suivant, 18, comme init-v3/02.
INSERT INTO criteria (id_author, id_search_request, country_iso, town, postal_code,
                      district, budget_min, budget_max, renovation_budget_min,
                      renovation_budget_max, surface_min, estate_type, typology,
                      change_reason)
SELECT 2, 13, 'FR', 'Montpellier', '34070', 'Figuerolles', NULL, 220000, NULL,
       NULL, 40, 'Appartement', 'T2 / F2',
       'T2 Figuerolles, budget 220000, premier achat, 40m2 min'
WHERE NOT EXISTS (SELECT 1 FROM criteria WHERE id_search_request = 13);

INSERT INTO mandate (id, reference, status, signature_date, ends_at, is_exclusive,
                     id_hunter, id_client, id_search_request)
OVERRIDING SYSTEM VALUE
VALUES (13, 'MAND-0013', 'active', '2026-02-10'::date,
        ('2026-02-10'::date + INTERVAL '6 months')::date, false, 2, 19, 13)
ON CONFLICT (id) DO NOTHING;

-- Q-MIG-10 : les 6 mandats échus au 25/07/2026.
UPDATE mandate SET status = 'expired'
WHERE status = 'active'
  AND reference IN ('MAND-0004', 'MAND-0007', 'MAND-0009',
                    'MAND-0010', 'MAND-0011', 'MAND-0012');

-- Q-MIG-03 : une demande sous mandat signé est « lancée ».
UPDATE search_request sr SET status = 'launched'
WHERE status = 'confirmed'
  AND EXISTS (SELECT 1 FROM mandate m WHERE m.id_search_request = sr.id);

COMMIT;
