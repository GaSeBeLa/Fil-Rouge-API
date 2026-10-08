-- ============================================================================
-- 05_parametres.sql — le premier jeu de paramètres du calcul de rémunération
-- ============================================================================
--
-- POURQUOI : les trois tables de paramètres sont vides à la création
--   (02_migration.sql:39-42), alors qu'un paiement non refusé doit pointer une
--   ligne de hunter_rate_parameters (chk_refused) et qu'une vente doit pointer
--   une ligne de parameters_fees (sale.id_parameters_fees NOT NULL).
--
-- D'OÙ VIENNENT LES VALEURS : « Le paramétrage proposé »
--   (documents utiles/REGLES-CALCUL-REMUNERATION.md, §14.3, l. 644-686) ;
--   mêmes chiffres que API/src/app/services/remuneration.py
--   (parametrage_par_defaut) et que HUNTER_RATE_PARAMETERS dans
--   API/tests/integration/test_constraints_db.py.
--   ⚠️ Ce sont des paramètres « proposés, à valider avec le client » (l. 59),
--   pas des exigences. Les changer = insérer une nouvelle version datée, jamais
--   modifier une ligne déjà utilisée par un paiement.
--
-- DATE DE DÉPART : 2026-01-01, comme `debut` dans le sujet (l. 646).
--
-- REJOUABLE : chaque insertion est sans effet si la ligne existe déjà.
--   Base déjà créée (ce script ne se lance qu'à la création du volume) :
--     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" \
--       -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/05_parametres.sql'
--
-- LA BASE DE TEST ne rejoue pas ce script (create_test_db.sh : 01, 02, 04) :
--   les tests créent leurs propres lignes sans collision de date.
-- ============================================================================

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
INSERT INTO hunter_rate_parameters (
    effective_from,
    weight_delay, weight_exclusivity, weight_sales, weight_mandates, weight_visits,
    delay_tiers, visit_tiers,
    score_exclusive, score_non_exclusive, points_per_sale, points_per_mandate,
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
    12,
    0.02, 0.10,
    50, 50, 0.20,
    0.20, 0.60
)
ON CONFLICT (effective_from) DO NOTHING;
