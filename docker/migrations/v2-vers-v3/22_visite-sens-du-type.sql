-- 22 : visit.visitor_type reçoit un commentaire qui dit le sens de ses deux valeurs (P23).
--
-- Pourquoi : le flux des sources (ADR-053, retenu le 12/10/2026). Le chasseur visite les biens
-- que le client a choisis parmi les propositions, puis rédige sa note d'avis ; le client visite
-- ensuite, avec lui, le bien qui lui convient. Seule la visite 'client' compte pour la performance
-- (ADR-048). Aucune contrainte : métadonnée seule. Texte corrigé le même jour : rejouer 22.
--
-- Rejouable.

BEGIN;

COMMENT ON COLUMN visit.visitor_type IS
  'hunter : visite du chasseur sur un bien que le client a choisi parmi les '
  'propositions, avant sa note d avis. client : visite du client avec son '
  'chasseur, sur un bien propose qui lui convient ; seules celles-ci comptent '
  'pour la remuneration (ADR-048, ADR-053).';

COMMIT;
