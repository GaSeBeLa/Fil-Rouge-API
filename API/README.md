
# API — Fil Rouge Immobilier

API REST (FastAPI + SQLModel) exposant les 21 tables du schéma PostgreSQL
`fil_rouge_immobilier` (voir [`../docker/init-v3/01_create_fil_rouge_immobilier.sql`](../docker/init-v3/01_create_fil_rouge_immobilier.sql)).

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
DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/fil_rouge_immobilier
```

`+psycopg2` est obligatoire : depuis SQLAlchemy 2.1, `postgresql://` seul cherche
psycopg 3, qui n'est pas installé.

`<user>` et `<password>` sont ceux définis dans `docker/.env` (`POSTGRES_USER` /
`POSTGRES_PASSWORD`). Si le mot de passe contient des caractères spéciaux
(`/`, `@`, `:`...), il doit être encodé pour l'URL, par exemple :

```bash
python3 -c "import urllib.parse; print(urllib.parse.quote('<mot_de_passe>', safe=''))"
```

Sans `.env`, l'API se connecte par défaut à `postgresql+psycopg2://postgres:postgres@localhost:5432/fil_rouge_immobilier`
(la valeur par défaut du `docker-compose.yml`).

⚠️ `.env` n'est jamais commité (voir `.gitignore` à la racine du repo) — seul `.env exemple` l'est.

🔑 **`JWT_SECRET`** (ADR-052) : le secret qui signe les jetons de connexion,
**32 caractères au moins** (`openssl rand -hex 32`). Absente ou trop courte,
l'API **refuse de démarrer**. Avec Docker, elle vient de `docker/.env` (modèle :
`docker/.env.exemple`) ; en local, ajoute-la au `.env` de `API/`.

🔑 **`API_KEY_<NOM>`** (ADR-028, points 4 à 6) : **une clé par programme** qui appelle
l'API — aujourd'hui `API_KEY_INTERNAL` (l'API interne) et `API_KEY_APP_BACKEND` (le
back de l'app). L'API lit toutes les variables `API_KEY_*` ; **aucune** clé, ou une
clé de moins de 32 caractères : elle **refuse de démarrer**. Une clé de plus = une
ligne dans `docker/.env` **et** une dans `docker-compose.yml`. La valeur se remet au
responsable du programme hors du dépôt et hors de Discord.

## Lancer l'API

### Avec Docker — recommandé, rien à installer

**Une seule fois, à la première installation** : copier `docker/.env.exemple`
sous le nom `docker/.env`, et y mettre ses propres mots de passe. Sans ce
fichier, `docker compose` affiche `variable is not set` et une base neuve ne
démarre pas.

```bash
cp docker/.env.exemple docker/.env
```

Le modèle explique chaque ligne. À retenir :

- `POSTGRES_DB` : garder `fil_rouge_immobilier`, l'API et les scripts l'attendent.
- `POSTGRES_PASSWORD` : jamais vide ; `MINIO_ROOT_PASSWORD` : 8 caractères au moins.
- `JWT_SECRET` : obligatoire, sinon l'API refuse de démarrer (`utils/security.py`).
- `API_KEY_INTERNAL` : la clé à coller dans le Swagger. Au moins une clé
  `API_KEY_<NOM>` doit avoir une valeur ; une clé laissée vide donne seulement un
  avertissement dans les logs (`utils/api_keys.py`).
- Chaque secret et chaque clé fait 32 caractères au moins : `openssl rand -hex 32`.
- `POSTGRES_READER_PASSWORD` : facultatif.

**Après un nouveau clone, le `.env` manque aussi** : git ne le suit jamais, le
clone ne l'apporte donc pas. Le recopier depuis l'ancien clone, ou repartir du
modèle. Piège : `docker compose up -d` affiche alors une série de
`The "POSTGRES_PASSWORD" variable is not set` (et de même pour `JWT_SECRET`, les
clés d'API, MinIO), **mais la base peut quand même dire `Healthy`**.
`docker-compose.yml` fixe le nom du projet (`name: fil_rouge_immobilier`) : Docker
reprend le volume de base déjà créé par un autre clone. Rien ne marche pour
autant, l'API n'a ni secret ni clé. Une fois le `.env` en place, depuis `docker/` :

- `.env` **recopié de l'ancien clone** : mêmes mots de passe que le volume
  existant, `docker compose up -d --build` suffit.
- `.env` **refait depuis le modèle**, avec d'autres mots de passe : le volume
  garde ceux de sa création, il faut repartir de zéro (⚠️ efface la base de dev
  locale) :

```bash
docker compose down -v && docker compose up -d --build
```

Dans les deux cas, puis depuis la racine du dépôt : `bash docker/create_test_db.sh`.

L'API est un service du `docker-compose` du projet. Depuis `docker/` :

```bash
docker compose up -d --build api
```

**Pourquoi `--build`** : l'image de l'API installe `requirements.txt` une seule
fois, quand elle est construite (`API/Dockerfile`). Sans `--build`,
`docker compose up -d` reprend l'image existante, même celle d'un autre clone
(le nom de projet est fixe). Après un `git pull` qui ajoute une dépendance,
l'API plante alors sur un module absent (vu le 2026-10-13 : `email-validator`,
ajouté par API4). `--build` ne coûte presque rien : si `requirements.txt` n'a
pas changé, Docker reprend sa couche en cache. Ne pas installer la dépendance
avec `pip` sur son poste : l'API tourne dans le conteneur.

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

**Au 2026-10-08** : **193 tests, `193 passed`** — 99 unitaires, 94 d'intégration
(chantier LOT, puis migrations 13 à 15 : `is_activated` et quartier → ville,
`hunter_rate_parameters`, clé du paiement vers ses réglages).

**Au 2026-10-12** : **258 passed, 7 skipped** (fiche API1) — 7 tests de connexion
ajoutés ; les 7 sautés sont ceux du seed, qui se lancent depuis `API/`, hors conteneur.
Puis **292 passed, 7 skipped** (fiche API4) : 18 tests de contrôles d'entrée. Avant :
**265 passed, 7 skipped** (fiche API2) : 7 tests de rôles ; puis **274 passed,
7 skipped** (fiche API3) : 9 tests de clés d'API. La fixture automatique
`api_test_key` pose une clé de test ; `client` et `db_client` l'envoient d'office.
Puis **308 passed, 7 skipped** (fiche API5) : 16 tests de versions figées et
d'ordre du paiement. Puis **332 passed, 7 skipped** : correctifs des deux relectures
de la série (lecture sans rejuger P16/P29, connexion au chronomètre, `NaN` et grands
entiers, `/users` et `/roles` à `Admin`, paiement pas à pas, créé `'announced'`, payé
figé). Puis **341 passed, 7 skipped** (fiche API6) : 11 tests d'auteurs, et les 2
anciens tests de la clé `estate.id_author` retirés (la valeur envoyée est ignorée).
Puis **358 passed, 7 skipped** (fiche API7) : 17 tests de propositions et de visites.
Puis **370 passed, 7 skipped** (fiche API8) : 12 tests de signature et de vente ;
`sale_payload` part d'un mandat neuf, signé, avec une offre `'accepted'`.
Puis **379 passed, 7 skipped** (fiche API9) : 9 tests de demande déposée avant le compte.
Puis **391 passed, 7 skipped** (fiche API10) : 15 tests d'anonymisation ; les 3 tests de
`DELETE` (routeur, `/users`, `/payments`) attendent désormais `405`.
Puis **393 passed, 7 skipped** (relecture de la série) : un renouvellement non signé
n'efface plus la fin du mandat signé ; le paiement seul garde le nom d'un chasseur.
Puis **398 passed, 7 skipped** (relecture, ADR-051) : la note d'un bien a pour auteur le
chasseur du jeton ; un `PUT` ne la donne plus à un autre ; Admin, Manager, Client → `403`.
Puis **399 passed, 7 skipped** (relecture) : `POST /search-requests/submit` répond pareil
à tous (`202`, sans id) ; un email de non-client est ignoré et logué.
Puis **433 passed, 8 skipped, 6 xfailed** (ADR-054, 2026-10-13) : 14 tests du contact du
vendeur (`estate_contact`).
Puis **443 passed, 8 skipped, 6 xfailed** (ADR-054, question 4, 2026-10-13) : le contact
anonyme 3 ans après la dernière activité du bien, Admin seul.
Puis **690 passed, 8 skipped, 6 xfailed** (fiche DRO1, 2026-10-13) : fermé par défaut ;
241 tests de droits par rôle, et 6 dans `test_roles.py` (routeur sans rôles fermé aux
5 rôles, `/roles` fermé aussi à l'Admin). Les tests qui créaient en
`Admin` passent par le rôle qui crée.
Puis **770 passed, 8 skipped, 6 xfailed** (fiche DRO2, 2026-10-13) : l'argent réservé à qui
l'annexe le donne ; 80 tests de droits de plus (tables d'argent, calcul réservé à l'Admin).
Puis **774 passed, 8 skipped, 7 xfailed** (fiche DRO3, 2026-10-13) : les routes à part ;
4 tests de plus, et 1 `xfail` strict qui montre la limite du formulaire (Limites connues).
Puis **784 passed, 8 skipped, 7 xfailed** (fiche DRO4, 2026-10-13) : le mécanisme « le
sien », 6 tests dans `test_le_sien.py`, 4 tests unitaires du routeur et du service.
Puis **826 passed, 8 skipped, 7 xfailed** (fiche DRO5, 2026-10-13) : le Client limité à
ses lignes, 35 tests dans `test_le_sien.py` (13 tables, deux clients), 7 unitaires.
Puis **876 passed, 8 skipped, 7 xfailed** (fiche DRO6, 2026-10-13) : le Hunter limité à
ses lignes, 51 tests dans `test_le_sien.py` (13 tables, deux chasseurs).
Puis **897 passed, 8 skipped, 7 xfailed** (fiche DRO7, 2026-10-13) : le Manager limité à
son équipe. Puis **905 passed** (fiche DRO8) : les comptes désactivés réservés à l'Admin.
Puis **910 passed, 8 skipped, 7 xfailed** (fiche DRO9, 2026-10-13) : `fil_rouge_reader`
fermé sur `payment` et sur les comptes désactivés, 5 tests dans `test_lecteur_sql.py`.
Puis **911 passed, 8 skipped, 6 xfailed** (fiche DRO11, 2026-10-13) : la fuite du
formulaire fermée, le `xfail` de DRO3 passe.
Puis **948 passed, 0 skipped, 7 xfailed** (chantier DEM, 2026-10-14) : le seed de démo
et ses 13 tests ; les 8 tests du seed des paramètres (`test_seed_parametres.py`,
`test_parametrage_service.py`) tournent aussi dans le conteneur, qui monte `init-v3`
depuis BAN2.

⚠️ Depuis API2, les fixtures `client` et `db_client` se présentent en **`Admin`**
(`get_principal` remplacé, voir [`tests/conftest.py`](tests/conftest.py)) : un test
de droits utilise `principal_as(<rôle>)`, ou retire ce remplacement. Depuis API6,
`with acting_as(<rôle>, <id>):` fait agir sous un compte du seed (le chasseur 1 crée
les biens : `post_as_hunter` dans `test_constraints_db.py`). Depuis DRO1, `Admin` ne
crée plus la plupart des tables : chaque `POST` d'un test passe par le rôle qui le
peut (`post_as_hunter`, `post_as_client`, `post_as_creator`, `post_as_manager` pour
les ventes). `POST /payments` étant fermé à tous (DRO2), les tests de paiement écrivent
par le service (`write_payment`) : un refus y est un `ConflictError`, le `409` de la route.

| Fichier | Ce qu'il prouve |
|---|---|
| [`test_health.py`](tests/test_health.py) | `/` répond |
| [`test_security.py`](tests/test_security.py) | hachage argon2 : jamais de clair, sel aléatoire, comptes migrés refusés sans exception, `needs_rehash` |
| [`test_user_service.py`](tests/test_user_service.py) | le mot de passe n'atteint jamais le repository en clair ; mise à jour partielle |
| [`test_base_service.py`](tests/test_base_service.py) | id inexistant → `NotFoundError` **avant** toute écriture ; la condition du crochet « le sien » part au repository, sauf pour l'Admin (DRO4) ; une ligne que le crochet `owns` refuse n'est ni créée ni modifiée, sauf par l'Admin (DRO5) |
| [`test_base_repository.py`](tests/test_base_repository.py) | `id` ignoré au `POST` ; `IntegrityError` → rollback + `ConflictError` |
| [`test_user_models.py`](tests/test_user_models.py) | mot de passe ≥ 12 caractères ; `UserPublic` sans `password` |
| [`test_crud_router.py`](tests/test_crud_router.py) | 404 / 409 / 201 / 422 sur un routeur factice ; `DELETE` → `405` (ADR-049) ; les deux `GET`, le `POST` et le `PUT` passent le compte au service (DRO4, DRO5) ; `ForbiddenError` au `PUT` → `403` |
| [`integration/test_auth.py`](tests/integration/test_auth.py) | connexion : jeton rendu ; mauvais mot de passe, compte inactif, jeton expiré ou forgé → `401` ; compte désactivé **après** l'émission du jeton → `401` (relu en base) |
| [`test_roles.py`](tests/test_roles.py), [`integration/test_roles_db.py`](tests/integration/test_roles_db.py) | sans jeton → `401` ; `Reader` lit (`200`) mais n'écrit pas (`403`) ; `Admin` crée (`201`) ; un routeur sans rôles déclarés → `403` pour les 5 rôles (DRO1) ; `/hunter-performances` et `/roles` fermés en écriture ; `/users` créé par l'Admin seul, modifié par l'Admin, le Client et le Hunter (DRO5, DRO6) ; `/` et `/auth/login` ouverts |
| [`integration/test_droits_par_role.py`](tests/integration/test_droits_par_role.py) | la grille de l'annexe d'ADR-027, recopiée à la main : chaque case fermée → `403` en lecture (liste et ligne), création, modification ; chaque case ouverte ≠ `403` ; au moins un refus par table (DRO1) ; tables d'argent, et `POST /sales/{id}/payment` réservé à l'Admin (DRO2) ; chaque route hors CRUD nommée avec le test qui la juge, `/` ne rend qu'un statut, `/auth/login` qu'un jeton (`sub`, `iat`, `exp`), `/auth/me` le seul compte du jeton, même avec un id dans l'URL (DRO3) ; formulaire mal formé → `409` quel que soit l'email (neuf, client, chasseur), bien formé → `202` sans compte ni fiche de plus (DRO11) |
| [`integration/test_le_sien.py`](tests/integration/test_le_sien.py) | « le sien » sur `/payments` (DRO4) : un Hunter liste ses paiements seulement, `404` sur celui d'un autre chasseur (même réponse qu'un id absent), refus au service en modification ; l'Admin voit tout. Le Client (DRO5) : deux clients du seed, une ligne chacun dans les 13 tables de sa colonne ; chacun liste les siennes, `404` sur celles de l'autre ; `PUT` du mandat d'un autre → `404` ; son mandat passé à un autre client, une fiche client ou une demande pour un autre compte, des critères sur la demande d'un autre, sa proposition déplacée sur le mandat d'un autre → `409` ; son rôle ou son activation → `403`. Le Hunter (DRO6) : chasseurs 1 et 2, une ligne chacun dans les 13 tables où sa colonne dit « le sien » ; même preuve ; biens et photos lisibles en entier, barème par défaut visible, son seul manager ; `PUT` de la ligne d'un autre → `404` (7 tables) ; une ligne au nom d'un autre → `409` (6 tables), un mandat sur la demande d'un autre aussi ; hors de ses coordonnées (même un champ omis), son rôle, son média sur la note d'un autre → `403` |
| [`test_api_keys.py`](tests/test_api_keys.py) | sans clé ou clé inconnue → `401` ; bonne clé et bon jeton → `200` ; bonne clé sans jeton → `401` ; `/` sans clé ; démarrage refusé sans clé ou clé trop courte |
| [`test_entrees.py`](tests/test_entrees.py) | `422` avant la base : email mal formé (P2), plus de chambres que de pièces (P16), réglages du taux incohérents — poids ≠ 1, plancher > plafond, paliers mal formés (P29), détail du calcul mal formé (P32) |
| [`integration/test_versions_paiement.py`](tests/integration/test_versions_paiement.py) | grille d'honoraires, ligne de barème, réglages du taux : citée → `PUT` `409`, non citée → `200` (ADR-030, ADR-034) ; statut du paiement : pas à pas → `200` ; saut, retour en arrière, refus après `'announced'`, paiement `'paid'` modifié ou supprimé → `409` (ADR-038) ; paiement créé au-delà de `'announced'`, ou au taux final faux → refusé par le service, `ConflictError` (ADR-038, P33 ; `POST /payments` est fermé à tous, fiche DRO2) ; `DELETE` → `405` (ADR-049) |
| [`integration/test_auteurs.py`](tests/integration/test_auteurs.py) | `POST /estates` en Hunter ou Manager → `id_author` = le compte du jeton, la valeur envoyée ignorée ; Client, Admin, Reader → `403` ; un `PUT` garde l'auteur (ADR-047) ; `POST /review-media` par le chasseur de la note → `201`, un autre chasseur ou un autre rôle → `403` (ADR-051) ; la note a pour auteur le chasseur du jeton, un `PUT` de la note d'un autre chasseur → `404` (DRO6), les autres rôles → `403` |
| [`integration/test_contact_vendeur.py`](tests/integration/test_contact_vendeur.py) | `/estate-contacts` : Hunter, Manager, Admin lisent et écrivent ; Client et Reader → `403`, même en lecture ; `id_author` = le compte du jeton, gardé par un `PUT` ; second contact pour un bien, téléphone hors ADR-007, ligne sans aucun renseignement → `409` ; `is_private` obligatoire (`422`), gardé avec l'agence ; `fil_rouge_reader` ne lit pas la table ; `POST /estate-contacts/anonymize-expired` : gardé avant 3 ans, anonyme après, une activité plus tardive repousse, rejouée → 0, non-`Admin` → `403` (ADR-054) |
| [`integration/test_lecteur_sql.py`](tests/integration/test_lecteur_sql.py) | le rôle PostgreSQL `fil_rouge_reader` (DRO9) : `SELECT` sur `payment` → `permission denied` (ADR-027, point 8) ; un compte désactivé absent de `"user"`, `client`, `hunter`, `real_estate_manager`, présent une fois activé (point 7) ; l'API, en `postgres`, le lit toujours |
| [`integration/test_propositions_visites.py`](tests/integration/test_propositions_visites.py) | proposition : bien hors de la sélection de la demande du mandat → `409` (P19), mandat non `'active'` → `409` (P20), un `PUT` qui change de bien repasse P19 ; visite `'client'` sur un bien jamais proposé → `409`, visite `'hunter'` libre (P23) ; visite après la fin du mandat → `409`, mandat annulé dans ses dates → `201` (P25) ; avant la signature, ou mandat non signé → `409` (ADR-044) |
| [`integration/test_signature_vente.py`](tests/integration/test_signature_vente.py) | mandat signé (créé signé ou par `PUT`) → demande `'launched'`, mandat refusé → demande inchangée (ADR-044) ; vente sur mandat non signé → `409` (Q-MAN-06) ; vente `'hunter'` sans offre `'accepted'` → `409`, `'client_alone'` libre (P27) ; vente → mandat `'completed'`, vente refusée → mandat inchangé (P28) ; grille qui n'est pas celle en vigueur à la date de l'acte → `409` (ADR-030) |
| [`integration/test_demande_avant_compte.py`](tests/integration/test_demande_avant_compte.py) | formulaire neuf → user **inactif** (mot de passe factice), fiche client et demande `'confirmed'` ; connexion refusée ; même email en majuscules → même compte (P2) ; email d'un client connu → sa fiche **n'est pas réécrite** ; email d'un chasseur → ignoré et logué (l'id, pas l'email) ; **même réponse** `202` pour tous ; adresse manquante → `422` ; refus de la base au milieu → `409` et **0 ligne** écrite ; `PUT /users/{id}` active le compte ; clé d'API exigée, pas de jeton (P5) |
| [`integration/test_anonymisation.py`](tests/integration/test_anonymisation.py) | `POST /users/{id}/anonymize` : client sans mandat → **tout** anonyme, compte désactivé, connexion refusée ; nom gardé **10 ans** après la fin du dernier mandat **signé** de la chaîne (un renouvellement pas encore signé n'efface pas la fin d'avant) ou le paiement (seul, pour un chasseur dont les mandats sont finis depuis longtemps) (versé, ou pas encore : à partir d'aujourd'hui), reste anonyme tout de suite ; commentaire du client et motif des critères vidés ; rappelée après le délai → nom « Anonyme » ; non-`Admin` → `403` ; `DELETE /clients/1` → `405` (ADR-049) |
| [`test_remuneration.py`](tests/test_remuneration.py) | les **55 cas** de [`10_calcul_remuneration_chasseur.feature`](../user-stories/10_calcul_remuneration_chasseur.feature), lignes d'exemples recopiées telles quelles |
| [`integration/test_banc_v2_v3.py`](tests/integration/test_banc_v2_v3.py) | le banc « base neuve = base migrée » : `init-v2` + migrations d'un côté, `init-v3` de l'autre, deux bases jetables jouées par `psql` ; colonnes, contraintes, index, triggers, fonctions et nombre de lignes (hors démo) identiques, sinon le diff ; `fil_rouge_reader` remis dans son état ([`docker/init-v3/README.md`](../docker/init-v3/README.md) §10) |
| [`integration/test_calcul_paiement.py`](tests/integration/test_calcul_paiement.py) | comptages purs : chaîne de renouvellements comptée une fois, première issue (vente, clôture, échéance), vente refusée, vente en cours exclue, fenêtre, visites `'client'` seules (ADR-048) ; `POST /sales/{id}/payment` → montant = `calculer_remuneration` sur les mêmes nombres, 2e appel → `409`, vente inconnue → `404`, hors dispositif → paiement `'refused'` ; note `'payment'` du journal absente tant que le paiement n'est pas `'paid'`, écrite au passage (ADR-035) |

**Calcul de la rémunération** : [`services/remuneration.py`](src/app/services/remuneration.py)
est le code de référence **du sujet**, extrait tel quel de `REGLES-CALCUL-REMUNERATION.md`
§14.2-14.3, à un écart près : le critère « mandats » noté par le taux de transformation
(ADR-048, voir sa docstring). Fonction pure, branchée sur la base par
[`services/payment_calculation_service.py`](src/app/services/payment_calculation_service.py)
(fiche API12).

**Pour écrire un test** :
- la fixture `client` ([`tests/conftest.py`](tests/conftest.py)) donne un `TestClient`
  sur la vraie app — `def test_xxx(client): ...` ;
- la fixture `fast_hasher` remplace argon2 (~300 ms par hash) par un hacheur faible ;
- pour isoler de la base : `MagicMock(spec=<Repository>)` à la place du repository,
  ou `app.dependency_overrides[get_session]` à la place de la session.

### Tests d'intégration — base de test isolée

Les tests de [`tests/integration/`](tests/integration/) tournent contre une vraie base
PostgreSQL, **`fil_rouge_test`** — jamais la base de dev. Avant la première fois, et
après toute modification de `docker/init-v3/01` ou `02` :

```bash
bash docker/create_test_db.sh
```

* **Même conteneur, autre base** : `01` + `02` rejoués, donc les mêmes contraintes
  que la base de dev ; pas le `03` (aucun bien).
* **Tout est annulé** : chaque test tourne dans une transaction annulée à la fin
  (fixture `db_session`) ; utiliser `db_client` au lieu de `client` pour que l'API
  écrive dedans. Mesuré : comptes de `fil_rouge_test` et `fil_rouge_immobilier`
  identiques avant et après la suite.
* **Base absente ou `db` arrêté** : ces tests sont **sautés** (`skipped`),
  avec la commande à lancer. Les écarter : `-m "not integration"`.

⚠️ La fixture `client` reste branchée sur la **vraie** base de dev : un test qui
écrit via `client` y écrit pour de bon. Pour écrire, toujours `db_client`.

**La suite, dans l'ordre** (chaque étape s'appuie sur la précédente) :
1. ✅ tests unitaires purs — la logique, sans base ;
2. ✅ base de test isolée — les contraintes PostgreSQL (FK, `CHECK`, `UNIQUE`) ;
3. ✅ calculette de rémunération — les 55 cas du sujet ;
4. ✅ calculette branchée sur la base (fiche API12) : `POST /sales/{id}/payment`
   lit le barème et écrit le paiement, testé sur la base de test
   ([`integration/test_calcul_paiement.py`](tests/integration/test_calcul_paiement.py)).

## Architecture

Chaque table suit une architecture en 3 couches (Router → Service → Repository) :

* **`routes/<table>_router.py`** — reçoit la requête HTTP, traduit les erreurs métier
  (`NotFoundError`, `ConflictError`, `ForbiddenError`) en codes HTTP (404, 409, 403)
* **`services/<table>_service.py`** — logique métier (aujourd'hui minimale, sauf
  `user_service.py` qui hache le mot de passe)
* **`repositories/<table>_repository.py`** — parle à la base via SQLModel/PostgreSQL,
  rien d'autre

Ces trois couches héritent chacune d'une classe générique (`routes/crud_router.py`,
`services/base_service.py`, `repositories/base_repository.py`) qui porte le
comportement CRUD commun aux 21 tables.

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
│       │   └── exceptions.py     # NotFoundError, ConflictError, ForbiddenError
│       ├── models/                # une classe SQLModel par table (20 fichiers)
│       ├── repositories/          # accès base : base_repository.py + 1 fichier par table
│       ├── services/              # logique métier : base_service.py + 1 fichier par table
│       └── routes/                # routage HTTP : crud_router.py + 1 fichier par table
└── tests/
    ├── conftest.py              # fixtures client, fast_hasher
    ├── test_*.py                # tests unitaires, voir § Tests
    └── integration/             # conftest (db_session, db_client) + un fichier par sujet
```

## Endpoints

Les 21 tables ont les **mêmes 4 routes**, construites par
[`routes/crud_router.py`](src/app/routes/crud_router.py) : `GET` (liste),
`GET /{id}`, `POST`, `PUT /{id}`. **Plus de `DELETE`** (ADR-049, fiche API10) : un
`DELETE` rend `405`. Plus `GET /` (health-check), `/auth`, la demande avant le compte
et l'anonymisation (d'un compte, des contacts de vendeur), et le calcul du paiement
d'une vente. Soit **91 opérations** (compté dans `/openapi.json` le 13/10/2026).

Dans le Swagger, **chaque opération a un titre et une description** : ce qu'elle fait,
qui peut l'appeler, et ce que veut dire chaque code de réponse. Chaque section (table)
a aussi sa phrase d'explication. Les routes communes tirent leur texte de
[`routes/crud_router.py`](src/app/routes/crud_router.py) ; les sections, de
[`main.py`](src/app/main.py) (`OPENAPI_TAGS`).

| Ressources |
|---|
| `/users` `/roles` `/hunters` `/clients` `/real-estate-managers` |
| `/search-requests` `/criteria` `/mandates` `/estates` `/estate-proposed` |
| `/estate-search-requests` `/pictures` `/visits` `/sales` `/payments` |
| `/commission-scales` `/parameters-fees` `/hunter-rate-parameters` `/hunter-performances` `/review-media` |
| `/estate-contacts` |

### Avoir un compte et un jeton — à faire une fois

Pour appeler l'API, il faut un **jeton**, et pour avoir un jeton, un **compte actif**.
Or la base de dev n'en a **aucun** : les comptes repris ont un faux mot de passe.
Et seul un `Admin` peut créer un compte par l'API. Le script
[`scripts/create_admin.py`](src/app/scripts/create_admin.py) crée donc le premier
compte `Admin`, directement dans **votre** base locale.

**1. Créer son compte Admin** (une seule fois par base), depuis `docker/`, le
conteneur `api` lancé :

```bash
docker compose exec api python -m src.app.scripts.create_admin
```

- Il demande l'email, puis le mot de passe deux fois, sans l'afficher.
- Mot de passe : **12 caractères** au moins. Il n'est gardé qu'haché (Argon2).
- Email déjà pris, email invalide, mot de passe trop court : le script le dit, et
  rien n'est créé.
- ⚠️ Sous **Git Bash**, si docker répond « the input device is not a TTY », mettre
  `winpty` devant la commande, ou la lancer depuis **PowerShell**.
- ⚠️ `docker compose down -v` efface la base, et le compte avec : relancer le script.

**2. Prendre un jeton** dans le Swagger (http://localhost:8000/docs) :

1. **Authorize** → `APIKeyHeader` : la clé `API_KEY_INTERNAL` de `docker/.env`.
2. `POST /auth/login` avec votre email et votre mot de passe → copier `access_token`.
3. **Authorize** → `HTTPBearer` : coller le jeton **seul**, sans le mot `Bearer`.

Le jeton dure **60 minutes** : ensuite, refaire l'étape 2. En `Admin`, vous pouvez
ensuite créer d'autres comptes avec `POST /users`, pour essayer les autres rôles
(`Client`, `Hunter`, `Manager`, `Reader`).

### Seed de démo — un parcours complet, en une commande

Le script [`scripts/seed_demo.py`](src/app/scripts/seed_demo.py) remplit **votre**
base de dev avec un parcours de bout en bout, joué par les vrais services :
demande et critères, sélection de biens, mandat signé, propositions, visites,
offre acceptée, vente, paiement calculé puis payé, note du chasseur, avis.
Données fausses (Faker `fr_FR`, graine fixe) : mêmes données à chaque base neuve.

**1. Le mot de passe des comptes de démo**, une fois : dans `docker/.env`,

```bash
DEMO_PASSWORD=<12 caractères au moins>
```

puis, depuis `docker/` : `docker compose up -d --build` (le paquet `faker` et
la variable n'arrivent dans le conteneur qu'au rebuild).

**2. Semer**, depuis `docker/` :

```bash
docker compose exec api python -m src.app.scripts.seed_demo
```

**3. Se connecter** (`POST /auth/login`, voir plus haut) avec l'un des 4 comptes,
tous activés, mot de passe `DEMO_PASSWORD` :

| Compte | Rôle |
|---|---|
| `demo-client@example.com` | `Client` |
| `demo-chasseur@example.com` | `Hunter` (rattaché au manager de démo) |
| `demo-manager@example.com` | `Manager` |
| `demo-lecteur@example.com` | `Reader` |

- Le script ne sème qu'**une fois par base** : si un compte de démo existe, il
  s'arrête sans rien écrire. Pour resemer : `docker compose down -v`, `up -d`.
- Il refuse d'écrire dans la base de test `fil_rouge_test` : **aucun test ne
  dépend du seed**.
- Un refus d'une règle (`409`) l'arrête avec son message : on corrige les
  données du seed, jamais la règle.

### Connexion — `/auth` (ADR-052)

| Route | Ce qu'elle fait |
|---|---|
| `POST /auth/login` | `{"email", "password"}` → `{"access_token", "token_type": "bearer", "expires_in": 3600}` ; mauvais identifiants **ou** compte non activé : `401`, même message |
| `GET /auth/me` | le compte du jeton (`Authorization: Bearer <jeton>`), sans `password` ; jeton absent, faux, expiré, ou compte désactivé depuis : `401` |

* Jeton JWT `HS256`, valable **60 minutes**, sans jeton de rafraîchissement.
* La dépendance `get_current_user` ([`current_user.py`](src/app/utils/current_user.py))
  **relit le compte en base à chaque appel** : rôle et activation du moment font foi.
* 🔒 **Toutes les routes CRUD exigent le jeton** (fiche API2, ADR-028) : sans jeton
  `401`.
* 🚪 **Fermé par défaut** (fiche DRO1) : une table ne s'ouvre qu'aux rôles qu'elle
  déclare (`read_roles`, `write_roles`, `create_roles` de `build_crud_router`) ; les
  autres → `403`. Les rôles viennent de l'annexe d'ADR-027
  (`md/adr/adr-027-annexe-matrice-detaillee.md`, dépôt Fil-Rouge), **au niveau du
  rôle**. « Le sien » (ADR-027, point 2 ; fiche DRO4) : les deux `GET` et le `PUT`
  passent le compte au service, dont le crochet `visible_rows` filtre les lignes **dans
  la requête SQL** ; la ligne d'un autre rend `404`, comme une ligne absente. L'Admin
  voit tout. Branché sur `/payments` (un Hunter, ses paiements seulement) et, pour le
  Client, sur les 13 tables de sa colonne (fiche DRO5) : son compte, sa fiche, son
  chasseur, ses demandes et leurs critères, ses mandats, les biens proposés pour lui
  (Q-ACC-05) et leurs photos, l'avis sur sa demande et ses médias, ses visites, sa
  vente. Les chemins, par les clés du schéma : `services/client_rows.py`. En écriture
  (`POST`, `PUT`), le crochet `owns` refuse une ligne qui ne serait pas à lui → `409`
  (ex. un mandat passé à un autre client) ; changer son rôle ou son activation → `403`.
  Pour le Hunter (fiche DRO6), sur 13 tables : son compte et sa fiche, ses clients (H3),
  ses demandes et leurs critères, ses mandats, ses notes et leurs médias, ses
  propositions, les visites et ventes de ses mandats, sa note de performance, le
  barème par défaut et le sien (Q-ACC-06), son manager ; les biens et leurs photos
  restent lisibles en entier (H2, H5). Chemins : `services/hunter_rows.py`. Il ne
  change de sa fiche que ses coordonnées (`HunterService`, `CONTACT_FIELDS` → `403`).
  Pour le Manager (fiche DRO7), le travail de **son équipe** (ADR-027, annexe) : ses
  chasseurs (`hunter.id_realestatemanager`) et les demandes qui lui sont confiées
  (`search_request.id_realestatemanager`). Il lit ses chasseurs, les demandes de
  l'équipe et leurs critères, ses mandats, leurs visites et leurs ventes, et ce qui suit
  ses chasseurs : paiements (Q-ACC-02), notes, barèmes (le leur et celui par défaut) ;
  plus son compte et sa fiche. Chemins : `services/manager_rows.py`, qui reprend ceux
  du chasseur. En écriture : il affecte une demande à l'un de ses chasseurs seulement
  (Q-ACC-10 ; un autre champ → `403`, hors équipe → `409`), enregistre une vente de
  son équipe (Q-ACC-03, sinon `409`), change ses coordonnées et son compte, sans rôle ni
  activation (`403`). Client, sélection et avis lui restent fermés (fiche DRO1).
  Compte désactivé (ADR-027, point 7 ; fiche DRO8) : son profil (`/users`, `/clients`,
  `/hunters`, `/real-estate-managers`) n'est plus lu que par l'**Admin** ; pour tout
  autre rôle, `Reader` compris, il sort des listes et rend `404`. Les lignes qui le
  citent (demande, mandat, vente) restent lisibles. ⚠️ Les 25 comptes du seed sont
  désactivés (migrés sans mot de passe) : en dev, leurs profils sont cachés aux
  non-Admin jusqu'à leur activation ; les tests les activent dans leur transaction
  (`db_client`, `tests/integration/conftest.py`).
  Le compte PostgreSQL `fil_rouge_reader`, en SQL direct, suit `Reader` (fiche DRO9) : ni
  `payment`, ni les comptes désactivés (politique par ligne), ni le mot de passe, ni
  `estate_contact` (`docker/init-v3/04_role-lecture-seule.sql`). Relevé complet et
  écarts : `md/securite/matrice-droits-crud-par-role.md` (dépôt Fil-Rouge).

  | Table | Lire | Créer | Modifier |
  |---|---|---|---|
  | `/roles` | Admin, Reader | personne | personne |
  | `/users` | tous | Admin | Admin, Client, Hunter, Manager (son compte, sans rôle ni activation) |
  | `/clients` | Admin, Client, Hunter, Reader | Client | Admin, Client |
  | `/hunters` | tous | Admin | Admin, Hunter (ses coordonnées) |
  | `/real-estate-managers` | Admin, Hunter, Manager, Reader | Admin | Admin, Manager (ses coordonnées) |
  | `/search-requests` | tous | Client, Hunter | Hunter, Manager (affecter un chasseur) |
  | `/criteria` | tous | Client, Hunter | personne (nouvelle version) |
  | `/mandates` | tous | Hunter | Admin, Client, Hunter |
  | `/estates`, `/pictures` | tous | Hunter, Manager | Admin |
  | `/estate-search-requests`, `/review-media` | Admin, Client, Hunter, Reader | Hunter | Hunter |
  | `/estate-proposed` | Admin, Client, Hunter, Reader | Hunter | Client, Hunter |
  | `/visits` | tous | Hunter | Admin |
  | `/hunter-performances` | Admin, Hunter, Manager, Reader | personne (ADR-035) | personne |
  | `/estate-contacts` | Admin, Hunter, Manager | Admin, Hunter, Manager | Admin, Hunter, Manager |
  | `/parameters-fees`, `/commission-scales`, `/hunter-rate-parameters` | Admin, Hunter, Manager, Reader | Admin | Admin |
  | `/payments` | Admin, Hunter, Manager | personne ¹ | Admin |
  | `/sales` | tous | Manager | personne |

  ¹ Un paiement n'est jamais saisi à la main (ADR-027, point 10) : il naît du calcul,
  `POST /sales/{id}/payment`, réservé à l'**Admin** (fiche DRO2). Ni Client ni Reader
  ne lisent les paiements (point 8).
  Écart à l'annexe : elle donne au Client « C son compte » sur `user` ; il le fait par
  `POST /search-requests/submit`, sans jeton (Q-ACC-12). `POST /users` reste à
  `Admin` : ouvert au Client, il lui laisserait choisir `id_role`, donc se créer un Admin.
  La description « Qui peut » de chaque route, dans `/docs`, suit ces rôles seule.
  Routes à part (fiche DRO3) : `GET /` ouverte à tous ; `POST /auth/login` et
  `POST /search-requests/submit`, clé d'API sans jeton ; `GET /auth/me`, tout compte
  connecté, son compte seul ; les deux anonymisations et le calcul du paiement,
  `Admin` seul. Chacune dit pourquoi dans son commentaire.
* ✍️ **Auteurs** (fiche API6) : `POST /estates` réservé à **Hunter** et **Manager**
  (ADR-047) ; `id_author` est rempli avec le compte du jeton, la valeur envoyée est
  ignorée, et un `PUT` ne la change pas ; vide = bien importé. `POST /review-media`
  réservé au **chasseur qui a écrit la note** (`estate_searchrequest.id_hunter`,
  ADR-051) : un autre compte → `403`. La note elle-même : `POST /estate-search-requests`
  réservé à **Hunter**, `id_hunter` = le compte du jeton, gardé par un `PUT`
  (relecture de la série API6 → API10).
* 📇 **Contact du vendeur** (ADR-054) : `/estate-contacts`, 0 ou 1 par bien, **lu et
  écrit** par **Admin**, **Hunter** et **Manager** seulement ; **Client** et **Reader** → `403`,
  même en lecture (données personnelles d'un tiers). `id_author` = le compte du jeton,
  gardé par un `PUT`. `POST /estate-contacts/anonymize-expired` (**Admin**, à la main) :
  le contact devient anonyme **3 ans** après la dernière activité du bien (création,
  sélection, proposition, fin de mandat, visite, vente) ; la ligne reste.
* 🏠 **Propositions et visites** (fiche API7, règles entre tables dans les services,
  ADR-040) : on ne propose qu'un bien de la **sélection** de la demande du mandat
  (P19), sur un mandat **`'active'`** (P20). Une visite tombe **entre la signature et
  la fin** du mandat (ADR-044, P25 ; le statut n'est pas regardé), et une visite
  `'client'` porte sur un bien **proposé sur ce mandat** (P23). Refus → `409`.
* ✒️ **Signature et vente** (fiche API8) : un mandat qui reçoit sa `signature_date`
  passe sa demande à **`'launched'`** (ADR-044). Une vente exige un mandat **signé**
  (Q-MAN-06), une offre **`'accepted'`** sur ce bien et ce mandat si elle est `'hunter'`
  (P27), et la grille d'honoraires **en vigueur à la date de l'acte** (ADR-030) ; refus
  → `409`. Une vente créée passe son mandat à **`'completed'`** (P28). Ces écritures
  doubles tiennent dans **une seule transaction** (`BaseRepository.stage`).
* 📝 **Demande avant le compte** (fiche API9, P5) : `POST /search-requests/submit`
  reçoit le formulaire du site (email, nom, téléphone, adresse obligatoire) et crée,
  **en une transaction**, un user **inactif** au mot de passe factice
  (`PENDING_SIGNUP_PASSWORD`, refusé à la connexion), sa fiche client et la demande
  `'confirmed'`. Un email déjà connu, **aux majuscules près**, retrouve son compte, sans
  réécrire sa fiche ; un email de chasseur ou de manager est ignoré, et logué. **Même
  réponse pour tous** : `202` et `{"detail": "Demande reçue."}`, sans id (relecture
  de la série). Refus de la base en chemin → `409`, rien d'écrit, **quel que soit
  l'email** : un email connu rejoue d'abord le chemin d'un email neuf dans un SAVEPOINT
  annulé, pour que la base juge ses formats (fiche DRO11). Activation : `PUT /users/{id}` (mot de passe et
  `is_activated`). La route exige la clé d'API, **pas de jeton** ; les critères de la
  demande ne sont pas pris par le formulaire.
* 🧹 **Effacer un compte** (fiche API10, ADR-049) : `POST /users/{id}/anonymize`,
  **Admin** seul. Le compte est désactivé ; email (`anonyme-<id>@exemple.invalid`), mot de
  passe (pas une empreinte : aucune connexion), téléphone (`+33000000000`), adresse
  (`'anonyme'`, `'00000'`, `'anonyme'`, `'FR'`), naissance et situation, commentaires du
  client et motifs des critères qu'il a écrits deviennent anonymes **tout de suite**.
  Prénom et nom attendent **10 ans** après la fin du dernier mandat de la chaîne, ou après
  le paiement ; la réponse dit jusqu'à quand (`names_kept_until`). Rappelée après ce jour,
  la route finit le travail : pas de tâche planifiée (V2).
* 💶 **Calculer le paiement d'une vente** (fiche API12) : `POST /sales/{id}/payment`,
  **Admin** seul (fiche DRO2). Compte en base les visites `'client'` de la chaîne du mandat, les
  ventes et les mandats du chasseur sur la fenêtre (ADR-048), charge le paramétrage à la
  date de l'acte, appelle `calculer_remuneration` et crée le paiement `'announced'` — ou
  `'refused'` avec son motif (ADR-024). Vente inconnue → `404` ; déjà payée ou paramétrage
  manquant → `409`. Le `PUT /payments/{id}` qui le passe à `'paid'` écrit la note
  `'payment'` du journal (ADR-035).
* 🔑 **Toutes les routes exigent aussi l'en-tête `X-API-Key`** (fiche API3),
  `/auth/login` compris : clé absente ou inconnue → `401`. La clé dit quel programme
  appelle, le jeton quelle personne agit : il faut les deux.
* Ouverts sans clé ni jeton : `GET /`, et la doc Swagger (`/docs`, `/redoc`, `/openapi.json`),
  laissée ouverte exprès pour que l'équipe teste dans le navigateur ; elle ne montre
  aucune donnée. `POST /auth/login` et `POST /search-requests/submit` : la clé, pas de jeton.
* Swagger : bouton **Authorize**, deux champs — `APIKeyHeader` (la clé) et
  `HTTPBearer` (le jeton seul, sans `Bearer`).

### Le paiement d'une vente, pas à pas

Pour qui découvre le projet. Quand une maison est vendue, le chasseur touche une
**commission**. L'API la **calcule seule** : personne ne tape de montant.

**Les étapes d'un paiement** (ADR-038), toujours dans cet ordre, sans en sauter :

```
POST /sales/{id}/payment  ──►  announced  ──►  scheduled  ──►  paid
                                   │
                                   └──►  refused   (pas de droit à commission)
```

| Statut | Ce que ça veut dire | Qui le pose |
|---|---|---|
| `announced` | le montant est calculé, le chasseur est prévenu | `POST /sales/{id}/payment` |
| `refused` | le chasseur n'a pas droit à la commission ; le motif est dans `refusal_reason` (ADR-024) | `POST /sales/{id}/payment`, ou un `PUT` depuis `announced` |
| `scheduled` | la date de versement est fixée (`scheduled_for`) | `PUT /payments/{id}` |
| `paid` | l'argent est versé (`paid_at`) ; le paiement **ne bouge plus** | `PUT /payments/{id}` |

**L'essayer dans le Swagger** (http://localhost:8000/docs) :

1. **Authorize** : la clé d'API et le jeton de `POST /auth/login` (voir plus haut),
   pris sur un compte **Admin** : le calcul et les `PUT /payments/{id}` lui sont
   réservés (fiche DRO2).
2. `POST /sales/{id}/payment` avec l'`id` d'une vente : rien à mettre dans le corps.
   La réponse est le paiement créé : `amount` (le montant en euros), les taux
   (`base_rate`, `seniority_rate`, `performance_rate`, `final_rate`) et
   `calculation_details` (le détail du calcul, pour pouvoir l'expliquer).
3. Rappeler la même route sur la même vente répond `409` : **une vente, un paiement**.
4. `PUT /payments/{id}` : renvoyer **tout** le paiement, avec `status` à `scheduled`
   et une date dans `scheduled_for`.
5. `PUT /payments/{id}` encore : `status` à `paid` et la date du jour dans `paid_at`.
   À ce moment, l'API écrit aussi la **note du chasseur** dans son journal
   (`hunter_performance`, ADR-035).

**Les erreurs les plus fréquentes** :

- `403` : le jeton n'est pas celui d'un Admin ;
- `404` : la vente n'existe pas ;
- `409` au `POST` : la vente a déjà un paiement, ou il manque un paramètre (barème,
  honoraires, réglages du taux) à la date de l'acte ;
- `409` au `PUT` : un saut d'étape (`announced` → `paid`), un retour en arrière,
  un paiement déjà `paid`, ou une date oubliée (`scheduled_for`, `paid_at`) ;
- `422` : le corps envoyé est mal formé (un champ manque, un type est faux).

**Où lire le code**, du plus simple au plus détaillé :

| Fichier | Son rôle |
|---|---|
| [`routes/sale_router.py`](src/app/routes/sale_router.py) | la route `POST /sales/{id}/payment` |
| [`services/payment_service.py`](src/app/services/payment_service.py) | les règles d'écriture : l'ordre des statuts, le taux final, la note du journal |
| [`services/payment_calculation_service.py`](src/app/services/payment_calculation_service.py) | compte les visites, ventes et mandats en base, puis appelle le calcul |
| [`services/parametrage_service.py`](src/app/services/parametrage_service.py) | lit les paramètres (barème, honoraires, réglages du taux) |
| [`services/remuneration.py`](src/app/services/remuneration.py) | le calcul lui-même, donné par le sujet : ne touche jamais à la base |

### Ce qu'un test doit attendre

Mesuré le 2026-10-02 contre l'API qui tourne (✅), ou lu dans le code (📖) :

| Cas | Code | `detail` renvoyé |
|---|---|---|
| liste, lecture | `200` | — |
| création réussie | **`201`** | — |
| id inexistant (`GET`, `PUT`) | `404` | `"<Entité> introuvable"`, ex. `"Chasseur introuvable"` ✅ |
| id non entier (`/hunters/abc`) | `422` | erreur Pydantic `int_parsing` ✅ |
| corps invalide au `POST` / `PUT` (type faux, champ obligatoire manquant, prix à virgule) | `422` | erreur Pydantic, ex. `int_from_float`, `missing` ✅ |
| règle d'une seule ligne violée (fiche API4) : email (P2), chambres > pièces (P16), réglages du taux (P29), détail du calcul (P32) — **à la saisie seulement** : une ligne déjà en base qui ne la respecte pas se relit en `200` ([`input_check.py`](src/app/models/input_check.py)) | `422` | `value_error`, message qui cite le `P<n>` ✅ |
| version citée modifiée (ADR-030, ADR-034), statut du paiement en arrière (ADR-038), taux final faux (P33) — fiche API5 | `409` | message qui cite l'ADR ou le `P33` ✅ |
| contrainte violée au `POST` / `PUT` (fiche FIN1) | `409` | la sorte de refus, puis le nom de la contrainte, ex. `"Cet email a déjà un compte (contrainte user_email_key)."` ; jamais la valeur refusée ([`constraint_messages.py`](src/app/utils/constraint_messages.py)) ✅ |
| erreur imprévue du serveur (fiche FIN1) | `500` | `"Erreur interne. Référence : <numéro>."` ; le même numéro dans le log, avec la pile ✅ |
| `DELETE`, sur n'importe quelle route (fiche API10, ADR-049) | `405` | `"Method Not Allowed"` ✅ |

✅ **Un champ obligatoire manquant donne `422`** (depuis le 2026-10-05) :
`POST /roles` avec `{}` renvoie `422`, `missing` sur `wording` (mesuré). Un
modèle de table SQLModel ne valide pas ce que FastAPI lui passe : avant ce
jour, ce cas finissait en `409`, et un prix `199999.5` était arrondi en
silence à `200000` par PostgreSQL. `_validated`
([`crud_router.py`](src/app/routes/crud_router.py)) revalide le corps avec
`model_validate`. Les `CHECK` du schéma, eux, restent vérifiés par PostgreSQL
seul (`409`).

⚠️ **Les 34 clés étrangères sont en `ON DELETE RESTRICT`** : supprimer un parent
encore référencé échoue toujours, même en SQL direct (l'API, elle, ne supprime plus rien).

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

* Droits : « le sien » est filtré pour le Client (fiche DRO5), le Hunter (fiches DRO4,
  DRO6) et le Manager (fiche DRO7) ; les comptes désactivés sont réservés à l'Admin
  (fiche DRO8). « Désactivé » ne distingue pas un compte effacé (ADR-049) d'un compte
  jamais activé, comme ceux du seed : les deux sont cachés.
* Le Client modifie son mandat et ses biens proposés **champ par champ sans limite** :
  l'annexe ne lui donne que signer (P3), commenter, prioriser, faire une offre (H6, H8).
  Seule l'appartenance est gardée (fiche DRO5).
* Un Hunter ne renouvelle pas le mandat d'un autre chasseur par l'API : il ne signe que
  sur ses demandes (fiche DRO6). La base l'accepte ; la réaffectation attend Jeff (Q-JEF-30).
* Le `PUT` recopie `created_at` du corps reçu, sur toute table (`BaseRepository.replace`) ;
  le garde des coordonnées du chasseur ne le regarde pas.
* TODO — pas de verrou entre un contrôle et l'écriture qui le suit (versions figées,
  ordre du paiement) : deux `PUT` simultanés sur le même paiement lisent tous deux
  `'announced'`, et le dernier écrit gagne. Correctif : `SELECT … FOR UPDATE` dans le
  repository avant le contrôle (relecture de la série API).
* Les contraintes `CHECK` du schéma SQL (ex. `typology`, `estate_type`, `floor`, `gender`,
  `country_iso`) ne sont pas répliquées côté Pydantic : une valeur hors liste est acceptée
  par FastAPI puis rejetée par PostgreSQL avec une erreur `409` peu explicite.
* Pas de pagination sur les routes de liste (`GET /estates` renvoie **2 556** lignes
  d'un coup avec le jeu de données actuel).
