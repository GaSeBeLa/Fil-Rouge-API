# `init-v2/` — schéma 18 tables, montants en euros

Ce dossier contient la chaîne complète de création et de peuplement de la base,
alignée sur le **MPD 03** (18 tables) et sur la convention **euros**.

Il ne remplace rien : `docker/init/` reste en place, intact. Les deux dossiers
coexistent tant que le groupe n'a pas validé le basculement.

| Fichier | Rôle | État |
|---|---|---|
| `01_create_fil_rouge_immobilier.sql` | schéma — 18 tables, 224 colonnes | testé, 0 erreur |
| `02_migration.sql` | données `Fil_Rouge_Depart` → cible | testé, 0 erreur |
| `03_populate_estate.sql` | 2 556 biens + 1 976 photos | testé, 0 erreur |

Vérifié de bout en bout sur PostgreSQL 16, dans cet ordre, sur une base vierge.

---

## 1. Pourquoi les euros, et pas les K€

C'est le changement structurant. Il ne vient pas d'une préférence, mais de
trois mesures sur les sources officielles.

### 1.1 Les fixtures officielles débordaient

`NUMERIC(6,1)` plafonne à **99 999,9**.

Dans `StarterPack - BASE/fixtures/PgSQL.sql` : **37 valeurs sur 47** dépassent
ce plafond, jusqu'à **700 000**. La base refusait donc le chargement des
données fournies avec le sujet (`numeric field overflow`).

### 1.2 Le barème officiel a des bornes à l'euro près

`user-stories/10_calcul_remuneration_chasseur.feature`, lignes 22-27 :

| montant min | montant max | taux |
|---|---|---|
| 0 | 199999 | 30 % |
| 200000 | 349999 | 35 % |
| 350000 | 499999 | 40 % |
| 500000 | 749999 | 45 % |
| 750000 | — | 50 % |

En K€ au dixième, `199999 €` devient `199,999` → arrondi à `200,0` → le bien
bascule à **35 % au lieu de 30 %**. Le barème était faussé à chaque borne.

Vérifié après correction : `199999` donne bien 30 %, `200000` donne 35 %.

### 1.3 L'arrondi au centime était impossible

La règle de rémunération impose un arrondi **au centime** (même fichier,
l. 253). Le dixième de K€ vaut 100 € : il l'interdisait.

**Conclusion.** La décision `D1` est tranchée en faveur de l'euro. La décision
`B` (K€) actée le 11/09/26 et marquée « à reconfirmer » est réfutée par les
sources officielles.

---

## 2. `03_populate_estate.sql` — deux changements

### 2.1 Les prix viennent de `price_eur`, pas d'une multiplication

`normalised/annonces_normalised.csv` contient **les deux** colonnes :

| colonne | min | max |
|---|---|---|
| `price` (K€) | 62.5 | 406.0 |
| `price_eur` (€) | 62 495 | 406 042 |

Le premier réflexe — multiplier les K€ par 1000 — **introduit une erreur**.
Mesuré : `62.5 × 1000 = 62 500`, alors que le prix réel est `62 495`.

> **2 531 biens sur 2 556** auraient eu un prix faux, avec un écart allant
> jusqu'à **50 €**.

Les 2 556 prix ont donc été repris **un par un depuis `price_eur`**, par
jointure sur la référence du bien. La base contient maintenant les valeurs
exactes du fichier source.

### 2.2 La colonne `energetic_score` a disparu

Elle n'existe pas dans le MPD 03, qui décrit l'énergie de façon plus fine :
`energy_class`, `energy_class_scheme`, `energy_class_date`, `energy_kwh_m2`,
`energy_co2_m2`.

Elle était `NULL` sur les 2 556 lignes : **aucune donnée n'est perdue**. La
colonne a simplement été retirée des `INSERT`.

> ➡️ À faire plus tard : alimenter `energy_class` depuis la colonne `dpe` du
> CSV, qui n'était pas exploitée par l'ancien script.

---

## 3. `02_migration.sql` — cinq changements

### 3.1 `role` : `libelle` → `wording`, valeurs capitalisées

Le schéma cible nomme la colonne `wording` et son `CHECK` n'accepte que
`'Admin'`, `'Client'`, `'Hunter'`, `'Manager'`.

| source | cible |
|---|---|
| `client` | `Client` |
| `hunter` | `Hunter` |
| `real_estate_manager` | `Manager` |

3 lignes. Le renommage `real_estate_manager` → `Manager` suit le `CHECK` du
MPD ; la table `real_estate_manager`, elle, garde son nom.

### 3.2 `criteria` : budgets convertis en euros

17 lignes. `320.0` devient `320000.00`. Ici la multiplication par 1000 est
**légitime** : contrairement aux annonces, la source ne fournit pas de colonne
en euros, et les budgets sont des montants ronds (`240.0` à `700.0`), saisis
au millier. Aucune précision n'est perdue.

### 3.3 `hunter.commission_rate` : retirée, mais pas effacée

La colonne n'existe plus dans le MPD 03 : la tarification vit désormais dans
`commission_scale` (barème de rémunération) et `parameters_fees` (honoraires).

**La valeur source est conservée en commentaire en fin de chaque ligne.**

⚠️ **Elle n'a délibérément PAS été migrée vers `commission_scale`**, parce que
son sens métier est ambigu :

| ce que contient la source | 2,00 · 2,50 · 2,75 · 3,00 · 3,25 |
|---|---|
| taux d'honoraires officiel | **3 %** → ça correspond |
| taux de rémunération chasseur | **30 à 50 %** → ça ne correspond pas |

Ces valeurs ressemblent donc à un **taux d'honoraires propre au chasseur**
(`parameters_fees.rate`), pas à un taux de commission. Les injecter dans
`commission_scale` aurait été un contresens métier.

> ❓ **À trancher par le groupe** : ces 6 valeurs sont-elles des honoraires ou
> une commission ? Une fois décidé, elles sont récupérables telles quelles dans
> les commentaires du script.

### 3.4 `hunter.hire_date` : hypothèse assumée

La colonne est `NOT NULL` dans le schéma cible et **absente de la source**.

Valeur retenue : `"user".created_at`, la seule date disponible pour un
chasseur (dates réelles obtenues : 2023-03-15 à 2025-11-03).

⚠️ C'est une **hypothèse de migration**, pas une donnée d'origine. Elle est
plausible — un chasseur reçoit son compte à son arrivée — mais elle reste à
confirmer. Elle est visible dans le script sous forme de sous-requête, pas
d'une valeur en dur, pour qu'on sache d'où elle vient.

### 3.5 `search_request.status` : hypothèse assumée

La colonne est `NOT NULL` et **absente de la source**. Valeur retenue :
`'confirmed'`, l'état d'entrée neutre parmi
`confirmed` / `accepted` / `rejected` / `launched`.

⚠️ Également une **hypothèse**. Une alternative défendable — une demande qui
porte déjà un mandat est « lancée » — est fournie en `UPDATE` commenté à la
fin du script :

```sql
-- UPDATE search_request sr SET status = 'launched'
--  WHERE EXISTS (SELECT 1 FROM mandate m WHERE m.id_search_request = sr.id);
```

---

## 4. ⚠️ Une contrainte du schéma a dû être corrigée

C'est le point qui demande une **décision du groupe**.

### Le problème, mesuré

Les **18 clients** de la source ont une **ville**, mais ni adresse de rue ni
code postal. Exemple : `Alice Martin`, `Montpellier`, adresse `NULL`.

La contrainte `ck_client_address_all_or_nothing` du script `01` exige que
`address`, `postal_code` et `town` soient **tous** renseignés ou **tous** nuls.
Elle rejette donc les 18 clients : la migration était impossible.

### Pourquoi la contrainte est trop stricte

Connaître la ville d'un client sans son adresse complète est un cas normal —
c'est même le cas général au début d'une relation commerciale.

La règle juste est une implication **à sens unique** :

> une adresse de rue n'a de sens qu'accompagnée d'un code postal et d'une
> ville ; l'inverse n'est pas vrai.

### Ce qui a été fait

`02_migration.sql` contient, juste après le `BEGIN` :

```sql
ALTER TABLE client DROP CONSTRAINT ck_client_address_all_or_nothing;
ALTER TABLE client ADD CONSTRAINT ck_client_address_all_or_nothing
    CHECK (address IS NULL OR (postal_code IS NOT NULL AND town IS NOT NULL));
```

Cet `ALTER` est **volontairement placé dans le `02`, et non dans le `01`**,
pour rester visible tant que le groupe n'a pas tranché. Une correction glissée
discrètement dans le schéma serait invisible en relecture.

**Deux suites possibles :**

| Option | Conséquence |
|---|---|
| ✅ valider la correction | la reporter dans `01`, supprimer ces 2 lignes du `02` |
| ❌ garder la contrainte d'origine | commenter l'`ALTER` et vider `town` sur les 18 clients — **perte d'information**, alors que la source la fournit |

---

## 5. Résultat mesuré

Chaîne complète, base vierge, PostgreSQL 16 :

| Script | Erreurs |
|---|---|
| `01_create_fil_rouge_immobilier.sql` | **0** |
| `02_migration.sql` | **0** |
| `03_populate_estate.sql` | **0** |

Contenu obtenu :

| Table | Lignes |
|---|---|
| `role` | 3 |
| `user` | 24 |
| `hunter` | 6 |
| `client` | 18 |
| `search_request` | 17 |
| `criteria` | 17 |
| `mandate` | 17 |
| `estate` | **2 556** |
| `picture` | **1 976** |

Montants après migration :

- `estate.price` : **62 495,00 → 406 042,00 €** (identique au CSV, au centime)
- `criteria.budget_max` : **240 000,00 → 700 000,00 €**

---

## 6. Activer ce dossier

Une seule ligne à changer dans `docker/docker-compose.yml` :

```yaml
volumes:
  - ./init-v2:/docker-entrypoint-initdb.d   # au lieu de ./init
```

Puis, **le volume devant être vide** pour que les scripts d'init rejouent :

```bash
docker compose down -v && docker compose up -d
```

### Tester sans rien toucher

```bash
docker run --rm -d --name pg_essai -e POSTGRES_PASSWORD=test -e POSTGRES_DB=fr postgres:16
```

puis passer les trois scripts dans l'ordre avec `psql`, et supprimer le
conteneur avec `docker rm -f pg_essai`.

---

## 7. Ce qui reste ouvert

| # | Sujet | Où |
|---|---|---|
| 1 | Valider la correction de `ck_client_address_all_or_nothing` | §4 |
| 2 | Trancher le sens de `commission_rate` (honoraires ou commission ?) | §3.3 |
| 3 | Confirmer `hire_date` = date de création du compte | §3.4 |
| 4 | Confirmer `status = 'confirmed'` pour les demandes migrées | §3.5 |
| 5 | Alimenter `energy_class` depuis la colonne `dpe` du CSV | §2.2 |
| 6 | Décisions `D2`, `D6`, `D7`, `D9`, `N2`, `R21`, `U02`, `U05` | en-tête du `01` |

Les points 1 à 4 sont des **hypothèses de migration** : elles font tourner la
chaîne aujourd'hui, mais elles engagent une lecture du métier qui n'a pas été
validée. Aucune n'est cachée — toutes sont signalées dans les scripts.
