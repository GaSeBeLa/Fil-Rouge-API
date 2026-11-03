"""
test_suggestion_query.py — Des critères à la requête Elasticsearch (fiche SUG7).

Sans Elasticsearch ni base : `query_from_criteria` est une fonction pure. Un
test par critère, un pour l'exclusion, un pour « tout None ». Les critères
sont des `Criteria` non écrits : seuls leurs champs comptent ici.
"""

from typing import Any

from src.app.models import Criteria
from src.app.services.suggestion_query import query_from_criteria


def criteria(**fields: Any) -> Criteria:
    """Des critères sans rien d'autre que `fields` (les champs obligatoires de la table à vide)."""
    base: dict[str, Any] = {"id_author": 1, "id_search_request": 1, "estate_type": None, "budget_max": None}
    return Criteria(**{**base, **fields})


def filters(query: dict[str, Any]) -> list[dict[str, Any]]:
    return query["bool"]["filter"]


def should(query: dict[str, Any]) -> list[dict[str, Any]]:
    return query["bool"]["should"]


# --- tout None ------------------------------------------------------------------


def test_no_criteria_adds_no_clause():
    query = query_from_criteria(criteria(), [])
    assert query == {"bool": {"filter": [], "should": [], "must_not": [], "minimum_should_match": 0}}


def test_bonuses_never_exclude_a_document():
    # Sans filtre, Elasticsearch rend un `should` obligatoire : le 0 l'en empêche.
    assert query_from_criteria(criteria(has_garden=True), [])["bool"]["minimum_should_match"] == 0


# --- filter : les critères durs -------------------------------------------------


def test_town_filters_the_town():
    assert {"term": {"town": "Montpellier"}} in filters(query_from_criteria(criteria(town="Montpellier"), []))


def test_postal_code_filters_when_no_town():
    query = query_from_criteria(criteria(postal_code="34000"), [])
    assert {"term": {"postal_code": "34000"}} in filters(query)


def test_town_wins_over_postal_code():
    query = query_from_criteria(criteria(town="Montpellier", postal_code="34000"), [])
    assert {"term": {"town": "Montpellier"}} in filters(query)
    assert {"term": {"postal_code": "34000"}} not in filters(query)


def test_estate_type_filters_the_type():
    assert {"term": {"estate_type": "Maison"}} in filters(query_from_criteria(criteria(estate_type="Maison"), []))


def test_budget_max_caps_the_price():
    assert {"range": {"price": {"lte": 300000}}} in filters(query_from_criteria(criteria(budget_max=300000), []))


def test_budget_min_and_max_bound_the_price():
    query = query_from_criteria(criteria(budget_min=200000, budget_max=300000), [])
    assert {"range": {"price": {"gte": 200000, "lte": 300000}}} in filters(query)


def test_surface_min_floors_the_surface():
    assert {"range": {"surface": {"gte": 60.0}}} in filters(query_from_criteria(criteria(surface_min=60), []))


def test_rooms_min_floors_the_rooms():
    assert {"range": {"nb_rooms": {"gte": 3}}} in filters(query_from_criteria(criteria(rooms_min=3), []))


def test_bedrooms_min_floors_the_bedrooms():
    assert {"range": {"nb_bedrooms": {"gte": 2}}} in filters(query_from_criteria(criteria(bedrooms_min=2), []))


def test_energy_class_max_keeps_the_letters_up_to_it():
    query = query_from_criteria(criteria(energy_class_max="C"), [])
    assert {"terms": {"energy_class": ["A", "B", "C"]}} in filters(query)


# --- should : les bonus ---------------------------------------------------------


def test_wanted_features_raise_the_score():
    wanted = criteria(has_garden=True, has_elevator=True, has_cellar=True, has_garage=True)
    clauses = should(query_from_criteria(wanted, []))
    for field in ("has_garden", "has_elevator", "has_cellar", "has_garage"):
        assert {"term": {field: True}} in clauses


def test_unwanted_feature_adds_no_bonus():
    assert should(query_from_criteria(criteria(has_garden=False), [])) == []


def test_parking_spaces_raise_the_score():
    assert {"range": {"parking_spaces": {"gte": 1}}} in should(query_from_criteria(criteria(parking_spaces=1), []))


# --- must_not : les biens déjà vus ----------------------------------------------


def test_excluded_ids_are_left_out():
    query = query_from_criteria(criteria(), [4, 9])
    assert query["bool"]["must_not"] == [{"ids": {"values": ["4", "9"]}}]
