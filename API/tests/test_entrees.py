"""
test_entrees.py — Les contrôles d'entrée sur une seule ligne (fiche API4).

P2 (email), P16 (chambres <= pièces), P29 (réglages du taux cohérents) et
P32 (forme du détail du calcul) : un refus rend 422, avant la base.

Sans base : une petite app monte build_crud_router sur les VRAIS modèles,
avec un service factice qui rend ce qu'on lui donne. La route revalide le
corps (`_validated`) exactement comme en production.
"""

import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.conf.database import get_session
from src.app.models import Estate, HunterRateParameters, Payment, UserCreate, UserUpdate
from src.app.routes.crud_router import build_crud_router
from src.app.services.base_service import BaseService
from src.app.utils.roles import ADMIN, get_principal

from .conftest import TEST_HEADERS, principal_as


@pytest.fixture
def api() -> TestClient:
    def echo_service() -> MagicMock:
        service = MagicMock(spec=BaseService)
        service.create.side_effect = lambda session, item: item
        service.replace.side_effect = lambda session, item_id, data: data
        service.get_by_id.side_effect = lambda session, item_id: stored.get(item_id)
        return service

    # Lignes « déjà en base » : la réponse d'un GET ne rejuge pas les règles.
    stored: dict[int, Any] = {
        1: Estate(id=1, reference="REPRIS-1", estate_type="Maison", surface=Decimal("80.00"), town="Moulins", nb_rooms=1, nb_bedrooms=4),
        2: incoherent_version(),
    }

    app = FastAPI()
    app.include_router(
        build_crud_router(
            service=echo_service(),
            prefix="/users",
            tag="u",
            response_model=UserCreate,
            update_model=UserUpdate,
            read_model=UserUpdate,  # le service factice rend l'entrée telle quelle
        )
    )
    app.include_router(build_crud_router(service=echo_service(), prefix="/estates", tag="e", response_model=Estate))
    app.include_router(
        build_crud_router(service=echo_service(), prefix="/rates", tag="r", response_model=HunterRateParameters)
    )
    app.include_router(build_crud_router(service=echo_service(), prefix="/payments", tag="p", response_model=Payment))
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[get_principal] = principal_as(ADMIN)
    return TestClient(app, headers=TEST_HEADERS)


def incoherent_version() -> HunterRateParameters:
    """Une version valide, puis faussée après coup (poids : somme 1,05), comme posée en SQL."""
    version = HunterRateParameters.model_validate({**rates(), "id": 2})
    version.weight_visits = Decimal("0.30")
    return version


def with_(base: dict[str, Any]) -> Callable[..., dict[str, Any]]:
    return lambda **overrides: {**base, **overrides}


# --- P2 : email -----------------------------------------------------------------

user = with_({"email": "alice@example.com", "password": "un-mot-de-passe-assez-long", "id_role": 1})


def test_p2_bad_email_returns_422(api: TestClient):
    assert api.post("/users", json=user(email="pas-un-email")).status_code == 422
    assert api.put("/users/1", json={"email": "toujours@pas@un-email"}).status_code == 422


def test_p2_good_email_is_accepted(api: TestClient):
    assert api.post("/users", json=user()).status_code == 201
    assert api.put("/users/1", json={"email": "bob@example.com"}).status_code == 200


# --- P16 : chambres <= pièces ---------------------------------------------------

estate = with_({"reference": "API4-1", "estate_type": "Appartement", "surface": "60.00", "town": "Lyon"})


def test_p16_more_bedrooms_than_rooms_returns_422(api: TestClient):
    response = api.post("/estates", json=estate(nb_rooms=1, nb_bedrooms=5))
    assert response.status_code == 422
    assert "P16" in response.text


def test_p16_stored_estate_is_read_without_being_judged(api: TestClient):
    # 251 biens repris ont plus de chambres que de pièces (ADR-053) : ils
    # restent lisibles. Avant le correctif, GET /estates rendait 500.
    response = api.get("/estates/1")
    assert response.status_code == 200, response.text
    assert response.json()["nb_bedrooms"] == 4


def test_p16_bedrooms_within_rooms_is_accepted(api: TestClient):
    assert api.post("/estates", json=estate(nb_rooms=3, nb_bedrooms=2)).status_code == 201
    assert api.post("/estates", json=estate(nb_rooms=3, nb_bedrooms=3)).status_code == 201
    assert api.post("/estates", json=estate()).status_code == 201  # inconnu : rien à juger


# --- P29 : réglages du taux -----------------------------------------------------

DELAY_TIERS = [{"maximum": 12, "note": 100}, {"maximum": 20, "note": 80}, {"maximum": None, "note": 0}]
rates = with_(
    {
        "effective_from": "2025-01-01",
        "weight_delay": "0.25",
        "weight_exclusivity": "0.10",
        "weight_sales": "0.25",
        "weight_mandates": "0.15",
        "weight_visits": "0.25",
        "delay_tiers": DELAY_TIERS,
        "visit_tiers": [{"maximum": 3, "note": 100}, {"maximum": None, "note": 0}],
        "score_exclusive": "100",
        "score_non_exclusive": "60",
        "points_per_sale": "20",
        "points_per_mandate": "10",
        "window_months": 12,
        "seniority_rate_per_year": "0.02",
        "seniority_cap": "0.10",
        "score_pivot": "50",
        "score_half_range": "50",
        "performance_amplitude": "0.20",
        "rate_floor": "0.20",
        "rate_ceiling": "0.60",
    }
)


def test_p29_coherent_version_is_accepted(api: TestClient):
    response = api.post("/rates", json=rates())
    assert response.status_code == 201, response.text


def test_p29_weights_not_summing_to_one_returns_422(api: TestClient):
    response = api.post("/rates", json=rates(weight_visits="0.30"))  # somme 1,05
    assert response.status_code == 422
    assert "poids" in response.text


def test_p29_stored_version_is_read_without_being_judged(api: TestClient):
    # Une version posée en SQL n'a aucun CHECK (ADR-034, D3) : elle se relit.
    assert api.get("/rates/2").status_code == 200


def test_p29_floor_above_ceiling_returns_422(api: TestClient):
    assert api.post("/rates", json=rates(rate_floor="0.70")).status_code == 422


@pytest.mark.parametrize(
    "tiers",
    [
        [{"maximum": 20, "note": 80}, {"maximum": 12, "note": 100}, {"maximum": None, "note": 0}],  # désordre
        [{"maximum": 12, "note": 100}, {"maximum": 20, "note": 80}],  # dernier fermé
        [{"maximum": 12, "note": 100}, {"maximum": None, "note": 80}, {"maximum": None, "note": 0}],  # ouvert trop tôt
        [{"max": 12, "note": 100}, {"maximum": None, "note": 0}],  # mauvaise clé
        [],  # aucun palier
    ],
)
def test_p29_malformed_tiers_return_422(api: TestClient, tiers: list[dict[str, Any]]):
    assert api.post("/rates", json=rates(delay_tiers=tiers)).status_code == 422


@pytest.mark.parametrize(
    "tier",
    [{"maximum": float("nan"), "note": 100}, {"maximum": 12, "note": float("nan")}, {"maximum": 12, "note": float("inf")}],
)
def test_p29_non_finite_number_returns_422(api: TestClient, tier: dict[str, Any]):
    # Le JSON reçu accepte NaN et Infinity ; json.dumps les écrit tels quels.
    body = json.dumps(rates(delay_tiers=[tier, {"maximum": None, "note": 0}]))
    response = api.post("/rates", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


# --- P32 : forme du détail du calcul --------------------------------------------

DETAILS: dict[str, Any] = {
    "notes": {"delay": 80, "exclusivity": 100, "sales": 50, "mandates": 40, "visits": 30},
    "visit_count": 12,
    "seniority_years": 2,
    "sales_12_months": 3,
    "mandates_12_months": 5,
}
payment = with_({"amount": "3560.34", "status": "announced", "id_sale": 1, "id_hunter": 1})


@pytest.mark.parametrize(
    "details",
    [
        {},  # le cas de P32
        {**DETAILS, "notes": {"delay": 80}},  # 4 notes manquantes
        {**DETAILS, "visits": 0},  # clé inconnue (faute de frappe)
        {**DETAILS, "notes": {**DETAILS["notes"], "sales": 120}},  # note au-dessus de 100
        {k: v for k, v in DETAILS.items() if k != "seniority_years"},  # entrée manquante
    ],
)
def test_p32_malformed_details_return_422(api: TestClient, details: dict[str, Any]):
    assert api.post("/payments", json=payment(calculation_details=details)).status_code == 422


def test_p32_well_formed_details_are_accepted(api: TestClient):
    response = api.post("/payments", json=payment(calculation_details=DETAILS))
    assert response.status_code == 201, response.text
    assert response.json()["calculation_details"]["notes"]["delay"] == 80
    # Absent : la forme n'a rien à juger ; présent ou non selon le statut,
    # c'est chk_refused, côté base, qui tranche (ADR-033, Décision 3).
    assert api.post("/payments", json=payment(calculation_details=None)).status_code == 201
