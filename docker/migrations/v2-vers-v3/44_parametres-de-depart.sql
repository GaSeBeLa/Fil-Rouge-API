-- =====================================================================
-- v2 → v3, chantier BAN — Le premier jeu de paramètres du calcul de
-- rémunération
-- =====================================================================
--
-- POURQUOI ? 06_parametres.sql crée les trois tables de paramètres sans
--   aucune ligne : une base migrée n'a ni honoraires, ni barème, ni
--   réglages du taux du chasseur, donc ne sait pas calculer une
--   rémunération. Une base neuve les reçoit de init-v3/05_parametres.sql
--   depuis le 2026-10-08 (e825253), sans migration jumelle jusqu'ici.
--
-- POUR QUI ? Toute base v2 migrée. Sans effet sur une base créée par
--   init-v3 : les lignes y sont déjà, et chaque insertion est ignorée.
--
-- SOURCE : les trois INSERT de docker/init-v3/05_parametres.sql, recopiés
--   tels quels (valeurs et provenance : voir son en-tête). Le banc
--   compare_v2_v3.sh compte les lignes des deux bases : il garde ces deux
--   fichiers alignés.
--
-- COMMENT ? Depuis docker/, en bash :
--
--   docker compose exec -T db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/v2-vers-v3/44_parametres-de-depart.sql
--
--   En PowerShell, qui n'a pas la redirection < :
--
--   Get-Content migrations/v2-vers-v3/44_parametres-de-depart.sql -Raw |
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord (ON CONFLICT et
--   NOT EXISTS), rien n'est modifié ni effacé. Retour en arrière : supprimer
--   les lignes datées du 2026-01-01, tant qu'aucun paiement ni aucune vente
--   ne les pointe.
-- =====================================================================

BEGIN;

-- 1) Honoraires : 3 000 € fixes + 2,5 % du prix (D1, sujet l. 649).
INSERT INTO parameters_fees (effective_from, fixed_amount, rate)
VALUES ('2026-01-01', 3000, 0.0250)
ON CONFLICT (effective_from) DO NOTHING;

-- 2) Barème par défaut (id_hunter NULL), par palier (D3, sujet l. 652-656).
--    Bornes hautes incluses : 199 999 puis 200 000, etc.
INSERT INTO commission_scale (amount_min, amount_max, rate, valid_from, id_hunter)
SELECT v.amount_min, v.amount_max, v.rate, DATE '2026-01-01', NULL
FROM (VALUES
    (0,      199999, 0.3000),
    (200000, 349999, 0.3500),
    (350000, 499999, 0.4000),
    (500000, 749999, 0.4500),
    (750000, NULL,   0.5000)
) AS v(amount_min, amount_max, rate)
WHERE NOT EXISTS (
    SELECT 1 FROM commission_scale c
    WHERE c.id_hunter IS NULL
      AND c.valid_from = DATE '2026-01-01'
      AND c.amount_min = v.amount_min
);

-- 3) Réglages du taux du chasseur (D6, D7, D8 ; sujet l. 658-685, texte l. 139).
--    Les paliers : borne haute incluse -> note, la dernière ouverte (null).
--    Critère « mandats » noté par le taux ventes ÷ mandats (ADR-048) : 1.0000,
--    soit 100 % pour la note max, choisi par le groupe le 2026-10-12 (le sujet
--    n'a pas de grille). points_per_mandate (10) n'est plus lu par le calcul.
INSERT INTO hunter_rate_parameters (
    effective_from,
    weight_delay, weight_exclusivity, weight_sales, weight_mandates, weight_visits,
    delay_tiers, visit_tiers,
    score_exclusive, score_non_exclusive, points_per_sale, points_per_mandate,
    mandate_success_rate_for_max_score,
    window_months,
    seniority_rate_per_year, seniority_cap,
    score_pivot, score_half_range, performance_amplitude,
    rate_floor, rate_ceiling
)
VALUES (
    '2026-01-01',
    0.25, 0.10, 0.25, 0.15, 0.25,
    '[{"maximum": 12, "note": 100}, {"maximum": 20, "note": 80},
      {"maximum": 28, "note": 60},  {"maximum": 36, "note": 40},
      {"maximum": 48, "note": 20},  {"maximum": null, "note": 0}]',
    '[{"maximum": 3, "note": 100},  {"maximum": 6, "note": 80},
      {"maximum": 9, "note": 60},   {"maximum": 12, "note": 40},
      {"maximum": 15, "note": 20},  {"maximum": null, "note": 0}]',
    100, 60, 20, 10,
    1.0000,
    12,
    0.02, 0.10,
    50, 50, 0.20,
    0.20, 0.60
)
ON CONFLICT (effective_from) DO NOTHING;

COMMIT;
