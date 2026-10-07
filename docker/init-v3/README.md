# `init-v3/` — part de `init-v2/` le 2026-10-07 (chantier LOT) ; les changements suivent par thème

Ce dossier contient la chaîne complète de création et de peuplement de la base,
alignée sur le **MPD 03 4** (18 tables, 2026-09-22) et sur la convention **euros** ;
une 19e table, `remuneration_parameters`, depuis LOT6 (2026-10-07).

Il ne remplace rien : `docker/init/` reste en place, intact. Les deux dossiers
coexistent tant que le groupe n'a pas validé le basculement.

| Fichier | Rôle | État |
|---|---|---|
| `01_create_fil_rouge_immobilier.sql` | schéma — 19 tables, 258 colonnes (mesuré après LOT9) | testé, 0 erreur |
| `02_migration.sql` | données `Fil_Rouge_Depart` → cible | testé, 0 erreur |
| `03_populate_estate.sql` | 2 556 biens + 1 976 photos | testé, 0 erreur |

Vérifié de bout en bout sur PostgreSQL 16, dans cet ordre, sur une base vierge.

---

## 0. Changements v3, par thème

Chaque changement est écrit ici **et** dans sa migration
`docker/migrations/v2-vers-v3/NN_<thème>.sql` ; le banc (§10) vérifie que les
deux chemins mènent au même schéma. Décisions : registre
`md/questions/questions-a-trancher.md`.

### Mandat et offre — LOT3, `03_mandat-statuts.sql`

- `mandate.status` accepte **`'lost'`** : vente perdue, personne n'est payé sur ce mandat — hors agence ou par un collègue ; un seul statut pour les deux cas, tranché le 2026-10-07 (Q-REM-02, Q-REM-14, Q-JEF-03).
- `mandate.is_client_signed` **retiré** : la date de signature et `'pending_signature'` suffisent ; retiré aussi des 17 mandats de `02` (Q-MAN-05, Q-MAN-09).
- `chk_status_signature` permet **`'canceled'` sans date de signature** ; les autres statuts restent stricts (Q-MAN-07).
- `estate_proposed.proposition_status` accepte **`'signed'`** (Q-SCH-04).

### Mandat : durée et exclusivité — LOT4, `04_mandat-duree-exclusivite.sql`

- `chk_mandate_six_months` remplace le CHECK de `ends_at` : un mandat dure **exactement 6 mois** (Q-MAN-01).
- Le trigger `trg_mandate_exclusivity` est **activé**, corrigé : parent et enfant d'un renouvellement exclus l'un pour l'autre ; un mandat `'canceled'` libère le client **tout de suite** (Q-MAN-02, Q-JEF-06).
- Compté avant d'activer, sur les 17 mandats repris : **0** violent les 6 mois, **0** paire viole l'exclusivité.

### Paiement — LOT5, `05_paiement.sql`

- Les statuts **`'invoice_submitted'` et `'verified'` sont retirés** : la facture est hors périmètre (Q-JEF-23). Le paiement va de `'announced'` à `'scheduled'`, puis `'paid'` — choisi le 2026-10-07 (Q-REM-17).
- Deux dates : **`announced_at`** (chasseur prévenu) et **`scheduled_for`** (jour prévu du virement). `chk_announced` et `chk_scheduled` les exigent dès que l'étape est atteinte, comme `chk_paid` (Q-REM-17).
- **`final_rate` entre 20 % et 60 %** (R21, Q-REM-19, confirmé par Jeff : Q-JEF-01). ⚠️ Ce sont des paramètres proposés : si Jeff les change, le CHECK change (Q-REM-05).
- `chk_refused` exige **`final_rate` hors refus** (Q-REM-10), et refuse un score sur un refus.
- **`performance_score`** fige le score qui a servi au calcul, de 0 à 100 (Q-REM-03) ; **`calculation_details`** (`JSONB`) garde les 5 notes et les entrées (Q-REM-04).
- Compté avant d'activer : **0** paiement en base de dev, et `02` n'en insère aucun.

### Paramètres de rémunération et journal des notes — LOT6, `06_parametres.sql`

- **`remuneration_parameters`**, 19e table : les réglages du calcul (poids, paliers en `JSONB`, notes, points, ancienneté, modulation, bornes) en table versionnée, sans `CHECK` sur les valeurs (Q-REM-05). Une version vaut jusqu'à la suivante, `UNIQUE (effective_from)` — choisi le 2026-10-07 à la place de `valid_from` / `valid_until`. Exposée en CRUD (`/remuneration-parameters`). La grille de notes de Q-JEF-05 n'y est pas : chantier API.
- `payment.seniority_rate` et `performance_rate` **relâchés** au domaine d'un taux : de **0 à 1** et de **−1 à 1** (v2 : 0 à 0,10 et −0,20 à 0,20). Bornes choisies le 2026-10-07, justifiées par `REGLES-CALCUL-REMUNERATION.md` l. 59, 199 et 203 (Q-REM-05).
- `parameters_fees` : **`effective_from`** remplace `valid_from` ; `valid_until` et l'`EXCLUDE` sortent ; **`UNIQUE (effective_from)`** — une grille vaut jusqu'à la suivante (Q-SCH-17).
- `commission_scale.rate` **`> 0`** : une tranche à 0 % est refusée (Q-SCH-15).
- `sale.id_parameters_fees`, **clé** vers la grille qui a donné les honoraires (Q-REM-13). Que ce soit la grille en vigueur à la date de l'acte n'est pas vérifié : TODO, API.
- `hunter_performance` devient un **journal** : `scored_at` à la seconde, `UNIQUE (id_payment)`, `UNIQUE (id_mandate)`, index `(id_hunter, scored_at DESC)` ; `valid_from`, `valid_until`, `chk_perf_period` et `excl_perf_no_overlap` sortent. Deux notes le même jour passent ; ferme D9 (Q-SCH-06).
- Compté avant d'activer : **0** vente, **0** grille, **0** note en base de dev ; `02` n'en insère aucune. La migration s'arrête si une date de fin serait perdue, ou si une vente précède la première grille.

### Personnes — LOT7, `07_personnes.sql`

- `ck_client_address_all_or_nothing` reste **tout-ou-rien** : l'`ALTER` qui l'assouplissait sort de `02` (Q-SCH-01). Les **18 clients** repris reçoivent `address = 'non renseigné'` et `postal_code = '00000'` ; leur ville est gardée (Q-SCH-18). Valeurs **factices**, à remplacer quand Jeff fournit les vraies (Q-JEF-26).
- **Téléphone** au format d'ADR-007 sur `client`, `hunter`, `real_estate_manager` : `ck_<table>_phone_number_format`, un `+`, puis 2 à 15 chiffres, le premier de 1 à 9, au plus un espace ou un tiret entre deux chiffres (« regex E.164 souple » d'ADR-007). `0612345678` est refusé (Q-PRO-08).
- Les **4 téléphones `0000000000`** (3 clients et le manager placeholder, §3.6) deviennent **`+33000000000`** : valeur **factice**, au format (Q-MIG-07).
- `estate_proposed.client_priority`, **`SMALLINT` de 1 à 5**, vide tant que le client n'a pas donné son avis : ferme D6 (Q-SCH-05, Jeff : Q-JEF-18).
- **`created_at`** sur `client`, `hunter`, `real_estate_manager`, `role` ; les lignes reprises prennent la date de la migration, faute de date source (Q-SCH-09).
- `hunter.is_cartet` devient **`is_carte_t`** : colonne, modèle, `02`, migration (Q-SCH-10).
- Compté avant d'activer : **4** téléphones `0000000000`, **0** autre numéro hors format, **18** clients sur 18 avec la ville seule, **0** offre en base de dev. La migration s'arrête si un téléphone ou une adresse ne se complète pas sans inventer une donnée.

### Localisation — LOT8, `08_localisation.sql`

- **`estate.country_iso = 'FR'`** sur les 2 556 biens (dans `03`), **puis** `chk_estate_postal_code_format` : le même contrôle par pays que `client` et `criteria`. Un code postal sans pays est refusé (Q-SCH-11).
- **Eircode sans espace** (`D02X285`) sur `client`, `criteria` et `estate` ; GB et NL gardent leur espace (Q-SCH-12, confirmé par Jeff le 2026-10-07). La migration retire l'espace d'un Eircode existant.
- Les **10 secteurs** d'origine ne sont plus ignorés : chacun des **17 critères** repris reçoit la ville, le code postal et le pays `'FR'` du secteur de son mandat (Q-MIG-08). N2 est fermée : la localisation reste sur `criteria` (Q-SCH-02).
- **`district`** (quartier), `VARCHAR(100)` facultatif, sur `criteria` et `estate` : vide pour 3 critères (Castelnau-le-Lez, Lattes, sans quartier à la source) et pour les 2 556 biens, le CSV n'en ayant pas (Q-MIG-08).
- **`criteria.budget_min` à NULL**, « inconnu », sur les 17 critères : la source n'avait qu'un budget, recopié dans le minimum (Q-MIG-09).
- Compté avant d'activer : **2 556** codes postaux de biens sur 2 556 à 5 chiffres, **0** pays renseigné, **0** client ni critère en Irlande. La migration s'arrête si un bien non repris du CSV a un code postal sans pays.

### Biens — LOT9, `09_biens.sql`

- **`estate.energy_class`** reçoit la lettre de la colonne `dpe` du CSV (dans `03`) : **1 623** biens ; **933** restent vides (NULL), le CSV n'en donne pas (Q-MIG-06). Le CSV n'étant pas monté dans le conteneur, `09` recopie les 1 623 lettres, classe par classe.
- Les quatre autres colonnes d'énergie restent **vides** ; l'ancien score unique n'existe ni en v2 ni en v3 (Q-MIG-05, §2.2).
- **`estate.id_author`**, `INTEGER` facultatif, clé vers `"user"(id)` `ON DELETE RESTRICT` : qui a saisi le bien à la main (chasseur ou manager) ; vide = bien importé. Même forme que `criteria.id_author` ; le rôle se vérifie dans l'API (Q-ACC-09, Q-JEF-24 ; nom et clé tranchés à LOT9).
- Compté avant d'activer : **2 556** biens, mêmes références dans le CSV et dans `03` ; A **491**, B **470**, C **121**, D **140**, E **126**, F **138**, G **137**.

### Anciens mandats — LOT10, `10_reprise-mandats.sql`

Tout est confirmé par Jeff (Q-JEF-13).

- Les **6 mandats « actif » échus** au 25/07/2026, date de l'audit (`MAND-0004`, `0007`, `0009`, `0010`, `0011`, `0012`), passent en **`'expired'`** (Q-MIG-10). Date **fixe** : le résultat ne dépend pas du jour du lancement. `MAND-0013`, `0014`, `0015`, finis depuis, restent `'active'` : les faire expirer revient à l'application.
- Le **mandat 13**, écarté jusqu'ici (son client était un chasseur), se rattache à **Nina Girard** (user 19, déjà cliente), avec sa demande et son critère tirés de la ligne source (T2 Figuerolles, 220 000 €, 40 m² min). Pas de compte en plus (Q-MIG-12). Soit **18** demandes, **18** critères, **18** mandats.
- Statuts source traduits : `actif` → `'active'`, `termine` → `'completed'`, `expire` → `'expired'`, **`suspendu` → `'canceled'`** : pas de pause dans la cible (Q-MIG-13).
- Les **18 demandes** passent en **`'launched'`** : toutes ont un mandat signé ; pas de nouvel état pour une recherche finie (Q-MIG-03, tranché à LOT10 ; §3.5).
- Compté avant d'activer : **17** demandes en `'confirmed'`, **17** mandats dont les 6 en `'active'`, **0** demande pour Nina Girard. La migration s'arrête si Nina n'est pas cliente, ou si l'id 13 est pris par un autre client.

### Clôture — LOT11, sans migration

- Les **3 TODO** de `01` qui croisent plusieurs tables (une visite avant la signature, une vente hors de la validité du mandat, un paiement au mauvais chasseur ou sur un barème périmé) sont annotés **« contrôlé par l'API »** (Q-MAN-06). Aucune table ne change ; les règles et leurs tests restent à écrire dans l'API.
- **Mot de passe** gardé, haché en Argon2 (Q-JEF-14) : rien à retirer du schéma.
- ✅ Le **rôle en lecture seule** (Q14) est venu ensuite : LOT12, ci-dessous.

### Rôle en lecture seule — LOT12, `04_role-lecture-seule.sql` et `12_role-lecture-seule.sql`

Jeff a dit oui sur Discord le 2026-10-07, **à condition** que le choix soit expliqué au jury, utile et cohérent (Q14). Voici l'explication.

**Ce que c'est** — deux rôles, à deux niveaux :

| Niveau | Nom | Ce qu'il peut faire |
|---|---|---|
| PostgreSQL | `fil_rouge_reader` | lire les 19 tables (`SELECT`), et rien d'autre : ni `INSERT`, ni `UPDATE`, ni `DELETE` |
| Application | `'Reader'` dans `role` (id 5) | consulter dans l'API sans modifier ; aucun utilisateur ne l'a encore |

**À quoi ça sert**
- Un projet Data-IA **lit** la base : requêtes d'analyse, notebook, outil de rapport. Sans ce rôle, il faut leur donner le compte `postgres`, qui peut tout effacer par erreur.
- C'est le **moindre privilège** : chacun reçoit les droits de son travail, pas plus.
- Côté application : quelqu'un qui consulte sans modifier, un auditeur ou le client qui suit l'avancement.

**Pourquoi les deux, et pas un seul**
- L'API se connecte avec le compte `postgres` : le rôle PostgreSQL **ne limite pas** ce qu'un utilisateur de l'API peut faire. Il protège les accès **directs** à la base.
- Le rôle `'Reader'` couvre l'autre porte : celle de l'API. ⚠️ L'API ne vérifie pas encore les rôles : ce contrôle viendra avec les outils d'authentification côté back. Aujourd'hui, la valeur existe, la règle reste à écrire.

**Sans risque pour le dépôt**
- Mot de passe : `POSTGRES_READER_PASSWORD`, dans `docker/.env`, **jamais dans git**. `docker-compose.yml` le passe au conteneur (une ligne, accord du 2026-10-07).
- Variable vide ou absente : le rôle existe **sans pouvoir se connecter** (`NOLOGIN`).
- Un rôle vit dans le serveur, partagé par toutes ses bases : sa création est **idempotente**. Ses droits, eux, se donnent base par base, y compris pour les tables futures (`ALTER DEFAULT PRIVILEGES`).

**Mesuré le 2026-10-07**
- Connecté avec ce rôle : `SELECT` accepté (5 rôles lus), `INSERT` refusé (`permission denied for table role`).
- Base de dev : **19** tables lisibles sur **19**, **0** modifiable.
- Tests `test_reader_role_can_select` et `test_reader_role_cannot_write` (insert, update, delete). Avec `GRANT INSERT` ajouté au script, `[insert]` échoue : le test voit bien le défaut.

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

> ✅ Fait à LOT9 : `energy_class` reçoit la lettre de la colonne `dpe` du CSV
> (1 623 biens, Q-MIG-06 ; voir §0).

---

## 3. `02_migration.sql` — six changements

### 3.1 `role` : `libelle` → `wording`, valeurs capitalisées

Le schéma cible nomme la colonne `wording` et son `CHECK` n'accepte que
`'Admin'`, `'Client'`, `'Hunter'`, `'Manager'`.

| source | cible |
|---|---|
| `client` | `Client` |
| `hunter` | `Hunter` |
| `real_estate_manager` | `Manager` |
| — | `Admin` (ajouté le 2026-09-22) |

⚠️ **`Admin` n'a aucune source** : le rôle était autorisé par le `CHECK` depuis
l'origine, mais sa ligne n'avait jamais été insérée. Corrigé le 2026-09-22 —
la table compte désormais **4 lignes**. Aucune table de profil ne lui est
rattachée, à la différence de `client` / `hunter` / `real_estate_manager` : un
admin porte des droits, pas un métier. Pour une base déjà créée :
`migrations/2026-09-22_role_admin.sql`.

3 lignes. Le renommage `real_estate_manager` → `Manager` suit le `CHECK` du
MPD ; la table `real_estate_manager`, elle, garde son nom.

### 3.2 `criteria` : budgets convertis en euros

17 lignes. `320.0` devient `320000.00`. Ici la multiplication par 1000 est
**légitime** : contrairement aux annonces, la source ne fournit pas de colonne
en euros, et les budgets sont des montants ronds (`240.0` à `700.0`), saisis
au millier. Aucune précision n'est perdue.

Depuis LOT8, seul `budget_max` reçoit ce montant : `budget_min`, qui le
recopiait, est **NULL** (Q-MIG-09, voir §0).

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

### 3.5 `search_request.status` : `'launched'` sous mandat (LOT10)

La colonne est `NOT NULL` et **absente de la source**. Parmi
`confirmed` / `accepted` / `rejected` / `launched`, une demande qui porte déjà
un mandat est « lancée » : tranché à LOT10 (Q-MIG-03). Les 18 demandes en
ont un ; l'`UPDATE` qui était commenté est actif, en section 9 de `02` :

```sql
UPDATE search_request sr SET status = 'launched'
 WHERE status = 'confirmed'
   AND EXISTS (SELECT 1 FROM mandate m WHERE m.id_search_request = sr.id);
```

### 3.6 `hunter.id_realestatemanager` : un manager placeholder

Depuis le **MPD 03 4** (2026-09-22), un chasseur a toujours un manager :
`hunter.id_realestatemanager` est `NOT NULL`. Voir §9.

La source n'a **aucun manager** : deux rôles seulement, `client` et
`chasseur`. Les 6 chasseurs ne pouvaient donc plus être migrés tels quels.

Valeur retenue : un **compte placeholder** unique,
`manager.migration@chassimmo.fr` (user 25, rôle `Manager`), au nom
volontairement bidon (« Manager Migration », téléphone `+33000000000` depuis
LOT7, `0000000000` avant), bloqué
par le même mot de passe placeholder que les 24 autres comptes. Les 6
chasseurs lui sont rattachés.

⚠️ C'est une **hypothèse de migration** : ce manager n'est pas une personne.
Le seed devra le remplacer par de vrais managers, puis le supprimer une fois
qu'aucun chasseur ne pointe plus vers lui.

---

## 4. ⚠️ Une contrainte du schéma a dû être corrigée

✏️ **Tranché le 2026-10-05, appliqué le 2026-10-07 (LOT7)** : le groupe garde
le tout-ou-rien (Q-SCH-01). L'`ALTER` ci-dessous est **retiré** de `02` ; les
18 clients reçoivent « non renseigné » et `00000` (Q-SCH-18, §0). La suite
décrit l'état d'avant, gardée pour l'historique.

C'était le point qui demandait une **décision du groupe**.

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
| `role` | 4 |
| `user` | 25 (24 migrés + 1 manager placeholder, §3.6) |
| `hunter` | 6 |
| `client` | 18 |
| `real_estate_manager` | 1 (placeholder, §3.6) |
| `search_request` | 17 |
| `criteria` | 17 |
| `mandate` | 17 |
| `estate` | **2 556** |
| `picture` | **1 976** |

Montants après migration :

- `estate.price` : **62 495 → 406 042 €** (identique au CSV ; euros entiers,
  `INTEGER` depuis Q-REM-01 du 2026-10-05 — 0 prix sur 2 556 avait des centimes)
- `criteria.budget_max` : **240 000 → 700 000 €** (`INTEGER`, revérifié le
  2026-10-05 sur `fil_rouge_test` : 17 lignes)

---

## 6. Activer ce dossier

Rien à changer : `docker/docker-compose.yml` monte déjà `./init-v3` sur
`/docker-entrypoint-initdb.d` depuis le 2026-10-07 (LOT1).

Les scripts d'init ne rejouent que sur un **volume vide**. Depuis `docker/`,
après avoir ajouté `POSTGRES_READER_PASSWORD=` à `docker/.env` (LOT12, voir
`.env.exemple`) :

```bash
docker compose down -v && docker compose up -d
```

⚠️ `down -v` efface la base de dev locale. `healthy` arrive **avant** la fin
de l'init : attendre « init process complete » dans `docker compose logs db`
avant de lire la base. Puis `bash docker/create_test_db.sh` pour la base de
test.

### Tester sans rien toucher

```bash
docker run --rm -d --name pg_essai -e POSTGRES_PASSWORD=test -e POSTGRES_DB=fr postgres:16
```

puis passer les quatre scripts (`01` à `04`) dans l'ordre avec `psql`, et
supprimer le conteneur avec `docker rm -f pg_essai`.

---

## 7. Ce qui reste ouvert

| # | Sujet | Où |
|---|---|---|
| 1 | ✅ Fermé (LOT7) : tout-ou-rien gardé, valeurs factices pour les 18 clients | §0, §4 |
| 2 | Trancher le sens de `commission_rate` (honoraires ou commission ?) | §3.3 |
| 3 | Confirmer `hire_date` = date de création du compte | §3.4 |
| 4 | ✅ Fermé (LOT10) : demandes sous mandat en `'launched'` | §0, §3.5 |
| 5 | ✅ Fermé (LOT9) : `energy_class` rempli depuis `dpe`, 1 623 biens | §0, §2.2 |
| 6 | Décision `D2` (`D7`, `U02`, `U05` : LOT4 ; `R21` : LOT5 ; `D9` : LOT6 ; `D6` : LOT7 ; `N2` : LOT8) | en-tête du `01`, §0 |
| 7 | Acter en ADR le lien chasseur → manager, et remplacer le manager placeholder par le seed | §3.6, §9 |

Les points 2, 3 et 7 restent des **hypothèses de migration** (1 et 4 sont
fermés) : elles font
tourner la chaîne aujourd'hui, mais elles engagent une lecture du métier qui
n'a pas été validée. Aucune n'est cachée — toutes sont signalées dans les
scripts.

---

## 8. `payment` — la traçabilité du refus (ADR-024)

> ⚠️ **ADR-024 est au statut « proposé »**, pas encore validé par le groupe.
> Le schéma l'applique déjà : si la décision change, c'est ici qu'il faudra
> revenir. Justification complète : `md/adr/adr-024-motif-refus-remuneration.md`.

### 8.1 Pourquoi

Le sujet ferme le droit à rémunération dans deux cas, et impose d'en garder
la raison : « Le refus retourne un **motif**, jamais un simple `False` »
(`REGLES-CALCUL-REMUNERATION.md` l. 497). Il désigne même l'emplacement :
« stocker le motif du droit refusé dans `paiements` » (l. 100).

La table ne pouvait rien enregistrer de tel : pas de colonne de motif, aucun
statut de refus, `base_rate NOT NULL CHECK (base_rate > 0)` et
`id_commission_scale NOT NULL`.

### 8.2 Ce qui a changé

| # | Changement |
|---|---|
| 1 | État `refused` ajouté à `status` |
| 2 | Colonne `refusal_reason`, limitée à `mandate_expired` et `out_of_scope` |
| 3 | `NOT NULL` retiré sur `base_rate`, `seniority_rate`, `performance_rate` |
| 4 | `NOT NULL` retiré sur `id_commission_scale` |
| 5 | Contrainte `chk_refused` ajoutée |

Les **bornes des `CHECK` n'ont pas bougé** : en PostgreSQL, un `CHECK` ne
s'applique pas à une valeur `NULL`. Retirer le `NOT NULL` suffit, la règle
métier reste intacte.

Les deux motifs viennent de l'énumération `MotifRefus` du sujet (l. 385),
transposés en anglais conformément à `ADR-002` :

| Sujet | En base |
|---|---|
| `MANDAT_EXPIRE` — mandat échu à la date de l'acte | `mandate_expired` |
| `HORS_DISPOSITIF` — mandat non-exclusif, vente hors dispositif | `out_of_scope` |

### 8.3 Résultat mesuré

PostgreSQL 16, schéma chargé à neuf **et** base existante migrée par
`docker/migrations/2026-09-21_adr-024_payment_refusal.sql`. Les deux voies
donnent le **même** comportement :

| # | Cas | Attendu | Obtenu |
|---|---|---|---|
| 1 | refus `mandate_expired`, montant 0, reste vide | accepté | ✅ |
| 2 | refus `out_of_scope`, idem | accepté | ✅ |
| 3 | refus **sans** motif | rejeté | ✅ `chk_refused` |
| 4 | refus **avec** un taux | rejeté | ✅ `chk_refused` |
| 5 | refus **avec** un montant | rejeté | ✅ `chk_refused` |
| 6 | refus, motif inconnu | rejeté | ✅ `payment_refusal_reason_check` |
| 7 | paiement **sans** barème | rejeté | ✅ `chk_refused` |
| 8 | paiement **avec** un motif | rejeté | ✅ `chk_refused` |
| 9 | paiement complet | accepté | ✅ |
| 10 | deux lignes sur la même vente | rejeté | ✅ `payment_id_sale_key` |

**10 cas sur 10.** Le script de migration a été passé **deux fois** de suite
sans erreur : il est rejouable.

Côté API, `Payment-Input` et `Payment-Output` exposent `refusal_reason`, et
les quatre champs concernés sont devenus facultatifs.

### 8.4 Ce que ça ne fait pas

`chk_refused` **enregistre** un refus, elle ne le **calcule** pas. Le TODO
`U01/U04` de l'en-tête du `01` reste ouvert : rien ne vérifie encore qu'un
paiement va bien au chasseur du mandat, ni que le barème était en vigueur à
la date de l'acte.

---

## 9. `hunter` — chaque chasseur a un manager (MPD 03 4, 2026-09-22)

> ⚠️ **Choix du groupe, pas encore acté en ADR.** Le schéma l'applique déjà :
> si la décision change, c'est ici qu'il faudra revenir.

### 9.1 Pourquoi

Le MPD 03 4 relie **Hunter (1,1) — RealEstateManager (0,n)**, lien
« Manages » : un chasseur a toujours un manager, un manager peut n'en avoir
aucun.

Le sujet parle du manager d'un chasseur à trois endroits :
`CAHIER-DES-CHARGES-TECHNIQUE.md` l. 97 (exemple ENF-03) et
`REGLES-CALCUL-REMUNERATION.md` l. 296 et 763 — « accès limité au chasseur
concerné et à son manager ».

⚠️ ENF-03 est un **exemple rempli dans un modèle**, pas une exigence du
client (déjà relevé dans `md/securite/securite-mots-de-passe-et-droits.md`). Les
`.feature` ne citent jamais de manager ; les fixtures n'ont que `client` et
`chasseur`. Le lien est donc un choix de modélisation, cohérent avec le rôle
`Manager` déjà en base.

### 9.2 Ce qui a changé

| # | Changement |
|---|---|
| 1 | Colonne `hunter.id_realestatemanager INTEGER NOT NULL`, FK vers `real_estate_manager(id_user)`, `ON DELETE RESTRICT` |
| 2 | `real_estate_manager` est créée **avant** `hunter` (dépendance de FK) |
| 3 | `02_migration.sql` : un manager placeholder (user 25) pour les 6 chasseurs migrés (§3.6) |
| 4 | Base déjà créée : `docker/migrations/2026-09-22_hunter_manager.sql` |
| 5 | API : `Hunter.id_realestatemanager: int` dans `hunter_model.py` |

Même convention que toutes les FK du schéma : la colonne pointe vers
`id_user`, donc contient un id de `"user"`.

Deux liens portent le même nom « Manages » sur le MPD :
`search_request.id_realestatemanager` (le manager qui **traite la demande**)
et `hunter.id_realestatemanager` (le manager **du chasseur**). Rien n'impose
qu'ils coïncident sur une même demande. À assumer, ou renommer le second
(« Supervises ») pour lever le doute.

### 9.3 Résultat mesuré

PostgreSQL 16, schéma chargé à neuf (01 → 02 → 03, **0 erreur**) **et** base
existante (scripts précédents) migrée par
`docker/migrations/2026-09-22_hunter_manager.sql`. Les deux voies donnent le
**même** comportement, la même contrainte (`hunter_id_realestatemanager_fkey`)
et le même commentaire de colonne :

| # | Cas | Attendu | Obtenu |
|---|---|---|---|
| 1 | chasseur **sans** manager | rejeté | ✅ `not-null constraint` |
| 2 | chasseur avec manager **inconnu** | rejeté | ✅ `hunter_id_realestatemanager_fkey` |
| 3 | chasseur avec manager valide | accepté | ✅ |
| 4 | supprimer un manager encore référencé | rejeté | ✅ `ON DELETE RESTRICT` |
| 5 | passer `id_realestatemanager` à `NULL` | rejeté | ✅ `not-null constraint` |
| 6 | un manager sans aucun chasseur (0,n) | accepté | ✅ |
| 7 | changer un chasseur de manager | accepté | ✅ |

**7 cas sur 7.** Après migration : 25 users, 1 manager, **0 chasseur sans
manager**. Le script de migration a été passé **deux fois** de suite sans
erreur : il est rejouable.

Colonnes mesurées via `information_schema` : 225 avant, **226** après
(18 tables). L'ancien compte « 224 » de l'en-tête du `01` n'avait pas été
mis à jour à l'ADR-024.

Côté API (image existante, lancée sur la base migrée) :

| Appel | Obtenu |
|---|---|
| `GET /hunters` | `200`, chaque chasseur expose `id_realestatemanager: 25` |
| `POST /hunters` sans manager | `409` (contrainte violée) |
| `POST /hunters` avec un manager inconnu | `409` |
| `POST /hunters` avec le manager 25 | `201` |

Le `409` plutôt qu'un `422` n'est pas propre à cette colonne : un modèle
SQLModel `table=True` ne valide pas les champs obligatoires à l'entrée, donc
**toute** colonne `NOT NULL` absente arrive jusqu'à la base (vérifié avec
`hire_date` : `409` aussi). Comportement préexistant de l'API.

### 9.4 Ce que ça ne fait pas

- Pas d'**historique** : un changement de manager écrase l'ancien. Suffisant
  pour les droits d'accès (ENF-03) ; à revoir si la performance doit être
  rattachée au manager de l'époque.
- Le manager placeholder n'est **pas une personne** : le seed devra le
  remplacer, puis le supprimer une fois qu'aucun chasseur ne pointe vers lui.

## 10. Vérifier v3 — le banc « base neuve = base migrée »

Chaque changement de v3 s'écrit **deux fois** : ici, pour une base neuve, et
dans `docker/migrations/v2-vers-v3/NN_<thème>.sql`, pour une base v2 qui
existe déjà. Le banc vérifie que les deux chemins mènent au même endroit.

```bash
bash docker/compare_v2_v3.sh
```

- **Ce qu'il fait** : il crée `cmp_v2_migree` (`init-v2/*.sql`, puis chaque
  migration `v2-vers-v3/*.sql` par ordre de nom) et `cmp_v3_neuve`
  (`init-v3/*.sql`), décrit les deux bases, compare, puis les supprime.
- **Ce qu'il compare** : colonnes (nom, type, nullable, défaut), contraintes
  (nom et définition), index, triggers, fonctions, et le nombre de lignes par
  table. L'**ordre des colonnes est ignoré** : `ADD COLUMN` la met en dernier.
- **Ce qu'il rend** : `IDENTIQUES` et code `0` ; sinon le diff et code `1` ;
  code `2` si un fichier ne se charge pas (il est nommé).
- **Mesuré le 2026-10-07** (LOT2, aucune migration encore) : `IDENTIQUES —
  499 faits comparés`, de 17,8 à 27,4 s selon le passage. Un mutant (`ALTER TABLE role ADD COLUMN
  mutant int` côté v3) rend `1` et nomme `public.role.mutant` ; la même
  colonne écrite au milieu du `CREATE TABLE role` rend `IDENTIQUES`.
- **Mutants** : les dossiers passent en variables (`V2_DIR`, `V3_DIR`,
  `MIG_DIR`) — on mute une copie temporaire, jamais ces dossiers.
- **Ce qu'il ne compare pas** : les droits (`GRANT`), les rôles (communs au
  serveur), les vues, les types et les séquences.
