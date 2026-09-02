# API — Fil Rouge Immobilier

API REST (FastAPI + SQLModel) exposant les 11 tables du schéma PostgreSQL
`fil_rouge_immobilier` (voir [`../docker/init/01_create_fil_rouge_immobilier.sql`](../docker/init/01_create_fil_rouge_immobilier.sql)).

## Stack

* [FastAPI](https://fastapi.tiangolo.com/) — routes HTTP + doc interactive auto-générée
* [SQLModel](https://sqlmodel.tiangolo.com/) — mapping des tables PostgreSQL en classes Python (Pydantic + SQLAlchemy)
* PostgreSQL 16 (via `docker/docker-compose.yml`, pas géré par ce dossier)

## Installation

```bash
cd API
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

La base doit tourner (`docker compose up -d` depuis `../docker`). Crée ensuite un fichier
`.env` dans `API/` (copie de [`.env exemple`](.env%20exemple)) avec l'URL de connexion :

```
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/fil_rouge_immobilier
```

`<user>` et `<password>` sont ceux définis dans `docker/.env` (`POSTGRES_USER` /
`POSTGRES_PASSWORD`). Si le mot de passe contient des caractères spéciaux
(`/`, `@`, `:`...), il doit être encodé pour l'URL, par exemple :

```bash
python3 -c "import urllib.parse; print(urllib.parse.quote('<mot_de_passe>', safe=''))"
```

Sans `.env`, l'API se connecte par défaut à `postgresql://postgres:postgres@localhost:5432/fil_rouge_immobilier`
(la valeur par défaut du `docker-compose.yml`).

⚠️ `.env` n'est jamais commité (voir `.gitignore` à la racine du repo) — seul `.env exemple` l'est.

## Lancer l'API

```bash
uvicorn src.app.main:app --reload
```

Puis ouvrir **http://localhost:8000/docs** : interface Swagger interactive pour tester
chaque route sans écrire de commande (bouton « Try it out »).

⚠️ `--reload` recharge le code Python à chaque modification, mais **pas** les variables
d'environnement : si tu modifies `.env`, il faut arrêter (Ctrl+C) et relancer `uvicorn`.

## Tests

```bash
pytest
```

Le seul test présent ([`tests/test_health.py`](tests/test_health.py)) est un test de fumée :
il vérifie que l'application démarre et que `/` répond, sans avoir besoin de PostgreSQL.

## Arborescence

```
API/
├── requirements.txt
├── .env exemple
├── src/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── database.py   # engine SQLModel + injection de session (get_session)
│       ├── main.py        # FastAPI + toutes les routes
│       └── models.py      # les 11 tables, mappées en classes SQLModel
└── tests/
    └── test_health.py
```

## Endpoints

Pour chacune des 11 tables : liste, lecture par id, création, remplacement complet,
suppression. Pas de `PATCH` (mise à jour partielle) — `PUT` remplace toute la ligne.

| Ressource | GET (liste) | GET /{id} | POST | PUT /{id} | DELETE /{id} |
|---|---|---|---|---|---|
| `/users` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/hunters` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/clients` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/real-estate-managers` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/search-requests` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/criteria` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/mandates` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/estates` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/estate-proposed` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/estate-search-requests` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/pictures` | ✅ | ✅ | ✅ | ✅ | ✅ |

Plus `GET /` : health-check (ne touche pas la base).

**Codes d'erreur** : `404` si la ligne demandée n'existe pas ; `409` si une contrainte
PostgreSQL est violée (valeur en double, clé étrangère invalide, ou suppression d'une
ligne encore référencée ailleurs — toutes les FK du schéma sont en `ON DELETE RESTRICT`).

## Limites connues

* Pas d'authentification ni d'autorisation : toutes les routes sont ouvertes.
* Les mots de passe (`User.password`) sont renvoyés tels quels dans les réponses JSON,
  pas de hachage ni de champ de sortie séparé — à corriger avant toute exposition publique.
* Les contraintes `CHECK` du schéma SQL (ex. `typology`, `estate_type`, `floor`) ne sont
  pas répliquées côté Pydantic : une valeur hors liste est acceptée par FastAPI puis
  rejetée par PostgreSQL avec une erreur `409` peu explicite.
* Pas de pagination sur les routes de liste (`GET /estates` renvoie plusieurs milliers
  de lignes d'un coup avec le jeu de données actuel).
