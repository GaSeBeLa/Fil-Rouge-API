
# API — Fil Rouge Immobilier

API REST (FastAPI + SQLModel) exposant les 18 tables du schéma PostgreSQL
`fil_rouge_immobilier` (voir [`../docker/init-v2/01_create_fil_rouge_immobilier.sql`](../docker/init-v2/01_create_fil_rouge_immobilier.sql)).

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

### Avec Docker — recommandé, rien à installer

**Une seule fois, à la première installation** : copier `docker/.env.exemple`
sous le nom `docker/.env`, et y mettre ses propres mots de passe. Sans ce
fichier, `docker compose` affiche `variable is not set` et la base ne démarre
pas.

L'API est un service du `docker-compose` du projet. Depuis `docker/` :

```bash
docker compose up -d api
```

Elle attend que PostgreSQL réponde (`healthcheck`) avant de démarrer, lit ses
identifiants dans le même `docker/.env` que la base, et recharge le code à
chaud — seuls `API/src/` et `API/tests/` sont montés, en lecture seule.

⚠️ Avec Docker, **`API/.env` n'est pas lu** : il ne sert qu'au lancement en
local. C'est voulu — son `DATABASE_URL` pointe sur `localhost`, qui dans le
conteneur n'est pas la base (l'API répondait alors `500`).

Pour l'arrêter : `docker compose stop api`. Pour voir ses logs :
`docker compose logs -f api`.

### Ou en local, si Python est installé

```bash
uvicorn src.app.main:app --reload
```

Dans les deux cas, ouvrir **http://localhost:8000/docs** : interface Swagger interactive pour tester
chaque route sans écrire de commande (bouton « Try it out »).

⚠️ `--reload` recharge le code Python à chaque modification, mais **pas** les variables
d'environnement : si tu modifies `.env`, il faut arrêter (Ctrl+C) et relancer `uvicorn`.

## Tests

Avec Docker, depuis `docker/` (l'API doit tourner) :

```bash
docker compose exec api python -m pytest -q -p no:cacheprovider
```

`-p no:cacheprovider` : `tests/` est monté en lecture seule, pytest ne peut pas y
écrire son cache. En local, depuis `API/` : `pytest`.

**État au 2026-10-02** : **121 tests, `121 passed`** — 99 unitaires, qui ne
touchent pas PostgreSQL (vérifié avec le conteneur `db` arrêté), dont les
**55 cas de rémunération** du sujet, et 22 d'intégration (voir plus bas).

**Au 2026-10-05** : **123 tests, `123 passed`**. Le routeur commun revalide
désormais l'entrée (voir « Codes de réponse ») ; deux tests y sont dédiés :
un prix à virgule et un champ obligatoire manquant rendent `422`.

| Fichier | Ce qu'il prouve |
|---|---|
| [`test_health.py`](tests/test_health.py) | `/` répond |
| [`test_security.py`](tests/test_security.py) | hachage argon2 : jamais de clair, sel aléatoire, comptes migrés refusés sans exception, `needs_rehash` |
| [`test_user_service.py`](tests/test_user_service.py) | le mot de passe n'atteint jamais le repository en clair ; mise à jour partielle |
| [`test_base_service.py`](tests/test_base_service.py) | id inexistant → `NotFoundError` **avant** toute écriture |
| [`test_base_repository.py`](tests/test_base_repository.py) | `id` ignoré au `POST` ; `IntegrityError` → rollback + `ConflictError` |
| [`test_user_models.py`](tests/test_user_models.py) | mot de passe ≥ 12 caractères ; `UserPublic` sans `password` |
| [`test_crud_router.py`](tests/test_crud_router.py) | 404 / 409 / 201 / 422 pour les 18 ressources |
| [`test_remuneration.py`](tests/test_remuneration.py) | les **55 cas** de [`10_calcul_remuneration_chasseur.feature`](../user-stories/10_calcul_remuneration_chasseur.feature), lignes d'exemples recopiées telles quelles |

**Calcul de la rémunération** : [`services/remuneration.py`](src/app/services/remuneration.py)
est le code de référence **du sujet**, extrait tel quel de `REGLES-CALCUL-REMUNERATION.md`
§14.2-14.3 (seule la docstring est ajoutée). Fonction pure : le branchement sur
`commission_scale`, `parameters_fees` et `payment` reste à écrire.

**Pour écrire un test** :
- la fixture `client` ([`tests/conftest.py`](tests/conftest.py)) donne un `TestClient`
  sur la vraie app — `def test_xxx(client): ...` ;
- la fixture `fast_hasher` remplace argon2 (~300 ms par hash) par un hacheur faible ;
- pour isoler de la base : `MagicMock(spec=<Repository>)` à la place du repository,
  ou `app.dependency_overrides[get_session]` à la place de la session.

### Tests d'intégration — base de test isolée

**22 tests** dans [`tests/integration/`](tests/integration/), contre une vraie base
PostgreSQL, **`fil_rouge_test`** — jamais la base de dev. Avant la première fois, et
après toute modification de `docker/init-v2/01` ou `02` :

```bash
bash docker/create_test_db.sh
```

* **Même conteneur, autre base** : `01` + `02` rejoués, donc les mêmes contraintes
  que la base de dev ; pas le `03` (aucun bien).
* **Tout est annulé** : chaque test tourne dans une transaction annulée à la fin
  (fixture `db_session`) ; utiliser `db_client` au lieu de `client` pour que l'API
  écrive dedans. Mesuré : comptes de `fil_rouge_test` et `fil_rouge_immobilier`
  identiques avant et après la suite.
* **Base absente ou `db` arrêté** : les 22 tests sont **sautés** (`skipped`),
  avec la commande à lancer. Les écarter : `-m "not integration"`.

⚠️ La fixture `client` reste branchée sur la **vraie** base de dev : un test qui
écrit via `client` y écrit pour de bon. Pour écrire, toujours `db_client`.

**La suite, dans l'ordre** (chaque étape s'appuie sur la précédente) :
1. ✅ tests unitaires purs — la logique, sans base ;
2. ✅ base de test isolée — les contraintes PostgreSQL (FK, `CHECK`, `UNIQUE`) ;
3. ✅ calculette de rémunération — les 55 cas du sujet ;
4. ➡️ brancher la calculette sur la base (lire le barème, écrire le paiement),
   testé sur la base de test — après arbitrage de `X01` par le groupe.

## Architecture

Chaque table suit une architecture en 3 couches (Router → Service → Repository) :

* **`routes/<table>_router.py`** — reçoit la requête HTTP, traduit les erreurs métier
  (`NotFoundError`, `ConflictError`) en codes HTTP (404, 409)
* **`services/<table>_service.py`** — logique métier (aujourd'hui minimale, sauf
  `user_service.py` qui hache le mot de passe)
* **`repositories/<table>_repository.py`** — parle à la base via SQLModel/PostgreSQL,
  rien d'autre

Ces trois couches héritent chacune d'une classe générique (`routes/crud_router.py`,
`services/base_service.py`, `repositories/base_repository.py`) qui porte le
comportement CRUD commun aux 18 tables.

## Arborescence

```
API/
├── requirements.txt
├── .env exemple
├── src/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py               # crée l'app FastAPI, branche un router par table
│       ├── conf/
│       │   └── database.py       # engine SQLModel + injection de session (get_session)
│       ├── utils/
│       │   └── exceptions.py     # NotFoundError, ConflictError
│       ├── models/                # une classe SQLModel par table (18 fichiers)
│       ├── repositories/          # accès base : base_repository.py + 1 fichier par table
│       ├── services/              # logique métier : base_service.py + 1 fichier par table
│       └── routes/                # routage HTTP : crud_router.py + 1 fichier par table
└── tests/
    ├── conftest.py              # fixtures client, fast_hasher
    ├── test_*.py                # 7 fichiers unitaires, voir § Tests
    └── integration/             # conftest (db_session, db_client) + 3 fichiers
```

## Endpoints

Les 18 tables ont les **mêmes 5 routes**, construites par
[`routes/crud_router.py`](src/app/routes/crud_router.py) : `GET` (liste),
`GET /{id}`, `POST`, `PUT /{id}`, `DELETE /{id}`. Plus `GET /` (health-check).
Soit **91 opérations** (compté dans `/openapi.json`).

| Ressources |
|---|
| `/users` `/roles` `/hunters` `/clients` `/real-estate-managers` |
| `/search-requests` `/criteria` `/mandates` `/estates` `/estate-proposed` |
| `/estate-search-requests` `/pictures` `/visits` `/sales` `/payments` |
| `/commission-scales` `/parameters-fees` `/hunter-performances` |

### Ce qu'un test doit attendre

Mesuré le 2026-10-02 contre l'API qui tourne (✅), ou lu dans le code (📖) :

| Cas | Code | `detail` renvoyé |
|---|---|---|
| liste, lecture | `200` | — |
| création réussie | **`201`** | — |
| id inexistant (`GET`, `PUT`, `DELETE`) | `404` | `"<Entité> introuvable"`, ex. `"Chasseur introuvable"` ✅ |
| id non entier (`/hunters/abc`) | `422` | erreur Pydantic `int_parsing` ✅ |
| corps invalide au `POST` / `PUT` (type faux, champ obligatoire manquant, prix à virgule) | `422` | erreur Pydantic, ex. `int_from_float`, `missing` ✅ |
| contrainte violée au `POST` / `PUT` | `409` | `"Contrainte violée (valeur en double ou référence inexistante)."` ✅ |
| `DELETE` d'une ligne encore référencée | `409` | `"Suppression impossible : cette ligne est encore référencée ailleurs."` 📖 |

✅ **Un champ obligatoire manquant donne `422`** (depuis le 2026-10-05) :
`POST /roles` avec `{}` renvoie `422`, `missing` sur `wording` (mesuré). Un
modèle de table SQLModel ne valide pas ce que FastAPI lui passe : avant ce
jour, ce cas finissait en `409`, et un prix `199999.5` était arrondi en
silence à `200000` par PostgreSQL. `_validated`
([`crud_router.py`](src/app/routes/crud_router.py)) revalide le corps avec
`model_validate`. Les `CHECK` du schéma, eux, restent vérifiés par PostgreSQL
seul (`409`).

⚠️ **Les 34 clés étrangères sont en `ON DELETE RESTRICT`** : supprimer un parent
encore référencé échoue toujours en `409`.

### Deux comportements à ne pas oublier

* **`id` est ignoré au `POST`** : il est remis à `None`, PostgreSQL le génère
  ([`base_repository.py`](src/app/repositories/base_repository.py)).
* **`PUT` remplace toute la ligne** — sauf `/users` :

| `/users` | Modèle | Particularité |
|---|---|---|
| `POST` (entrée) | `UserCreate` | mot de passe en clair, **haché** par le service (Argon2) |
| `PUT` (entrée) | `UserUpdate` | tous les champs optionnels : mise à jour **partielle** |
| réponses | `UserPublic` | **jamais** de champ `password` ✅ |

## Limites connues

* Pas d'authentification : le client l'a mise hors périmètre (ADR-026).
* Les contraintes `CHECK` du schéma SQL (ex. `typology`, `estate_type`, `floor`, `gender`,
  `country_iso`) ne sont pas répliquées côté Pydantic : une valeur hors liste est acceptée
  par FastAPI puis rejetée par PostgreSQL avec une erreur `409` peu explicite.
* Pas de pagination sur les routes de liste (`GET /estates` renvoie **2 556** lignes
  d'un coup avec le jeu de données actuel).
