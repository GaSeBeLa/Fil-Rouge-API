-- 22 : visit.visitor_type reçoit un commentaire qui dit le sens de ses deux valeurs (P23).
--
-- Pourquoi : précision du groupe (Discord, 12/10/2026). Le chasseur visite d'abord seul pour
-- se renseigner, avant de proposer ; la visite 'client' se fait ensemble, sur un bien proposé,
-- et seule elle compte pour la performance (ADR-048). Aucune contrainte : métadonnée seule.
--
-- Rejouable.

BEGIN;

COMMENT ON COLUMN visit.visitor_type IS
  'hunter : visite de renseignement, seul, avant la proposition (libre). '
  'client : visite commune client et chasseur, sur un bien propose ; '
  'seules celles-ci comptent pour la performance (ADR-048).';

COMMIT;
