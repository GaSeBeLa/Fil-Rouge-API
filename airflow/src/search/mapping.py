"""mapping.py — L'index Elasticsearch `estates` : réglages et mapping.

Chantier FLX, fiche FLX8. Sur le modèle du TP1 du cours ELK (kit-TP/ingest.py) :
  - "dynamic": "strict" : un champ hors du mapping est refusé à l'écriture ;
    la liste blanche de documents.py est donc gardée deux fois ;
  - un seul shard, aucune réplique : un nœud unique (profil elk, FLX7) ;
  - analyseur `french` sur le texte libre ;
  - `keyword` pour ce qui se filtre tel quel (ville, code postal, type…) ;
  - nombres pour prix et surface : les requêtes `range` (intervalles) s'y font ;
  - `geo_point` depuis latitude et longitude, présentes ensemble ou pas du
    tout (contrainte chk_estate_coordinates_pair, migration 31).
"""
from __future__ import annotations

INDEX = "estates"

SETTINGS = {"number_of_shards": 1, "number_of_replicas": 0}

MAPPINGS = {
    "dynamic": "strict",
    "properties": {
        "id": {"type": "integer"},
        "reference": {"type": "keyword"},
        "created_at": {"type": "date"},
        "country_iso": {"type": "keyword"},
        "postal_code": {"type": "keyword"},
        "town": {"type": "keyword"},
        "district": {"type": "keyword"},
        "location": {"type": "geo_point"},
        "estate_type": {"type": "keyword"},
        "typology": {"type": "keyword"},
        "floor": {"type": "keyword"},
        "energy_class": {"type": "keyword"},
        "price": {"type": "integer"},
        "surface": {"type": "float"},
        "land_surface": {"type": "float"},
        "construction_date": {"type": "date"},
        "nb_rooms": {"type": "short"},
        "nb_bedrooms": {"type": "short"},
        "nb_bathrooms": {"type": "short"},
        "parking_spaces": {"type": "short"},
        "has_garden": {"type": "boolean"},
        "has_garage": {"type": "boolean"},
        "has_elevator": {"type": "boolean"},
        "has_cellar": {"type": "boolean"},
        "is_climatised": {"type": "boolean"},
        "needs_renovation": {"type": "boolean"},
        "is_imported": {"type": "boolean"},
        "information": {"type": "text", "analyzer": "french"},
    },
}
