"""
test_versions_paiement.py — Versions figées et ordre du paiement (fiche API5).

- ADR-030, ADR-034 : une grille d'honoraires, une ligne de barème ou une
  version des réglages citée par une vente ou un paiement ne se modifie plus
  (PUT -> 409) ; non citée, elle se corrige (PUT -> 200).
- ADR-038 : le statut d'un paiement n'avance que de 'announced' à
  'scheduled' puis 'paid' ; 'refused' depuis 'announced' seulement.
- P33 : le taux final doit être celui que les taux stockés et la version des
  réglages donnent (taux_final de remuneration.py).

Sur la base de test : les helpers de test_constraints_db posent la vente, le
barème et les réglages.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLModelSession

from src.app.utils.exceptions import ConflictError

from .test_constraints_db import (
    HUNTER_RATE_PARAMETERS,
    REFUSED,
    advance,
    fees_grid,
    payment_payload,
    rate_parameters,
    post_as_manager,
    sale_payload,
    write_payment,
)

GRID = {"effective_from": "2025-01-01", "fixed_amount": 3000, "rate": "0.0250"}
SCALE = {"amount_min": 0, "rate": "0.3000", "valid_from": "2025-01-01"}


def create_payment(
    db_client: TestClient, db_session: SQLModelSession, *steps: dict[str, Any], **overrides: Any
) -> tuple[int, dict[str, Any]]:
    """Un paiement 'announced', puis avancé par PUT, étape par étape (ADR-038)."""
    return advance(db_client, db_session, payment_payload(db_client, **overrides), *steps)


# --- ADR-030, ADR-034 : une version citée est figée ---------------------------


def test_cited_fees_grid_cannot_change(db_client: TestClient):
    grid = fees_grid(db_client)
    sale = post_as_manager(db_client, "/sales", sale_payload(db_client, id_parameters_fees=grid))
    assert sale.status_code == 201, sale.text

    response = db_client.put(f"/parameters-fees/{grid}", json={**GRID, "fixed_amount": 3500})
    assert response.status_code == 409
    assert "ADR-030" in response.text


def test_uncited_fees_grid_can_change(db_client: TestClient):
    grid = fees_grid(db_client)

    response = db_client.put(f"/parameters-fees/{grid}", json={**GRID, "fixed_amount": 3500})
    assert response.status_code == 200, response.text
    assert response.json()["fixed_amount"] == 3500


def test_cited_commission_scale_cannot_change(db_client: TestClient, db_session: SQLModelSession):
    _, payload = create_payment(db_client, db_session)
    scale = payload["id_commission_scale"]

    assert db_client.put(f"/commission-scales/{scale}", json={**SCALE, "rate": "0.3500"}).status_code == 409


def test_uncited_commission_scale_can_change(db_client: TestClient):
    scale = db_client.post("/commission-scales", json=SCALE).json()["id"]

    assert db_client.put(f"/commission-scales/{scale}", json={**SCALE, "rate": "0.3500"}).status_code == 200


def test_cited_rate_parameters_cannot_change(db_client: TestClient, db_session: SQLModelSession):
    _, payload = create_payment(db_client, db_session)
    version = payload["id_hunter_rate_parameters"]

    changed = {**HUNTER_RATE_PARAMETERS, "rate_ceiling": "0.55"}
    assert db_client.put(f"/hunter-rate-parameters/{version}", json=changed).status_code == 409


def test_uncited_rate_parameters_can_change(db_client: TestClient):
    version = rate_parameters(db_client)

    changed = {**HUNTER_RATE_PARAMETERS, "rate_ceiling": "0.55"}
    assert db_client.put(f"/hunter-rate-parameters/{version}", json=changed).status_code == 200


# --- ADR-038 : le statut n'avance que dans un sens ------------------------------

SCHEDULED = {"status": "scheduled", "scheduled_for": "2026-03-15"}
PAID = {**SCHEDULED, "status": "paid", "paid_at": "2026-03-15T10:00:00Z"}
ANNOUNCED = {"status": "announced", "scheduled_for": None, "paid_at": None}


def test_payment_moves_forward_step_by_step(db_client: TestClient, db_session: SQLModelSession):
    payment_id, payload = create_payment(db_client, db_session)

    scheduled = db_client.put(f"/payments/{payment_id}", json={**payload, **SCHEDULED})
    assert scheduled.status_code == 200, scheduled.text
    paid = db_client.put(f"/payments/{payment_id}", json={**payload, **PAID})
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"


def test_paid_payment_cannot_go_back_to_announced(db_client: TestClient, db_session: SQLModelSession):
    payment_id, payload = create_payment(db_client, db_session, SCHEDULED, PAID)

    response = db_client.put(f"/payments/{payment_id}", json={**payload, **ANNOUNCED})
    assert response.status_code == 409
    assert "ADR-038" in response.text


def test_announced_payment_cannot_skip_scheduled(db_client: TestClient, db_session: SQLModelSession):
    # PAID porte scheduled_for : chk_scheduled accepterait, seule ADR-038 refuse.
    payment_id, payload = create_payment(db_client, db_session)

    assert db_client.put(f"/payments/{payment_id}", json={**payload, **PAID}).status_code == 409


def test_paid_payment_is_frozen(db_client: TestClient, db_session: SQLModelSession):
    payment_id, payload = create_payment(db_client, db_session, SCHEDULED, PAID)

    response = db_client.put(f"/payments/{payment_id}", json={**payload, "amount": "3600.00"})
    assert response.status_code == 409
    assert "ADR-038" in response.text


def test_payment_cannot_be_deleted(db_client: TestClient, db_session: SQLModelSession):
    # ADR-049, Décision 10 : plus aucune route DELETE, payé ou non.
    payment_id, _ = create_payment(db_client, db_session, SCHEDULED, PAID)

    assert db_client.delete(f"/payments/{payment_id}").status_code == 405
    assert db_client.get(f"/payments/{payment_id}").status_code == 200


@pytest.mark.parametrize("step", [SCHEDULED, PAID])
def test_payment_cannot_be_created_past_announced(db_client: TestClient, db_session: SQLModelSession, step: dict[str, Any]):
    # Les dates sont là : la base accepterait, seule ADR-038 refuse.
    payload = payment_payload(db_client, **step)
    with pytest.raises(ConflictError, match="ADR-038"):
        write_payment(db_session, payload)


def test_scheduled_payment_cannot_go_back_to_announced(db_client: TestClient, db_session: SQLModelSession):
    payment_id, payload = create_payment(db_client, db_session, SCHEDULED)

    assert db_client.put(f"/payments/{payment_id}", json={**payload, **ANNOUNCED}).status_code == 409


def test_announced_payment_can_be_refused_but_not_reopened(db_client: TestClient, db_session: SQLModelSession):
    payment_id, payload = create_payment(db_client, db_session)

    refused = db_client.put(f"/payments/{payment_id}", json={**payload, **REFUSED})
    assert refused.status_code == 200, refused.text
    # Droit fermé (ADR-024) : on ne revient pas à 'announced'.
    assert db_client.put(f"/payments/{payment_id}", json=payload).status_code == 409


def test_scheduled_payment_cannot_be_refused(db_client: TestClient, db_session: SQLModelSession):
    payment_id, payload = create_payment(db_client, db_session, SCHEDULED)

    # scheduled_for vidé : sans lui, chk_scheduled refuserait déjà, et le test
    # ne prouverait plus la règle d'ADR-038.
    refused = {**payload, **REFUSED, "scheduled_for": None}
    assert db_client.put(f"/payments/{payment_id}", json=refused).status_code == 409


# --- P33 : le taux final est recalculé ------------------------------------------


def test_wrong_final_rate_returns_409(db_client: TestClient, db_session: SQLModelSession):
    # 0,30 × (1 + 0 + 0) = 0,30 ; 0,35 annoncé ne s'explique pas.
    payload = payment_payload(db_client, final_rate="0.3500")
    with pytest.raises(ConflictError, match="P33"):
        write_payment(db_session, payload)


@pytest.mark.parametrize(
    ("base", "seniority", "performance", "final"),
    [
        ("0.3000", "0.0400", "0.1000", "0.3420"),  # 0,30 × 1,14
        ("0.1500", "0.0000", "0.0000", "0.2000"),  # 0,15 relevé au plancher
        ("0.5500", "0.1000", "0.2000", "0.6000"),  # 0,715 ramené au plafond
    ],
)
def test_right_final_rate_is_accepted(db_client: TestClient, db_session: SQLModelSession, base: str, seniority: str, performance: str, final: str):
    rates = {"base_rate": base, "seniority_rate": seniority, "performance_rate": performance, "final_rate": final}
    assert write_payment(db_session, payment_payload(db_client, **rates)).id is not None


def test_wrong_final_rate_on_update_returns_409(db_client: TestClient, db_session: SQLModelSession):
    payment_id, payload = create_payment(db_client, db_session)

    response = db_client.put(f"/payments/{payment_id}", json={**payload, "final_rate": "0.3100"})
    assert response.status_code == 409
