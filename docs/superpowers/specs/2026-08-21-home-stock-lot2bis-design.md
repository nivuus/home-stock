# home_stock — Lot 2bis : objectifs nutritionnels, portion manuelle et tri des déchets

> Spec du lot 2bis. Ramasse les **trois points différés** que les lots 1 et 2
> ont laissés sans lot d'accueil : les objectifs nutritionnels
> (`2026-08-20-home-stock-lot2-design.md` § 18), la portion manuelle par
> produit (même § 18) et le matériau d'emballage / tri des déchets
> (`2026-08-19-home-stock-lot1-design.md` § 17).
>
> **Ce lot est délibérément petit.** Aucun des trois sujets ne justifie un
> mécanisme : deux d'entre eux se branchent sur des données déjà calculées, le
> troisième tient dans un module pur de soixante lignes. Un document qui les
> gonflerait produirait du code que personne n'ouvrirait.

## 1. Objectif et livrable

Fixer une limite journalière sur ce qu'on mange, la voir tenir ou céder, et
faire dire à Bleuenn quand elle cède. Corriger à la main la portion d'un produit
que la médiane apprise devine mal. Savoir dans quel bac va un emballage, au
moment précis où on le jette.

Livrable vérifiable : poser un objectif de 6 g de sel par jour, manger 8 g,
voir `binary_sensor.home_stock_nutrition_goals` passer à `on` avec le détail en
attribut, et l'automation créée depuis le blueprint livré l'annoncer le soir —
une fois, pas dix. Fixer la portion d'un produit à 45 g depuis le catalogue et
retrouver « Ma portion (45 g) » sur l'écran « manger » à la place de la médiane
apprise. Déclarer un pot de yaourt fini et lire « Bac jaune » sous le bouton.

## 2. Périmètre

**Dans le lot :** neuf objectifs journaliers maximaux, stockés dans les options
de l'entrée ; un `binary_sensor` de dépassement, jour et moyenne glissante sur
sept jours ; un blueprint d'annonce livré et jamais installé ; une colonne
`product.manual_portion` et sa place en tête de l'ordre de priorité des
portions ; l'extraction du matériau d'emballage depuis Open Food Facts et la
consigne de tri française sur l'écran « manger ».

**Hors du lot :** les objectifs **minimaux** (« au moins 80 g de protéines »),
tranchés au § 7.5 ; l'édition des objectifs depuis le panneau ; un objectif de
dépense en euros — l'argent est au lot 4 ; le poids corporel, l'activité
physique et tout ce qui ferait de `home_stock` un journal de santé ; le suivi
du volume réel de déchets par bac.

## 3. Décisions validées

| Question | Réponse retenue |
|---|---|
| Où vivent les objectifs | **Options de l'entrée de configuration**, ni table, ni entités `number` (§ 7.1) |
| Sens d'un objectif | **Un plafond**, jamais un plancher (§ 7.5) |
| Quels nutriments | **Les neuf**, y compris ceux dont le capteur est éteint (§ 7.2) |
| Lecture d'un dépassement | **Un seul `binary_sensor`**, liste en attribut (§ 7.4) |
| Fenêtres | **Jour ET moyenne des sept journées closes**, même seuil (§ 7.3) |
| Annonce à Bleuenn | **Blueprint livré, jamais installé**, comme les DLC du lot 2 (§ 7.4) |
| Portion manuelle | Colonne sur **`product`**, prioritaire sur l'apprise et sur Open Food Facts (§ 8) |
| Emballage | **Lecture à la volée depuis `off_raw`**, aucune colonne, aucun backfill (§ 9) |
| Migration | **Une seule colonne** — `product.manual_portion`. Numéro fixé au merge (§ 6) |

## 4. Amendements aux specs précédents

**A1 — Le § 17 du lot 1 est factuellement faux, et c'est la découverte
structurante de ce lot.** Il annonce « Matériau d'emballage, tri des déchets —
conservé gratuitement dans `off_raw` ». Ce n'est pas le cas : `off/ingest.py`
écrit `off_raw = json.dumps(product)` où `product` est la réponse **déjà filtrée
par le paramètre `fields=`** de la requête (`off/client.FIELDS`), qui ne demande
ni `packagings` ni `packaging_tags`. Vérifié sur les fixtures :
`grep -c packaging tests/fixtures/off/*.json` rend **0** sur les trois fichiers,
et les clés d'un enregistrement capturé sont exactement celles de `FIELDS`. La
donnée n'est donc pas « déjà en base » : elle n'a jamais été demandée.
Conséquence directe sur le § 9 — **rien à rattraper rétroactivement**, et un
`apply()` qui relirait `off_raw` ne trouverait rien, sur aucun article, jamais.

**A2 — Les neuf capteurs quotidiens ne sont pas la source du calcul du jour.**
Le lot 2 les alimente depuis `coordinator.data["today"]`, produit par
`application.summary()` → `repo.totals_between()`. Tout le § 7 en dépend : un
objectif se compare à `today[...]`, jamais à l'état d'une entité. C'est ce qui
rend un objectif sur un capteur éteint parfaitement propre.

## 5. Architecture

| Fichier | Rôle |
|---|---|
| `domain/goals.py` | **Nouveau.** Pur : compare des totaux à des objectifs, rend les dépassements |
| `off/packaging.py` | **Nouveau.** Pur : lit `packagings`/`packaging_tags` dans un `off_raw`, rend des bacs |
| `off/client.py` | `FIELDS` gagne `packagings,packaging_tags` |
| `const.py` | `CONF_GOALS`, `GOAL_NUTRIENTS`, `MAX_GOAL`, `GOAL_WINDOW_DAYS`, `RECYCLING_BINS` |
| `config_flow.py` | Neuf champs facultatifs de plus |
| `application.py` | `summary()` rend `week_mean` en plus de `today` |
| `storage/repositories.py` | `article_off_raw()`, `manual_portion` dans `PRODUCT_FIELDS` |
| `storage/migrations/m00N_portion.py` | **Nouveau.** Une colonne. Numéro fixé au merge (§ 6) |
| `coordinator.py` | Appelle `domain/goals.py` avec les options, publie `goals` |
| `binary_sensor.py` | `NutritionGoalsBinarySensor` |
| `validators.py` | `goal_quantity()`, `check_manual_portion()` |
| `websocket_api.py` | `product/get` étendu ; `manual_portion` dans `PRODUCT_EDITABLE` |
| `blueprints/automation/home_stock/objectifs_bleuenn.yaml` | **Nouveau.** Livré, jamais installé |
| `frontend/src/tri.ts` | **Nouveau.** Libellés français des bacs, purs |
| `frontend/src/ecrans/{catalogue,consommation,journal}.ts` | Un champ, une ligne, une ligne |

`portion.ts` ne change pas de logique : il reçoit une portion et une source, il
ne se demande pas d'où elles viennent. Le front garde ses identifiants **en
français**, le Python les siens **en anglais**.

## 6. Migration : une colonne, et un numéro qui n'est pas garanti

L'état réel de `storage/migrations/` au 2026-08-21 est `m001_initial` (VERSION 1)
à `m005_equipment` (5) : le premier numéro libre est **`m006`**. Mais le **lot 4,
spécifié en parallèle, le revendique explicitement** (`m006_shopping.py`,
`VERSION = 6`, son § 6). Ce lot part donc du principe qu'il prendra **`m007`**,
et le numéro se fixe **au merge**, jamais à la rédaction :

- `apply_migrations()` n'applique que les migrations strictement supérieures à
  `MAX(version)`. Un **trou** est sans conséquence ; un **dépassement** ne l'est
  pas — une base passée en 6 par ce lot ne verrait jamais le `m006` du lot 4,
  sautée définitivement et en silence.
- `tests/storage/test_migrations.py` porte déjà une contiguïté **stricte**
  (`test_migration_versions_are_contiguous_from_one`) et une assertion de
  nommage (`m00N_*.VERSION == N`). Le plan doit donc, au merge : relire
  `migrations/__init__.py`, prendre le **premier numéro libre**, et renommer le
  module **et** sa constante ensemble.
- Ce lot glisse à `m006` **ou** `m007` sans rien casser : sa migration ne dépend
  d'aucune colonne des lots 3, 4 ou 5 et n'expose **aucun hook `apply()`**. Elle
  est la plus indépendante des migrations en attente, donc celle qui cède le
  numéro si l'ordre de merge change.

```sql
-- La portion que le foyer a fixée à la main, dans l'unité de base du produit.
-- Prime sur la médiane apprise et sur la portion d'Open Food Facts (§ 8.2).
-- NULL = « déduis-la », soit 100 % du catalogue le jour de la migration.
ALTER TABLE product ADD COLUMN manual_portion REAL;
```

C'est tout. Pas de table `goal` (§ 7.1), pas de colonne d'emballage (§ 9.4).

## 7. Objectifs nutritionnels

### 7.1 Où ils vivent : les options de l'entrée

| Candidat | Verdict | Pourquoi |
|---|---|---|
| **Options de l'entrée** | **Retenu** | Un objectif est un réglage : neuf nombres, un propriétaire, aucun historique, aucune requête. Déjà persistées, déjà sauvegardées, déjà éditables par un flux existant, déjà lues par le coordinateur — comme `expiration_alert_days` depuis le lot 0 |
| Table `goal` | Rejeté | Une table d'une ligne pour une préférence : migration, dépôt, deux commandes. Un mécanisme complet pour ce qu'un dictionnaire fait gratuitement |
| Neuf entités `number` | Rejeté | Entité d'**état** : valeur dans le `recorder` (purgé à dix jours), restaurée depuis le registre — un réglage qui peut disparaître. Et neuf entités actives, quand le lot 2 en a créé cinq **éteintes** pour ne pas encombrer |

**Conséquence assumée : l'édition se fait dans Paramètres → Appareils et
services → Garde-manger → Configurer, pas dans le panneau**, qui *lit* les
objectifs (§ 11) sans les écrire. Une écriture websocket vers
`async_update_entry(options=…)` demanderait une commande, un validateur en
double et un rechargement d'entrée, pour un geste annuel. Reporté au § 14.

### 7.2 Quels nutriments, et les cinq capteurs éteints

Les **neuf** que le lot 2 gèle dans le journal :

```python
GOAL_NUTRIENTS = ("kcal", *MACRO_COLUMNS)   # kcal + les huit macros
CONF_GOALS = "nutrition_goals"              # dict {nutriment: plafond}
MAX_GOAL = 20_000.0                         # au-delà, c'est une faute de frappe
```

Clé absente ou `None` = **pas d'objectif** ; le défaut livré est « aucun
objectif », et rien ne change tant que personne n'a rien réglé.

**Un objectif sur un capteur éteint fonctionne, et c'est structurel.** Cinq des
neuf capteurs quotidiens sont créés désactivés ; le calcul ne les regarde
jamais, il lit `coordinator.data["today"][nutriment]`, produit par
`repo.totals_between()` que l'entité soit activée ou n'existe pas du tout
(§ 4, A2). Corollaire à respecter : **ni le `binary_sensor` ni le blueprint ne
référencent un capteur par nutriment**. Une condition
`state('sensor.home_stock_fiber_today')` rendrait `unavailable` sur une entité
éteinte, et une automation qui ne se déclenche jamais est le pire des états —
le défaut exact que `CLAUDE.md` reproche à l'interrupteur cuisine.

### 7.3 Jour, et moyenne des sept journées **closes**

| Fenêtre | Ce qu'on compare | Ce que ça dit |
|---|---|---|
| `day` | Le total de la journée alimentaire **courante** | Un écart ponctuel |
| `week` | La **moyenne** des sept journées alimentaires **closes** (J-7 … J-1) | Une dérive |

Les deux fenêtres partagent le **même plafond réglé** : deux nombres par
nutriment doubleraient le formulaire pour une nuance que personne ne saurait
chiffrer.

**La journée courante est exclue de la moyenne, et c'est la décision décisive du
paragraphe.** L'inclure ferait chuter la moyenne toute la matinée puis remonter
au dîner : le capteur clignoterait chaque jour, sur une grandeur censée décrire
une tendance. Une dérive se lit sur des journées finies.

Les bornes viennent de `domain/foodday.py`, jamais d'un calcul local :
`food_day_bounds(now, tz)` pour la journée, `bounds_of_food_day(food_day_of(now,
tz) - timedelta(days=7), tz)` pour l'origine, la moyenne portant sur
`[week_start ; today_start[` et divisée par **sept journées**, pas par
168 heures — une journée est une journée, même quand elle en dure 23 ou 25.
`application.summary()` gagne **une** requête agrégée de plus par
rafraîchissement, sur la même connexion et dans le même travail d'exécuteur, et
publie `data["week_mean"]`.

### 7.4 Comment se lit un dépassement, et qui l'annonce

**Un seul `binary_sensor.home_stock_nutrition_goals`**, « Objectifs
nutritionnels », dans la lignée de `…_expirations` et `…_shortages` du lot 0.
`is_on` : au moins un objectif dépassé, sur l'une ou l'autre fenêtre.

```yaml
exceeded:                 # trié par ratio décroissant
  - {nutrient: salt, scope: day, value: 8.4, goal: 6.0, ratio: 1.4}
count: 1
day_count: 1
week_count: 0
food_day: "2026-08-21"    # la journée alimentaire évaluée, pas la date civile
```

**Ni un attribut sur `kcal_today`** (illisible sur un capteur éteint, § 7.2)
**ni une entité par nutriment** (neuf fois la même phrase dans le registre) : la
liste en attribut est déjà le choix du lot 2 pour les péremptions, parce que
c'est elle qui rend le nombre actionnable et qu'une annonce vocale veut une
phrase, pas neuf. **Aucune entité `event` non plus** : une péremption est un
franchissement daté qu'on n'annonce qu'une fois (d'où
`batch.expiry_announced_stage` en base), un dépassement est un **état** qui dure
jusqu'à 4 h — un `event` obligerait à retenir en base ce qui a été annoncé, donc
une table, donc la migration que le § 6 refuse.

Le calcul vit dans `domain/goals.py`, pur —
`exceeded(today, week_mean, goals) -> list[dict]`. Le coordinateur l'appelle
avec `self.config_entry.options.get(CONF_GOALS, {})` et publie `data["goals"]` ;
les options ne descendent **jamais** dans `application.py`. Un objectif
**atteint exactement** n'est pas dépassé (`>`, jamais `>=`).

L'annonce passe par `blueprints/automation/home_stock/objectifs_bleuenn.yaml`,
livré dans le dépôt et **jamais installé par le composant** — même règle qu'au
lot 2 pour les DLC : le composant part sur HACS et n'a pas à coder l'assistant
vocal d'un foyer en dur. Entrées : l'heure (défaut **21:30**, après le dîner,
dernier moment où la journée est encore corrigeable), l'agent (défaut
`conversation.personas_studio_home_manager`), le capteur. Déclencheur
**horaire**, jamais d'état — un déclencheur sur le passage à `on` annoncerait au
rafraîchissement du coordinateur, donc à n'importe quel quart d'heure, y compris
à table. Action : `conversation.process`, phrase construite depuis `exceeded` en
distinguant les deux fenêtres.

### 7.5 Ce qui ne doit surtout pas arriver

- **Une alerte en boucle.** Le composant ne notifie jamais de lui-même : il
  publie un état. Le seul émetteur est une automation **horaire**, donc au plus
  une annonce par jour et par automation installée.
- **Un déclenchement à 4 h 01 sur une journée vide.** Réglé **par construction,
  pas par une garde** : un objectif est un plafond, la journée vaut alors zéro
  partout, le capteur est `off`. Rien à protéger, donc aucune condition
  « la journée n'est pas vide » à écrire.
- **C'est pourquoi les objectifs minimaux sont hors du lot** (§ 14) : un
  plancher n'a de sens qu'à la **clôture** de la journée, donc heure de clôture
  réglable, mémoire des annonces, et la table que le § 6 refuse.
- **Une frontière à minuit.** Elle est évitée gratuitement : `today` est bornée
  par `food_day_bounds()` et le coordinateur repose déjà un rendez-vous à 4 h
  (`_schedule_food_day_rollover`) — sans lui, un dépassement de la veille
  resterait `on` toute la matinée. Ce lot n'a qu'à ne pas le contourner :
  **aucun calcul de date locale dans `domain/goals.py`, `binary_sensor.py` ou
  le blueprint**. Un test l'épingle (§ 13).

## 8. Portion manuelle par produit

### 8.1 Sur `product`, pas sur `article`

`article.serving_quantity` (lot 2) est la portion **du fabricant**, propre à un
code-barres. La portion manuelle est celle **du foyer** : « chez moi, une part
de riz c'est 80 g », que le riz vienne d'un paquet de 500 g ou d'un sac de 1 kg.
Elle suit donc le produit, comme la portion apprise que
`repo.learned_portion(conn, product_id)` calcule déjà par produit, et comme
l'écran « manger », qui vise un produit.

### 8.2 La priorité, et l'endroit exact où le code en décide

L'ordre du lot 2, relevé dans le code — `websocket_api.product_get`,
lignes 349-359 : `learned` (médiane des trois dernières consommations), puis
`serving` (`article.serving_quantity` du lot FIFO), puis `None`. Confirmé par
`tests/test_websocket_consume.py` (80 g appris contre 200 g déclarés → 80) et
par `tests/storage/test_repositories_journal.py` (médiane des trois dernières,
jamais moins de trois, jamais un `waste`).

**La portion manuelle prime sur les deux.** Nouvel ordre, en une ligne, au même
endroit — `product_get` reste le **seul** endroit du dépôt qui décide d'une
portion :

```python
suggested, source = (
    (manual,  "manual")  if manual  is not None else
    (learned, "learned") if learned is not None else
    (serving, "serving") if serving is not None else (None, None))
```

`portion_source` est déjà renvoyé depuis le lot 2 ; il gagne `"manual"`. Une
valeur **saisie par une personne** l'emporte toujours sur une valeur
**déduite**, sinon la saisie n'a servi à rien — même règle que
`article.manual_fields`, qui protège d'une resynchronisation Open Food Facts
tout champ corrigé à la main.

### 8.3 Les bornes, reprises à l'identique du lot 2

Les trois refus de `off/mapping.plausible_serving()`, dans le même ordre :
**produit suivi en `g` ou `ml` uniquement** (une portion à la pièce vaut une
pièce, et le raccourci « 1 » est déjà armé pour 239 des 299 produits) ;
**`]0 ; 5000]`** (`MAX_SERVING` existe déjà) ; **jamais supérieure au poids net
connu** — sur un produit, le **plus grand `net_quantity` connu parmi ses
articles**, puisqu'un même riz existe en 500 g et en 1 kg et que 800 g reste une
portion (indigeste), pas une faute de saisie. Aucun poids connu → seule la borne
numérique s'applique.

Les trois vivent dans **une** fonction, `validators.check_manual_portion(value,
*, base_unit, max_net_quantity)`. La règle du lot 1 tient : **aucune des deux
surfaces n'a le droit d'être la plus faible**. `product/update` est aujourd'hui
la seule surface qui édite un produit (aucun service `home_stock.*` ne le
fait) ; le validateur est écrit dans `validators.py` et non dans
`websocket_api.py`, précisément pour qu'un futur service n'ait rien à réécrire.
Le front duplique la borne `]0 ; 5000]` pour refuser avant l'aller-retour, comme
il duplique déjà `PARTS_MAX` — **jamais** comme seul contrôle.

### 8.4 L'effacer, et où on la saisit

Envoyer `manual_portion: null`. Le catalogue applique déjà sa convention « une
saisie vide vaut `null` » (`champsModifies`, `analyserNombre`) : vider le champ
« Ma portion » rend le produit à la déduction automatique, et l'écran « manger »
repasse à `portion_source: "learned"` (ou `"serving"`) au rechargement suivant.

La saisie se fait **dans le Catalogue, et seulement là** : `manual_portion`
rejoint `PRODUCT_EDITABLE` et `CHAMPS_MODIFIABLES` à côté de `min_quantity`. Un
raccourci « en faire ma portion » depuis l'écran « manger » serait plus proche du
moment où l'on constate que la médiane se trompe, mais c'est un second chemin
d'écriture — file hors-ligne, clé d'idempotence et tests compris — pour un geste
posé une fois par produit. Reporté au § 14.

## 9. Matériau d'emballage et tri des déchets

**C'est le plus mince des trois sujets, et il est dimensionné comme tel** : un
module pur, deux champs ajoutés à une constante, un champ de plus dans une
réponse websocket existante, une ligne dans un écran existant. Zéro commande
nouvelle, zéro colonne, zéro migration.

### 9.1 Ce qu'il faut d'abord réparer

Le § 4 (A1) l'établit : la donnée n'est pas dans `off_raw`. Le lot commence donc
par ajouter `packagings,packaging_tags` à `off/client.FIELDS` — zéro requête de
plus, quelques centaines d'octets par fiche, très loin du plafond
`MAX_OFF_RAW_BYTES` de 256 kB. Le test
`test_the_requested_fields_are_the_ones_the_mapping_reads` devient le garde-fou
qui empêche de les retirer un jour sans le voir. **Conséquence pour
`docs/exploitation.md` :** la consigne n'apparaît que pour les articles
**scannés ou resynchronisés après le déploiement**, aucun rattrapage n'étant
possible ; `home_stock.resync_off` (une quarantaine de minutes, lot 1) la ramène
pour tout le catalogue en une passe.

### 9.2 La forme réelle de la donnée

- `packaging_tags` : tags plats, langue comprise (`["en:plastic", "fr:pot"]`),
  mélangeant matériau, forme et recyclabilité sans les distinguer ;
- `packagings` : une liste d'objets, un par composant — `{"material":
  "en:pp-polypropylene", "shape": "en:pot", "number_of_units": 4, …}`. Champ
  moderne, et le seul qui sépare proprement matériau et forme.

`off/packaging.py` lit **`packagings` d'abord**, retombe sur `packaging_tags`
seulement si le premier est absent ou vide, et applique la discipline défensive
de `serving_from_raw` : `off_raw` illisible, tronqué, non-objet ou liste
contenant autre chose que des dictionnaires → `None` sans lever. C'est un
confort d'affichage, jamais une donnée dont dépend le stock.

### 9.3 La consigne, et le bon moment

`RECYCLING_BINS = ("yellow", "glass", "household", "dropoff")` — bac jaune
(plastiques, cartons, briques, métal : l'extension des consignes de tri couvre
la France depuis 2023), bac à verre, ordures ménagères, déchèterie. Le serveur
rend **les clés** et les matériaux bruts, `frontend/src/tri.ts` les phrases
françaises.

**Le bon moment est le rebut, pas le rangement.** Au rangement, l'emballage est
plein et part dans un placard : personne ne trie alors, et l'afficher
encombrerait l'écran le plus chargé du panneau. La consigne s'affiche donc sur
l'écran **« manger »**, dans deux cas et deux seulement : le motif choisi est
**`Jeté`** ou **`Périmé`** ; ou la quantité choisie **vide le lot visé** (« Tout
le reste », ou une saisie ≥ au reste) — le cas réel, le pot de yaourt qu'on
finit.

Deux composants peuvent viser deux bacs (le pot et son étui) : la liste est
dédupliquée **par bac**, jamais par matériau — ce qu'on doit faire, c'est ouvrir
un ou deux couvercles, pas lire un inventaire. **Rien de connu → rien
d'affiché** : une consigne inventée envoie du verre dans le bac jaune avec
l'assurance de l'écran.

### 9.4 Pourquoi aucune colonne

La donnée est lue **une fois par ouverture de l'écran « manger »**, sur **un**
article — celui du lot FIFO, dont `list_batches_for_product` rend déjà
l'`article_id` : un `repo.article_off_raw(conn, article_id)` ciblé, dans le même
travail d'exécuteur que le reste de `product/get`. Elle n'est **jamais agrégée,
triée, filtrée, ni jointe** — une colonne ne servirait à rien de ce à quoi une
colonne sert, et coûterait une migration, une écriture à l'ingestion **et** à la
resynchronisation, un `apply()` de rattrapage qui (A1) ne trouverait rien, et
une valeur périmée dès qu'Open Food Facts corrige la fiche.

Compter un jour les emballages sortis par bac demanderait de **figer le bac sur
le mouvement**, comme les neuf nutriments — pas une colonne sur l'article.
Autre sujet, § 14.

## 10. Surface Home Assistant

### 10.1 Options

| Clé | Type | Défaut |
|---|---|---|
| `nutrition_goals` | dict `{nutriment: plafond}` | `{}` |

Le flux d'options gagne neuf champs `vol.Optional`, chacun validé par
`goal_quantity` (`]0 ; MAX_GOAL]`, fini, jamais booléen). Un champ vidé **omet
la clé** plutôt que d'écrire `0` — même mécanique que `CONF_RECIPE_AGENT` au
lot 3, pour la même raison : « pas d'objectif » doit rester exprimable.
Libellés dans `translations/fr.json` et `en.json`, sous
`options/step/init/data/`.

### 10.2 Commandes websocket

Aucune commande nouvelle. Une étendue :

| Commande | Ce qu'elle gagne |
|---|---|
| `home_stock/product/get` | `manual_portion` (la valeur brute), `portion_source` peut valoir `"manual"`, et `packaging` : `{"bins": ["yellow"], "materials": [...]}` ou `null` |
| `home_stock/product/update` | `manual_portion` rejoint `PRODUCT_EDITABLE` |
| `home_stock/journal/day` | `goals` : les plafonds réglés, pour que le panneau dessine la ligne d'objectif |

### 10.3 Services

Aucun service nouveau, aucun service modifié.

## 11. Le panneau

- **Catalogue** : un champ « Ma portion (g/ml) », masqué pour un produit suivi à
  la pièce, mention « vide = déduite automatiquement ». Il rejoint
  `CHAMPS_MODIFIABLES` et passe par la file hors-ligne comme les autres.
- **Manger** : le bouton devient « **Ma portion** (45 g) » quand
  `portion_source === 'manual'`, contre « 1 portion (45 g) » sinon — on doit
  voir d'où vient le chiffre proposé.
- **Manger** : la consigne de tri, aux deux conditions du § 9.3, sous les
  boutons de quantité. Une ligne, jamais une carte : la hauteur de l'écran ne
  doit pas bouger selon qu'un emballage est connu ou non.
- **Journal** : sous les totaux du jour, une ligne par objectif réglé — « Sel
  8,4 / 6 g » — et la même en gris pour la moyenne des sept journées closes
  quand elle dépasse. Aucun objectif réglé → aucune ligne, écran identique au
  lot 2.

Contraintes inchangées : aucun geste, virgule décimale acceptée partout,
`verifier-rendu.mjs` en 412×915 et 1280×800.

## 12. Erreurs

| Cas | Comportement |
|---|---|
| Portion manuelle sur un produit à la pièce | Refusée, message français ; le champ n'est pas offert par le panneau |
| Portion manuelle hors `]0 ; 5000]` ou > au plus grand poids net connu | Refusée avant écriture, message disant la borne |
| `manual_portion: null` | Accepté : c'est l'effacement (§ 8.4) |
| Objectif hors `]0 ; MAX_GOAL]` | Refusé par le flux d'options, l'entrée n'est pas enregistrée |
| Objectif sur un nutriment inconnu | Impossible : le formulaire est fermé sur `GOAL_NUTRIENTS` |
| Journée sans aucune sortie | Capteur `off`. Rien à annoncer (§ 7.5) |
| Objectif sur un nutriment au capteur éteint | Fonctionne : le calcul ne lit aucune entité (§ 7.2) |
| Journée dont les kcal sont inconnues | Comptée pour ce qu'elle porte ; `unvalued_movements` (lot 2) dit combien de sorties ne sont pas chiffrées |
| `off_raw` absent, tronqué, sans `packagings` | `packaging: null`, aucune consigne affichée, aucune erreur |
| `packagings` avec un matériau inconnu de la table | Le composant est ignoré ; les autres restent. Jamais de bac deviné |

## 13. Tests, et ce qu'il faut écrire dans `docs/exploitation.md`

Suites existantes vertes — `./scripts/test.sh` (1390 aujourd'hui), `npm test`
(405), `node outils/verifier-rendu.mjs` (39 scénarios) — plus :

**Python**

- `domain/goals.py` : dépassement jour, moyenne, les deux, aucun objectif réglé,
  objectif **atteint exactement** (pas un dépassement), tri par ratio.
- Fenêtre glissante : journée courante **exclue** ; sept journées dont une de
  23 h et une de 25 h (28 mars et 24 octobre 2026) toujours divisées par sept ;
  base sans historique → moyenne nulle, capteur `off`.
- Aucune entité lue : un objectif sur `fiber` se déclenche avec
  `sensor.home_stock_fiber_today` désactivé dans le registre.
- Frontière : 03:59 et 04:01 dans deux journées différentes ; après le
  rendez-vous de 4 h, un dépassement de la veille est retombé à `off`.
- Flux d'options : champs facultatifs, un champ vidé **omet** la clé, valeur
  hors bornes refusée.
- `m00N` (numéro du merge) : colonne créée, migration rejouable, produits
  existants à `NULL`, contiguïté des `VERSION` vérifiée.
- Portion : manuelle > apprise > Open Food Facts quand les trois existent ;
  `portion_source == "manual"` ; effacement par `null` rendant la main à
  l'apprise ; refus à la pièce, hors bornes, au-delà du plus grand poids net
  connu ; acceptation quand aucun poids n'est connu.
- `off/packaging.py` : `packagings` structuré, repli sur `packaging_tags`,
  composants dédupliqués par bac, matériau inconnu ignoré, `off_raw` absent /
  tronqué / non-objet / liste de non-dictionnaires → `None` sans lever.
- `off/client.py` : les deux champs présents dans `FIELDS`. Websocket :
  `product/get` rend `manual_portion` et `packaging`, `product/update` refuse
  une portion invalide en français.

**Front**

- `portion.test.ts` : « Ma portion » sur `manual`, « 1 portion » ailleurs.
- `catalogue.test.ts` : champ absent à la pièce, vide → `null`, virgule acceptée.
- `consommation.test.ts` : consigne affichée sur `Jeté`, `Périmé` et « Tout le
  reste » ; absente sur une sortie partielle en `Mangé` et quand `packaging`
  est `null`.
- `journal.test.ts` : ligne d'objectif présente, absente sans objectif réglé.
- `verifier-rendu.mjs` : deux scénarios de plus — « manger » avec consigne de
  tri, Journal avec trois lignes d'objectif — la hauteur du cadre ne bougeant
  pas.

**`docs/exploitation.md`** gagne une section « Lot 2bis » de trois
paragraphes : les objectifs se règlent dans **Paramètres → Appareils et
services → Garde-manger → Configurer** (champ vide = pas d'objectif ; inutile
d'allumer les cinq capteurs éteints pour cela) ; **rien n'est annoncé sans
importer le blueprint** `objectifs_bleuenn.yaml`, comme pour les dates limites ;
**la consigne de tri n'apparaît que sur les articles scannés ou resynchronisés
après cette version**, une passe `home_stock.resync_off` la ramenant pour tout
le catalogue.

**Interdit :** rien ne touche l'instance vivante. Pas de `docker compose`, pas
de redémarrage, pas de rechargement de l'intégration, pas de lecture du jeton,
aucune écriture dans `/opt/nivuus/HomeAssistant/config/`.

## 14. Points différés

| Sujet | Où | Raison |
|---|---|---|
| **Objectifs minimaux** | ultérieur | Un plancher n'a de sens qu'à la clôture de la journée : heure réglable, mémoire des annonces, donc une table. Un mécanisme, pas un champ (§ 7.5) |
| **Éditer les objectifs depuis le panneau** | ultérieur | Écrire dans les options depuis le websocket demande une commande, un validateur en double et un rechargement d'entrée, pour un geste annuel (§ 7.1) |
| **Objectif de dépense en euros** | 4 | L'argent est le sujet du lot 4 ; la mécanique du § 7 s'y branchera telle quelle, `cost` étant déjà dans `today` |
| **« En faire ma portion »** depuis l'écran « manger » | ultérieur | Second chemin d'écriture, file et clé comprises, pour un geste posé une fois par produit (§ 8.4) |
| **Portion manuelle à la pièce** | — | Une portion y vaut une pièce, et le raccourci « 1 » est déjà armé |
| **Compter les emballages par bac** | ultérieur | Demanderait de figer le bac **sur le mouvement**, comme les neuf nutriments (§ 9.4) |
| **Consignes de tri locales** | — | Aucune source ouverte fiable ; l'extension des consignes couvre la France depuis 2023, la table nationale suffit |
| **Objectifs par personne** | — | Le foyer ne suit qu'une personne, comme les parts du lot 2 le disent déjà |

*Rédigé le 2026-08-21.*
