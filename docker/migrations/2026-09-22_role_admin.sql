-- =====================================================================
-- Ajout du rôle « Admin »
-- =====================================================================
--
-- POURQUOI ? La table role autorisait 'Admin' depuis l'origine :
--
--     CHECK (wording IN ('Admin', 'Client', 'Hunter', 'Manager'))
--
--   mais seules trois lignes étaient insérées (Client, Hunter, Manager).
--   Le rôle était donc déclaré, jamais créé. Impossible d'attribuer des
--   droits d'administration à qui que ce soit.
--
-- POUR QUI ? Seulement pour une base **déjà créée**. Si tu peux repartir
--   de zéro, ne lance pas ce script : fais plutôt, depuis docker/ :
--
--       docker compose down -v
--       docker compose up -d
--
--   02_migration.sql contient déjà la ligne.
--
-- CE DOSSIER N'EST PAS MONTÉ par docker compose (seul init-v2/ l'est) :
--   ce fichier ne part jamais tout seul, il se lance à la main.
--
-- COMMENT ? Depuis docker/ :
--
--   docker exec -i fil_rouge_immobilier_db sh -c \
--     'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' \
--     < migrations/2026-09-22_role_admin.sql
--
-- SÛRETÉ : une transaction, rejouable sans effet de bord.
--
-- CE QUE CE SCRIPT NE FAIT PAS : il ne crée **aucun compte** admin. Créer
--   un compte demanderait d'y écrire un mot de passe, qui serait stocké en
--   clair tant que le hachage n'est pas en place (ADR-016, Argon2id).
--   Le compte admin se crée donc APRÈS le hachage, pas avant.
--
-- Détail et justification : md/securite-mots-de-passe-et-droits.md
-- =====================================================================

BEGIN;

INSERT INTO role (id, wording) OVERRIDING SYSTEM VALUE
VALUES (4, 'Admin')
ON CONFLICT (id) DO NOTHING;

-- La séquence est réalignée sur le plus grand id présent, comme le fait
-- déjà 02_migration.sql : sans cela, un INSERT sans id échouerait.
SELECT setval(pg_get_serial_sequence('role', 'id'),
              COALESCE((SELECT MAX(id) FROM role), 0));

COMMIT;

-- =====================================================================
-- Vérifier après coup : quatre rôles, et zéro compte admin.
--
--   SELECT r.id, r.wording, count(u.id) AS comptes
--   FROM role r LEFT JOIN "user" u ON u.id_role = r.id
--   GROUP BY r.id, r.wording ORDER BY r.id;
-- =====================================================================
