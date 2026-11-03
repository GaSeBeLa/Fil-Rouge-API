"""
suggestion_query.py — Des critères d'une demande à la requête Elasticsearch
du moteur de suggestion (fiche SUG7, chantier SUG).

Une fonction pure, sans base ni Elasticsearch : `query_from_criteria`. Elle
rend une requête `bool` pour l'index `estates`, dont les champs sont ceux de
`airflow/src/search/mapping.py` :

- `filter` : les critères durs — un bien qui ne les tient pas est écarté ;
- `should` : des bonus de score — un bien qui les a remonte, aucun n'est
  écarté (`minimum_should_match` à 0 : sans lui, Elasticsearch rend un
  `should` obligatoire dès qu'il n'y a pas de `filter`) ;
- `must_not` : les biens déjà vus, par leur `_id` (= `estate.id`,
  `airflow/src/search/documents.py`).

Les critères que l'index ne porte pas ne s'inventent pas : balcon, terrasse,
vue, piscine, calme, lumineux, cheminée, salles de bains, toilettes, étage,
neuf, travaux et surface du terrain sont ignorés ici. Les ajouter demande
d'abord de les indexer (mapping et documents de l'index `estates`).
"""

from typing import Any, Optional, Sequence

from ..models import Criteria

# Les lettres du DPE, de la meilleure à la pire (CHECK de criteria.energy_class_max).
ENERGY_LETTERS = ("A", "B", "C", "D", "E", "F", "G")

# Les équipements voulus qui montent le score : critère → champ de l'index.
BONUS_FEATURES = ("has_garden", "has_elevator", "has_cellar", "has_garage")


def _price_range(budget_min: Optional[int], budget_max: Optional[int]) -> dict[str, int]:
    """Les bornes du prix en euros ; vide si aucun budget n'est donné."""
    return {key: value for key, value in (("gte", budget_min), ("lte", budget_max)) if value is not None}


def _energy_letters(energy_class_max: Optional[str]) -> list[str]:
    """Les lettres du DPE jusqu'à `energy_class_max` incluse ; vide si absente ou inconnue."""
    if energy_class_max not in ENERGY_LETTERS:
        return []
    return list(ENERGY_LETTERS[: ENERGY_LETTERS.index(energy_class_max) + 1])


def query_from_criteria(criteria: Criteria, excluded_ids: Sequence[int]) -> dict[str, Any]:
    """
    La requête `bool` qui traduit `criteria` pour l'index `estates`, sans les
    biens de `excluded_ids`.

    Un critère absent (`None`) n'ajoute rien ; un équipement à `False` non
    plus (le client ne le cherche pas, il ne l'exclut pas). La ville l'emporte
    sur le code postal quand les deux sont donnés. Tout absent : une requête
    aux quatre listes vides, qui rend tout l'index.
    """
    filters: list[dict[str, Any]] = []
    if criteria.town is not None:
        filters.append({"term": {"town": criteria.town}})
    elif criteria.postal_code is not None:
        filters.append({"term": {"postal_code": criteria.postal_code}})
    if criteria.estate_type is not None:
        filters.append({"term": {"estate_type": criteria.estate_type}})
    price = _price_range(criteria.budget_min, criteria.budget_max)
    if price:
        filters.append({"range": {"price": price}})
    if criteria.surface_min is not None:
        filters.append({"range": {"surface": {"gte": float(criteria.surface_min)}}})
    for field, minimum in (("nb_rooms", criteria.rooms_min), ("nb_bedrooms", criteria.bedrooms_min)):
        if minimum is not None:
            filters.append({"range": {field: {"gte": minimum}}})
    letters = _energy_letters(criteria.energy_class_max)
    if letters:
        filters.append({"terms": {"energy_class": letters}})

    bonuses: list[dict[str, Any]] = [
        {"term": {field: True}} for field in BONUS_FEATURES if getattr(criteria, field) is True
    ]
    if criteria.parking_spaces:
        bonuses.append({"range": {"parking_spaces": {"gte": criteria.parking_spaces}}})

    excluded: list[dict[str, Any]] = [{"ids": {"values": [str(i) for i in excluded_ids]}}] if excluded_ids else []
    return {"bool": {"filter": filters, "should": bonuses, "must_not": excluded, "minimum_should_match": 0}}
