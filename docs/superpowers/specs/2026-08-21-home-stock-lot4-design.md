# home_stock — Lot 4 : liste de courses, ticket de caisse et correction

*Conception validée le 2026-08-21. Suite des lots 0 à 3 et 5, dont ce document
reprend les conventions : code, schéma et identifiants en **anglais**, textes
affichés en **français** (`translations/fr.json`), quantités en unité de base,
journal en ajout seul, aucune clé d'API dans le composant.*

## 1. Objectif et livrable

Le lot 0 a résumé le lot 4 en une phrase et un critère de recette :

> Manques + planning → liste, pointage au scan, coût du panier, ticket de caisse
> (Gemini), ordre des rayons par magasin et apprentissage du parcours.
> **Livrable : une session de courses complète.**

« Complète » veut dire quelque chose de précis, et c'est ce que ce lot doit rendre
vrai bout à bout :

> Partir de la maison avec une liste que personne n'a écrite à la main ; la
> parcourir dans l'ordre du magasin où l'on est ; cocher en scannant ; savoir ce
> que le chariot coûte avant la caisse ; photographier le ticket et laisser la
> maison relire les prix ; ranger ; et, le lendemain, pouvoir corriger une ligne
> fausse sans réécrire l'histoire.

Le lot 1 a construit tout le mode magasin **sauf ce qui le rend utile** : la
session existe côté serveur, les lignes se scannent, le panier se trie par rayon,
le rangement crée les lots. Il manque ce qui vient **avant** le magasin (la liste)
et ce qui vient **après** la caisse (le ticket, la correction). Le lot 4 ferme les
deux bouts.

Il solde aussi une dette différée deux fois : **le journal est en ajout seul et
rien ne sait encore le corriger** (lot 2 § 18, lot 3 § 20). Une validation de repas
ne s'annule pas, un prix relevé de travers ne se reprend pas. Chaque jour sans
correction est un jour où la comptabilité kcal/€ s'éloigne du réel — et où l'on
apprend à ne plus lui faire confiance, ce qui est la seule panne dont un journal ne
se relève pas.

## 2. Périmètre

**Dans le lot :** la liste de courses, ses quatre origines et leur fusion sans
doublon ; l'entité `todo.home_stock_shopping` ; les lignes récurrentes ; le
pointage d'une ligne de liste par un scan en rayon ; la séparation du coût
**estimé** et du coût **constaté** dans le panier ; le ticket de caisse
photographié, lu par une entité `ai_task` de la maison, rapproché du panier et
appliqué ; le magasin promu en table ; l'ordre des rayons par magasin, appris des
sessions réelles et corrigible à la main ; la correction d'un mouvement déjà écrit
et la correction de prix ; deux écrans de panneau et quatre modifiés ; la migration
`m006` ; les commandes websocket et les services associés.

**Hors du lot :** les tablettes murales, la vue dense PC et le vocal Bleuenn
(lot 6) ; la reprise du stock, de l'historique et des recettes Grocy, et l'arrêt du
conteneur (lot 7) ; les objectifs de budget mensuel ; la contribution de prix vers
Open Prices (écartée définitivement au lot 1) ; plusieurs personnes qui font les
courses en même temps.

**Hors du lot, et ce n'est pas un oubli :** le lot 4 n'écrit **rien** dans
`/opt/nivuus/HomeAssistant/config/` en dehors de sa propre base et du dossier
`media/` que Home Assistant expose déjà. Aucun redémarrage de conteneur, aucun
rechargement d'intégration, aucune lecture de jeton — règle posée au lot 1 et
répétée à chaque lot depuis.

## 3. Décisions validées

| Question | Réponse retenue |
|---|---|
| Où vit la liste | Une table `shopping_list_item` **plus une entité `todo` native**. Le lot 0 l'avait annoncée dans la colonne Lovelace de sa répartition ; c'est tenu |
| Fusion des origines | Une ligne **par produit**, et autant de **revendications** (`claim`) qu'il y a de raisons de l'acheter. La quantité de la ligne est le maximum de ses revendications |
| Que veut dire cocher | **« Je l'ai »**, jamais « c'est en stock ». Une case porte un bit ; l'entrée en stock reste le scan et le rangement du lot 1 |
| Qui possède la liste | **Le composant**, comme `todo.maintenance` appartient à son automation. Une ligne ajoutée à la main est respectée ; une ligne de rupture disparaît quand la rupture disparaît |
| Coût du panier | Un total unique, **dont la part estimée est dite en toutes lettres**. On ne présente jamais une somme de suppositions comme un montant |
| Ticket de caisse | Une entité **`ai_task`** désignée dans les options, appelée avec la photo en pièce jointe et une **structure** de réponse. Reprise de la décision du lot 3 : aucune clé d'API dans le composant |
| Envoi de la photo | **La vue de téléversement de Home Assistant** (`/api/media_source/local_source/upload`), pas une vue HTTP maison |
| Ordre des rayons | Appris du **rang moyen de scan** sur les sessions d'un magasin, fiable à partir de **trois** sessions, épinglable à la main |
| Corriger un mouvement | Une **écriture miroir** qui porte le motif de celle qu'elle annule et un lien `corrects_id`, jamais une valeur `reason` nouvelle. Un mouvement ne s'annule qu'**une** fois, garanti par index |
| Compteurs cumulés | `kcal_total`, `cost_total` et `cost_waste_total` passent de `TOTAL_INCREASING` à **`TOTAL`**. Un compteur qui peut légitimement baisser ne se déclare pas croissant |

## 4. Amendements aux specs précédents

Quatre points changent. Ils sont normatifs.

### A1 — `correction` est un **lien**, pas une valeur de `reason`

Le lot 2 (§ 18) et le lot 3 (§ 20) ont tous deux écrit « motif `correction` ». C'est
la formulation naturelle, et elle est fausse : la mettre en œuvre telle quelle
casse la comptabilité qu'elle prétend réparer.

`reason` n'est pas une étiquette décorative dans ce schéma, c'est le **compte
comptable** de la ligne. Quatre endroits en dépendent : `repo.totals_between`
(coût et sorties non chiffrées, filtrés sur `consumption` et les deux motifs de
gaspillage), `repo._PERSONAL_SUMS` (les neuf nutriments pondérés par les parts),
`repo.journal_entries` et `repo.counted_movements` (journal du jour et séries du
panneau, bornés sur `CONSUME_REASONS`), et les onze capteurs du lot 2 qui les
lisent.

Un mouvement de motif `correction` serait **invisible des quatre** : il annulerait
le stock sans annuler les calories ni les euros. Le rendre visible imposerait
d'apprendre aux quatre requêtes qu'une correction compense « le motif de l'autre »
— donc de stocker ce motif quelque part, donc de réintroduire par la fenêtre ce
qu'on croyait sortir par la porte.

**La règle comptable est plus simple et plus ancienne que ce composant : une
écriture de contrepassation porte le compte de l'écriture qu'elle annule, avec le
signe inverse.** Le lot 4 la reprend telle quelle. Une correction est un mouvement
ordinaire, de motif identique à celui qu'il compense, dont la quantité, le coût et
les neuf nutriments sont négatifs, et qui porte en plus `movement.corrects_id`
pointant sur la ligne annulée. Toutes les sommes existantes se corrigent alors
**sans qu'une seule requête soit touchée**.

`REASONS` ne gagne donc aucune valeur au lot 4. C'est aussi la conclusion à
laquelle le lot 5 était arrivé pour les piles (son A3), pour exactement la même
raison, et la répétition n'est pas un hasard : dans ce schéma, ajouter un motif est
une opération beaucoup plus chère qu'elle n'en a l'air.

### A2 — Trois compteurs cumulés passent en `state_class: TOTAL`

`sensor.home_stock_kcal_total`, `cost_total` et `cost_waste_total` sont déclarés
`TOTAL_INCREASING`. Une correction les fait **baisser**, et Home Assistant lit une
baisse sur un `TOTAL_INCREASING` comme une remise à zéro d'appareil : il ajoute
alors la nouvelle valeur au cumul déjà enregistré, ce qui produit un saut au lieu
d'une soustraction. Le lot 2 a documenté cette lecture exacte, sur ces capteurs
exacts, en assumant une rupture une fois.

`TOTAL` sans `last_reset` est la déclaration honnête : Home Assistant somme alors
les **différences** entre relevés successifs, et une différence négative est une
donnée valide. C'est le seul `state_class` compatible avec un compteur qu'on a le
droit de corriger.

Le prix est le même qu'au lot 2 et il se paie une seconde et dernière fois : les
statistiques déjà enregistrées gardent l'ancienne définition, et Home Assistant
ouvre un `repair` « la classe d'état a changé » qu'il faut résoudre en supprimant
les statistiques de ces trois entités. **Ce geste appartient au propriétaire et il
est écrit dans `docs/exploitation.md`** — le composant ne supprime jamais de
statistiques tout seul. Les onze capteurs `_today` ne bougent pas.

### A3 — Un prix suggéré n'est pas un prix observé

Le lot 1 a posé une cascade de prix à quatre rangs, dont le rang 1 est « le dernier
prix connu de cet article **dans ce magasin** ». `ShoppingService.add_line` écrit
aujourd'hui une ligne `price` de source `manual` **dès que la ligne porte un
prix** — y compris quand ce prix est la suggestion Open Prices que le panneau avait
pré-remplie et que personne n'a touchée.

Conséquence, mesurable dès le deuxième voyage : une suggestion Open Prices acceptée
sans y penser devient une observation faite dans ce magasin, prend le rang 1 de la
cascade et **écrase la vraie source de vérité** — l'étiquette du rayon. La cascade
se nourrit alors de ses propres suppositions.

`shopping_line` reçoit donc une colonne `price_source`, et `price.source` reçoit la
valeur correspondante : `manual` quand la valeur a été tapée ou modifiée,
`open_prices` quand elle vient de la suggestion et n'a pas bougé, `receipt` quand
elle vient du ticket. `repo.latest_price_in_store` ne considère plus que les
sources **observées** (`manual`, `receipt`, `import`) : une supposition ne remonte
jamais au rang 1.

### A4 — Le magasin devient une table

`shopping_session.store` et `price.store` sont des chaînes libres. C'était suffisant
tant que le magasin ne servait qu'à filtrer une cascade de prix ; ça ne l'est plus
dès qu'un ordre de rayons lui est rattaché, qu'un ticket le nomme et qu'un capteur
l'affiche. « Leclerc », « leclerc » et « E.Leclerc » sont aujourd'hui trois
magasins.

`m006` crée `store`, y verse les enseignes distinctes déjà présentes dans les deux
colonnes, et ajoute `shopping_session.store_id`. **`price.store` reste une chaîne
et n'est pas réécrite** : `price` est un journal d'observations, chaque ligne dit ce
qui a été vu le jour où ça l'a été. On lui adjoint `store_id`, rempli pour les
lignes reconnues, `NULL` pour les autres. Réécrire le texte pour faire joli, c'est
exactement ce que le lot 0 refuse au journal des mouvements, et un journal de prix
n'est pas d'une autre nature.

## 5. Architecture

Aucune couche nouvelle. Les règles vivent dans le domaine pur, la lecture dans les
dépôts, l'orchestration dans `application.py` et `shopping.py`, la surface dans le
websocket et les services. Un seul module Home Assistant nouveau : celui qui parle
à l'entité `ai_task`, isolé pour la même raison que `off/client.py` l'est — c'est le
seul endroit du lot qui sort du processus.

| Fichier | Rôle |
|---|---|
| `domain/shoppinglist.py` | **Nouveau.** Fusion des origines, revendications, réconciliation. Pur, sans `hass`, sans SQLite |
| `domain/route.py` | **Nouveau.** Apprentissage de l'ordre des rayons à partir de suites de scans. Pur, déterministe |
| `domain/correction.py` | **Nouveau.** L'algèbre d'une contrepassation : ce qui change de signe, ce qui se recopie, ce qui se refuse |
| `domain/matching.py` | Étendu : rapprochement d'une ligne de ticket sur une ligne de panier |
| `domain/pricing.py` | Étendu : `suggest_price` distingue désormais une valeur **observée** d'une valeur **suggérée** |
| `receipt/task.py` | **Nouveau.** Le seul appel à `ai_task`. Aucun accès SQLite |
| `receipt/parse.py` | **Nouveau.** Réponse du modèle → lignes validées. Aucun réseau, aucun `hass` |
| `shopping.py` | Étendu : pointage au scan, source de prix, clôture qui apprend le parcours |
| `application.py` | Étendu : réconciliation de la liste, correction d'un mouvement, application d'un ticket |
| `storage/migrations/m006_shopping.py` | **Nouveau.** Tables, colonnes, remplissage rétroactif |
| `storage/repositories.py` | Dépôts de la liste, du magasin, de l'ordre des rayons, du ticket |
| `todo.py` | Une seconde liste : `todo.home_stock_shopping` |
| `sensor.py` | Trois capteurs de plus, `cart_total` enrichi |
| `websocket_api.py` | Les commandes de la liste, du magasin, de la correction |
| `websocket_receipts.py` | **Nouveau.** Les commandes du ticket, comme `websocket_recipes.py` et `websocket_batteries.py` avant lui |
| `frontend/src/ecrans/liste.ts` | **Nouveau.** La liste, dans l'ordre du magasin |
| `frontend/src/ecrans/ticket.ts` | **Nouveau.** Photographier, relire, appliquer |

`domain/shoppinglist.py`, `domain/route.py`, `domain/correction.py` et
`receipt/parse.py` ne connaissent ni `hass`, ni le réseau, ni SQLite. Même
discipline que `off/mapping.py` et `domain/conversion.py` au lot 1, et pour la même
raison : ce sont les quatre endroits où une erreur se paie cher et où un test ne
doit rien avoir à démarrer. `websocket_receipts.py` est séparé parce que
`websocket_api.py` fait déjà 1 251 lignes et que les lots 3 et 5 ont créé le
précédent.

## 6. Migration `m006`

### 6.1 Le numéro

L'état réel de `storage/migrations/` au 2026-08-21 est `m001_initial` … `m005_equipment`
(VERSION 1 à 5) : le lot 5, fusionné avant le lot 4, a pris le premier numéro libre
plutôt que le `m006` que son spec annonçait — exactement ce que son § 6.1 demandait.
**Le lot 4 prend donc `m006`, `VERSION = 6`.**

`test_migration_versions_are_contiguous_from_one` exige `[1, 2, …, n]` sans trou et
`test_migration_modules_are_named_after_their_version` un fichier `m006_*`. Les deux
passent avec `m006_shopping.py` / `VERSION = 6`, et **il ne faut pas les affaiblir** :
un dépassement de version saute une migration définitivement (`apply_migrations` ne
redescend jamais) et sans bruit.

### 6.2 DDL

```sql
-- Le magasin, promu de chaîne libre à ligne (amendement A4).
CREATE TABLE store (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  position INTEGER NOT NULL DEFAULT 0,  -- ordre d'affichage des pastilles
  active INTEGER NOT NULL DEFAULT 1
);

-- L'ordre du parcours DANS ce magasin. Une ligne par rayon effectivement
-- rencontré : un rayon jamais vu ici garde sa place par défaut (aisle.position).
CREATE TABLE store_aisle (
  store_id INTEGER NOT NULL REFERENCES store(id),
  aisle_id INTEGER NOT NULL REFERENCES aisle(id),
  position INTEGER NOT NULL,
  -- 'learned' : recalculé à chaque clôture de session.
  -- 'manual'  : épinglé par le propriétaire, jamais déplacé par l'apprentissage.
  source TEXT NOT NULL CHECK (source IN ('learned','manual')),
  mean_rank REAL,                 -- le rang moyen observé, pour l'explication
  observed_sessions INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT,
  PRIMARY KEY (store_id, aisle_id)
);

-- La liste. Une ligne par produit à acheter, quelles que soient les raisons.
CREATE TABLE shopping_list_item (
  id INTEGER PRIMARY KEY,
  product_id INTEGER REFERENCES product(id),
  free_text TEXT,                 -- une ligne qui ne nomme aucun produit
  quantity REAL,                  -- unité de base du produit ; NULL = « ce qu'il faut »
  note TEXT,
  added_at TEXT NOT NULL,
  checked_at TEXT,                -- « je l'ai » (§ 7.5), jamais « c'est en stock »
  removed_at TEXT,                -- retiré à la main : la réconciliation le respecte
  session_id INTEGER REFERENCES shopping_session(id),
  line_id INTEGER REFERENCES shopping_line(id),
  CHECK (product_id IS NOT NULL OR free_text IS NOT NULL)
);

-- Au plus UNE ligne ouverte par produit. C'est la règle anti-doublon, tenue par
-- la base et non par la bonne volonté des quatre producteurs de lignes.
CREATE UNIQUE INDEX idx_list_open_product ON shopping_list_item(product_id)
  WHERE product_id IS NOT NULL AND checked_at IS NULL AND removed_at IS NULL;

-- Pourquoi cette ligne est là. Autant de revendications que de raisons.
CREATE TABLE shopping_list_claim (
  item_id INTEGER NOT NULL REFERENCES shopping_list_item(id) ON DELETE CASCADE,
  origin TEXT NOT NULL CHECK (origin IN ('shortage','meal_plan','manual','recurring')),
  quantity REAL,                  -- ce que CETTE raison réclame, unité de base
  detail TEXT,                    -- « Dîner de jeudi », « seuil 500 g », « toutes les 3 sem. »
  claimed_at TEXT NOT NULL,
  PRIMARY KEY (item_id, origin)
);

-- Ce qu'on rachète sans que rien ne le réclame : le café, les sacs poubelle.
CREATE TABLE shopping_recurring (
  id INTEGER PRIMARY KEY,
  product_id INTEGER REFERENCES product(id),
  free_text TEXT,
  quantity REAL,
  every_days INTEGER NOT NULL,
  last_added_on TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  CHECK (product_id IS NOT NULL OR free_text IS NOT NULL)
);

-- Le ticket photographié, et ce que le modèle en a lu.
CREATE TABLE receipt (
  id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES shopping_session(id),
  media_content_id TEXT NOT NULL, -- media-source://… rendu par le téléversement HA
  captured_at TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','read','failed','applied','discarded')),
  store_id INTEGER REFERENCES store(id),
  purchased_on TEXT,
  total REAL,                     -- le total lu sur le ticket, tel quel
  agent_entity_id TEXT,           -- QUI a lu : l'entité ai_task, figée sur la ligne
  read_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,                     -- en français, affichable tel quel
  raw TEXT                        -- la réponse du modèle, brute, comme article.off_raw
);

CREATE TABLE receipt_line (
  id INTEGER PRIMARY KEY,
  receipt_id INTEGER NOT NULL REFERENCES receipt(id),
  position INTEGER NOT NULL,
  label TEXT NOT NULL,            -- le libellé de caisse, illisible et abrégé
  quantity REAL,
  unit_price REAL,                -- € par unité VENDUE, pas par unité de base
  total_price REAL,
  line_id INTEGER REFERENCES shopping_line(id),
  article_id INTEGER REFERENCES article(id),
  -- Même vocabulaire qu'au lot 3 pour l'appariement d'un ingrédient : quatre
  -- états, les mêmes mots, la même signification.
  match_state TEXT NOT NULL DEFAULT 'unmatched'
    CHECK (match_state IN ('unmatched','auto','confirmed','ignored')),
  applied_at TEXT
);

-- La contrepassation (amendement A1). UNIQUE : un mouvement ne s'annule qu'une
-- fois. Deux corrections d'une même ligne rembourseraient deux fois.
ALTER TABLE movement ADD COLUMN corrects_id INTEGER REFERENCES movement(id);
CREATE UNIQUE INDEX idx_movement_corrects ON movement(corrects_id)
  WHERE corrects_id IS NOT NULL;

ALTER TABLE shopping_session ADD COLUMN store_id INTEGER REFERENCES store(id);
ALTER TABLE shopping_line ADD COLUMN price_source TEXT;   -- amendement A3
ALTER TABLE price ADD COLUMN store_id INTEGER REFERENCES store(id);

CREATE INDEX idx_list_open ON shopping_list_item(checked_at, removed_at);
CREATE INDEX idx_receipt_line_receipt ON receipt_line(receipt_id, position);
CREATE INDEX idx_store_aisle_order ON store_aisle(store_id, position);
```

### 6.3 Remplissage rétroactif

`m006` expose un `apply(conn)` — le mécanisme existe depuis `m002` — qui fait trois
choses, toutes rejouables :

1. **Crée les magasins** depuis les chaînes distinctes non vides de
   `shopping_session.store` puis `price.store`, et renseigne les deux `store_id` par
   égalité **exacte**. Aucun rapprochement approximatif : fusionner « Leclerc » et
   « E.Leclerc » est une décision, pas une migration, et le panneau le fait à la main
   (§ 11.1). Une migration qui devine réunit un jour deux magasins réellement
   différents, sans trace.
2. **Renseigne `shopping_line.price_source` à `manual`** partout. C'est faux dans le
   détail — certaines valeurs étaient des suggestions acceptées — et c'est le choix le
   moins nuisible : `manual` **conserve** le comportement actuel de la cascade, alors
   que marquer `open_prices` rétroactivement supposerait de deviner et effacerait des
   prix réellement tapés. À partir de `m006` la colonne dit la vérité ; avant, elle
   dit « on ne sait pas, on ne touche à rien ».
3. **Ne crée aucune ligne de liste.** La liste se construit à la première
   réconciliation (§ 7.3). Une migration qui sème 40 lignes ferait apparaître au
   premier redémarrage une liste que personne n'a demandée — et la première impression
   d'une liste de courses décide si on s'en sert.

La migration est **rejouable**, et testée sur une **copie** de la vraie base issue du
lot 5, pas sur une base vide.

## 7. La liste de courses

### 7.1 Quatre origines, et une seule est humaine

| Origine | D'où elle vient | Ce qu'elle réclame |
|---|---|---|
| `shortage` | `binary_sensor.home_stock_shortages`, donc `repo.shortage_rows` : tout produit actif sous `min_quantity` | `min_quantity − stock` |
| `meal_plan` | `sensor.home_stock_missing_ingredients`, donc `repo.missing_products_between` sur sept jours | `needed − available`, déjà mis à l'échelle des convives |
| `manual` | Le panneau, l'entité `todo`, `home_stock.add_to_shopping_list`, le vocal au lot 6 | ce qui a été demandé, ou rien |
| `recurring` | `shopping_recurring`, quand `last_added_on + every_days ≤ aujourd'hui` | la quantité déclarée |

**Les rechanges de piles et les consommables du lot 5 n'ont besoin d'aucun code
ici**, et c'est le résultat le plus satisfaisant de ce découpage. Le lot 5 a fait de
la CR2032 de rechange un `product` avec `edible = 0`, refusant un
`binary_sensor.home_stock_spares_missing` au motif que ce serait « la même donnée,
sur la même tablette, sous deux noms ». La conséquence se récolte ici : une rechange
sous son seuil est un produit sous son seuil, elle produit une revendication
`shortage` et apparaît au rayon « Entretien et maison ». Le filtre du purificateur et
les sacs de l'aspirateur suivent le même chemin. **Le lot 4 ne contient pas une ligne
de code qui connaisse le mot « pile ».** Un produit non comestible ne se distingue
dans la liste que par son rayon — ce qui est exactement l'information utile.

### 7.2 Les revendications, ou pourquoi la fusion n'est pas un `UNION`

Écrire la liste comme la réunion de quatre requêtes dédupliquée sur le produit échoue
sur trois cas quotidiens :

- **Le lait est réclamé deux fois** — sous son seuil *et* manquant pour le gratin de
  jeudi. Une ligne, mais quelle quantité ? Pas la somme (on n'achète pas deux fois le
  même litre), pas la première venue.
- **La rupture disparaît, le repas reste.** On rachète du lait : la revendication
  `shortage` s'éteint, celle du planning tient. La ligne doit survivre.
- **La ligne a été barrée à la main.** La réconciliation suivante ne doit pas la
  remettre.

D'où le couple `shopping_list_item` / `shopping_list_claim` : **l'item est une ligne
de liste, la revendication est une raison de l'acheter**, au plus une par origine.

```
quantity(item) = MAX(quantity(claim) non nulles) ; NULL si aucune
```

Le maximum et non la somme : un seuil de réapprovisionnement et un besoin de recette
décrivent le même stock manquant vu de deux côtés, pas deux stocks. Une revendication
sans quantité (`manual`, « prends du pain ») n'écrase jamais une quantité connue et ne
s'y ajoute pas ; sans aucune valeur, la ligne dit « ce qu'il faut ».

### 7.3 La réconciliation

`domain/shoppinglist.reconcile()` : fonction pure recevant l'état voulu (les quatre
productions d'origines) et l'état réel, rendant **à créer / à mettre à jour / à
retirer**. Aucun accès base, aucun `hass` — la même forme, et sciemment la même
sémantique `items` / `keep`, que la macro `maintenance_plan()` de la maison.

Elle tourne au démarrage, sur le tic de 15 minutes du coordinateur, après toute
écriture qui change une rupture ou le planning, et à la demande
(`home_stock.refresh_shopping_list`).

1. **Une revendication qui n'est plus fondée est supprimée.**
2. **Un item sans revendication et jamais coché est retiré** (`removed_at`), sauf
   revendication `manual` — règle 5.
3. **Un item coché est laissé tranquille tant que la session en cours n'est pas
   close.** C'est la fenêtre entre le chariot et le placard : la rupture existe
   encore en base, et rien ne doit remettre la ligne pendant qu'on est à la caisse.
4. **Un item coché dont la session est close est purgé.** Si la rupture persiste — on
   a coché sans acheter, ou pas assez — une ligne neuve est recréée. La liste dit ce
   qui manque *maintenant*.
5. **Une ligne posée à la main n'est jamais retirée par le robot.** Seule dérogation
   à « la liste appartient au composant », et indispensable : sans elle, « prends des
   piles pour la télécommande du salon » disparaîtrait en quinze minutes.

**Hystérésis.** Une revendication `shortage` apparaît sous `min_quantity` et **se
maintient** jusqu'à `min_quantity × 1,15`. Sans cette marge, un produit qui oscille
autour de son seuil fait clignoter sa ligne tous les quarts d'heure, et une liste qui
clignote est une liste qu'on n'ouvre plus.

**Jamais de fermeture sur une donnée absente.** Seuil supprimé, produit désactivé,
appariement de recette défait : la revendication est **maintenue**. Règle reprise mot
pour mot de `maintenance.jinja` — on ne retire une ligne que sur une mesure qui prouve
que le besoin a disparu, jamais sur une absence de mesure. C'est ce qui évite les
disparitions fantômes au redémarrage, quand les entités sont encore muettes.

### 7.4 Pourquoi une entité `todo` native

Le lot 0 avait rangé « Liste de courses cochable (`todo`) » dans la colonne
**Lovelace** de sa répartition (§ 5.1). Le lot 4 tient la promesse plutôt que
d'ajouter un écran, pour quatre raisons qui tiennent à ce qu'une liste de courses est.
Elle **se consulte ailleurs** que dans le panneau : carte `todo-list`, application
mobile, tablette murale au lot 6, automation. Elle **se dit à la voix** —
`todo.add_item` et `todo.get_items` sont des services standards que les agents de la
maison comprennent déjà, donc « Bleuenn, ajoute du beurre à la liste » marche sans que
le lot 6 écrive un intent. **Le précédent existe et marche**
(`todo.home_stock_expirations`, lot 0, sa règle « cocher vaut consommé », son
garde-fou sur un `uid` périmé). Et **le panneau ne perd rien** : il lit la même table
par websocket, avec quantités, rayons et origines.

**Fonctionnalités déclarées** : `CREATE_TODO_ITEM | UPDATE_TODO_ITEM |
DELETE_TODO_ITEM`. Pas de `SET_DUE_DATE` — une ligne de courses n'a pas d'échéance, et
en annoncer une promettrait un tri qui n'existe pas. Pas de `MOVE_TODO_ITEM` :
**l'ordre de la liste est celui du magasin**, il est calculé (§ 11), et laisser une
carte Lovelace le réordonner ferait diverger les deux surfaces sur la seule chose que
ce lot passe son temps à apprendre.

`uid` = l'identifiant de `shopping_list_item` · `summary` = « Lait — 2 L » via
`format_quantity` · `description` = les origines en clair (« sous le seuil · dîner de
jeudi »). Créer depuis la carte crée une ligne `manual` (`free_text` si aucun produit
ne dépasse le seuil de présélection du lot 1) ; supprimer depuis la carte vaut
`removed_at`, jamais un `DELETE` — la réconciliation doit se souvenir qu'on n'en veut
pas.

### 7.5 Cocher veut dire « je l'ai », jamais « c'est en stock »

C'est la décision la plus importante de la section, et elle reprend l'argument tranché
au lot 0 pour `todo.home_stock_expirations` : **une case cochée ne porte qu'un bit.**
Elle ne peut dire ni quel article, ni quelle quantité, ni quel prix, ni quel
emplacement, ni quelle DLC — exactement les cinq informations qu'il faut pour créer un
lot.

Cocher ne crée donc **aucun lot, aucun mouvement, aucune entrée en stock** : ça marque
l'intention comme satisfaite. L'entrée en stock reste le chemin du lot 1 — on scanne,
on range. Le pointage du § 8 fait le lien dans le sens naturel : **c'est le scan qui
coche, pas la case qui range.**

Conséquence à dire au propriétaire, et écrite dans `docs/exploitation.md` : une ligne
cochée sans achat réel revient à la synchronisation suivante, une fois la session
close. Même contrat que `todo.maintenance` (« cocher une tâche à la main ne sert à
rien si la condition persiste »).

**Ce qui n'est pas dans la liste** : pas de sous-listes, pas de partage entre
personnes, pas de magasin par ligne. Une ligne se rattache à un rayon, le rayon à un
ordre, l'ordre à un magasin — c'est tout ce dont un parcours a besoin.

## 8. Le pointage au scan

Une seule règle, greffée sur `session/add_line` du lot 1, dans la même transaction que
l'insertion de la ligne :

> Si un item de liste ouvert porte le produit de l'article scanné, il est coché :
> `checked_at` prend l'instant, `session_id` et `line_id` retiennent qui l'a coché.

Le rattachement se fait **sur le produit, pas sur l'article** — même règle qu'au lot 3
pour les ingrédients, et même raison : la liste dit « du lait », le rayon propose une
brique de telle marque. Un article inconnu créé au scan et rattaché à « Lait » coche
donc la ligne « Lait » sans rien de plus.

**Un article qui n'y était pas** entre au panier comme les autres, et rien d'autre ne
se produit : acheter ce qu'on n'avait pas prévu est le comportement normal d'un être
humain dans un magasin, pas une anomalie à signaler. Le panier affiche un compteur
« *n* hors liste », utile à une seule chose — savoir, à la caisse, combien d'articles
se sont invités. Un appui les isole.

**Décocher.** `session/remove_line` sur une ligne qui avait coché un item **le
décoche** : retirer une ligne du panier, c'est reposer l'article sur l'étagère.
`update_line` ne touche à rien. Une ligne déjà rangée ne décoche plus — `remove_line`
y est déjà refusé par le lot 1 (« corrigez le lot, pas la liste ») et l'item est purgé
ou recréé par la réconciliation.

**Le pointage n'est jamais une condition du scan** : liste vide, produit absent, table
verrouillée — la ligne de panier s'écrit quand même. Règle générale du composant
depuis le lot 1 : ce qui est accessoire ne bloque jamais ce qui est essentiel.

**Idempotence.** `add_line` rejoué avec la même clé rend la ligne déjà créée sans rien
réécrire, donc sans re-cocher. La file hors ligne rejoue dans l'ordre : un
`remove_line` posté après un `add_line` décoche après avoir coché, et l'état final est
le bon.

## 9. Le coût du panier : estimé et constaté

`sensor.home_stock_cart_total` existe depuis le lot 1 et somme
`quantity × unit_price`. Le chiffre est utile et **ambigu** : une partie vient de
l'étiquette du rayon, une autre d'une suggestion Open Prices que personne n'a
vérifiée, une troisième n'existe pas (ligne sans prix, comptée zéro par `COALESCE`).

| Catégorie | Ce que c'est | `price_source` |
|---|---|---|
| **Constaté** | Prix tapé ou corrigé par un humain devant l'étiquette, ou lu sur le ticket | `manual`, `receipt` |
| **Estimé** | Suggestion acceptée sans y toucher | `open_prices`, `last_known`, `store` |
| **Inconnu** | Aucun prix. Compté **zéro dans le total, et signalé** | `NULL` |

`domain/pricing.suggest_price` rend déjà une `PriceSuggestion` avec sa `source` ; il
suffit que le panneau la transmette à `add_line` au lieu de la jeter — c'est
`shopping_line.price_source` (amendement A3), la même colonne qui protège la cascade
de ses propres suppositions.

Le panier affiche : `47,20 € — dont 12,30 € estimés, 2 lignes sans prix`. Une ligne,
trois faits, aucune moyenne trompeuse. C'est le chiffre qu'on compare mentalement au
ticket ; un écart inexpliqué détruit la confiance dans tout le reste.

`cart_total` garde son état et gagne les attributs `estimated`, `observed`,
`unpriced_lines`, `off_list_lines`, `store`. Aucun capteur nouveau pour le panier : le
lot 0 a posé qu'une synthèse s'enrichit d'attributs plutôt que de se dupliquer.

**La liste a son estimation à elle.** `sensor.home_stock_list_estimate` donne ce que
la liste ouverte coûterait, en appliquant la cascade du lot 1 à l'article d'achat
habituel de chaque produit (le dernier acheté, à défaut l'article générique). C'est
**entièrement estimé**, et l'attribut `confidence` porte la proportion de lignes
réellement chiffrées. Ce capteur répond à « ça va faire combien ? » et à rien d'autre :
il n'entre dans aucune comptabilité.

**Le coût par nutriment est gratuit.** Le lot 2 a figé les neuf nutriments sur *tout*
mouvement, achats compris, en annonçant que ça « rendrait le lot 4 gratuit ». C'est
vérifié : le panier connaît les kilocalories qu'il rapporte sans une colonne de plus.
Le panneau l'affiche en second rang, comme une curiosité et non une décision.

## 10. Le ticket de caisse

### 10.1 Une entité `ai_task`, et pourquoi pas `conversation`

Le lot 3 a tranché : **aucune clé d'API dans le composant**, l'adaptation passe par
un agent de Home Assistant désigné dans les options. Ses quatre raisons valent mot
pour mot ici — pas de second magasin de secrets, la maison a déjà ses backends Gemini,
le composant part sur HACS et ne code aucun fournisseur en dur, et la `GEMINI_KEY` de
`data/tools/grocy-off/.env` est une clé d'outillage jamais recopiée.

**La décision est reprise ; c'est l'entité qui change, parce que l'entrée change : un
ticket est une image, pas une phrase.** `conversation.process` prend un texte et rend
un texte ; il n'a ni pièce jointe ni réponse structurée, et décrire la photo est
précisément l'information qu'on cherche à extraire.

Home Assistant 2026.8.2 fournit la porte qu'il faut — vérifié dans l'image de test
alignée sur la version du foyer (`ai_task/task.py`) :
`ai_task.async_generate_data(hass, task_name=…, entity_id=…, instructions=…,
structure=…, attachments=[…])`. Trois choses que `conversation` n'a pas :

- **`attachments`** — des `media_content_id` résolus par `media_source` vers un
  fichier local et transmis au modèle. L'entité doit déclarer
  `AITaskEntityFeature.SUPPORT_ATTACHMENTS`, sans quoi l'appel est refusé avant le
  réseau.
- **`structure`** — un schéma de sortie. Le modèle rend un objet conforme, pas une
  phrase contenant du JSON : la gymnastique du lot 3 (« le premier bloc délimité par
  des accolades équilibrées ») disparaît.
- **Le même fournisseur, sans configuration en plus.** L'intégration Google Generative
  AI déjà présente expose une entité `ai_task` à côté de son entité `conversation`,
  sur la même entrée et la même clé.

| Option | Défaut | Effet |
|---|---|---|
| `receipt_agent` | *(vide)* | Sélecteur `entity` sur le domaine `ai_task`. Vide → aucune lecture, et le panneau le dit au lieu d'afficher un bouton mort |

**L'option est validée quand elle est choisie**, pas quand elle sert : une entité sans
`SUPPORT_ATTACHMENTS` est refusée par le flux d'options, en français. Découvrir
l'incompatibilité à 21 h sur un parking n'est pas un moment acceptable pour
l'apprendre.

### 10.2 Le chemin de la photo, sans une ligne de HTTP maison

Le lot 5 a refusé d'écrire un point d'entrée de téléversement pour les notices, un
geste fait deux fois par an. Un ticket arrive à chaque voyage — et **le point d'entrée
n'a toujours pas à être écrit**, parce que Home Assistant en fournit un :

```
POST /api/media_source/local_source/upload
  media_content_id = media-source://media_source/local/home_stock/receipts
  file             = la photo
→ { "media_content_id": "media-source://media_source/local/home_stock/receipts/…jpg" }
```

Cette vue (`media_source/local_source.py`) est **authentifiée et réservée aux
administrateurs**, plafonne à 20 Mo, refuse tout ce qui n'est pas `image/*`,
`video/*` ou `audio/*`, valide nom de fichier et chemin cible, et rend exactement le
`media_content_id` que `ai_task.generate_data` attend. Rien à écrire, rien à
sécuriser, rien à maintenir.

Trois conséquences, écrites dans `docs/exploitation.md`. **Le dossier `media/` doit
exister** — il l'est, le lot 5 s'y appuie pour les notices. **Le téléversement exige
un compte administrateur** ; le foyer n'en a qu'un, et un 403 s'affiche en français au
lieu de laisser tourner un rond. **Jamais sous `config/www/`** — règle du lot 5, même
force : un ticket porte un numéro de carte tronqué, une heure, un magasin et des
habitudes, et tout ce qui vit dans `www/` est servi sur `/local/` **sans
authentification**.

**La photo n'est pas supprimée toute seule** : elle est la pièce justificative de tout
ce que le modèle en a tiré, et une purge automatique effacerait la preuve le jour où
un chiffre paraît faux. Le nettoyage est un geste du propriétaire ; les réglages
affichent la taille du dossier pour qu'il ne l'oublie pas.

### 10.3 L'invite, la structure et la lecture défensive

`receipt/task.py` construit une invite **en français** décrivant ce qu'est un ticket
de caisse français, ce qu'il faut en extraire et ce qu'il faut ignorer (promotions de
fidélité, points, mode de paiement). Elle donne aussi **les libellés des articles de
la session en cours** : un modèle qui sait qu'il cherche « LT DEMI ECR 1L » parmi
vingt candidats connus se trompe beaucoup moins qu'un modèle qui lit dans le vide.

`structure` fixe la forme : magasin, date, total, devise, et des lignes
`{libellé, quantité, prix unitaire, prix total}`.

**La réponse structurée est validée quand même**, champ par champ, avec les helpers du
composant (`bounded_text`, `finite_float`, `non_negative_float`, `bounded_int`, la
date ISO stricte de `validators.py`). Un schéma contraint la forme, pas la
vraisemblance : rien n'empêche un modèle de rendre 4 000 € ou une date en 1970.

| Contrôle | Seuil |
|---|---|
| Prix unitaire et total d'une ligne | `0 ≤ v ≤ 1 000` € |
| Total du ticket | `0 ≤ v ≤ 3 000` € |
| Quantité d'une ligne | `0 < v ≤ 500` |
| Nombre de lignes | `≤ 200` |
| Date d'achat | dans `[session.started_at − 2 j ; aujourd'hui]` |
| Somme des lignes contre le total lu | écart signalé au-delà de 2 %, **jamais bloquant** |

Une ligne fautive est **écartée seule**, contrairement à la nutrition OFF du lot 1 où
un dépassement refuse toute la fiche. La différence est assumée : une fiche OFF est un
tout cohérent dont une valeur aberrante trahit la table entière ; un ticket est une
suite de lignes indépendantes, et perdre les dix-neuf bonnes parce que la vingtième
est illisible n'aide personne. L'écart au total rend l'omission visible.

### 10.4 Rapprochement, puis application

Chaque `receipt_line` est rapprochée d'une `shopping_line` par `domain/matching.py`,
écrit au lot 1 et étendu ici : similarité de chaîne entre libellé de caisse et libellé
d'article (marque comprise, puis marque retirée), plus une prime de **proximité de
prix** — deux lignes dont les prix unitaires coïncident à 1 % près se rapprochent même
quand les libellés divergent, cas normal des abréviations de caisse. Seuils du lot 1
inchangés : `auto` au-delà de 0,75 avec 0,10 d'avance sur le second, `unmatched`
sinon.

**Appliquer** est une transaction qui fait trois choses et jamais une quatrième :

1. `shopping_line.unit_price` prend le prix du ticket **ramené à l'unité de base** par
   la règle du lot 1 (division par le poids net en `g`/`ml`, aucun diviseur en
   `piece`) ; `price_source` passe à `receipt`.
2. Une observation `price` par ligne corrigée, `source = 'receipt'`, `store_id` de la
   session, `observed_on` la date du ticket. C'est elle qui alimentera le rang 1 de la
   cascade au voyage suivant.
3. Si la ligne est **déjà rangée**, la correction passe par le § 12.4 : le lot existe,
   une partie a peut-être été consommée, et le journal est en ajout seul.

**Ce que l'application ne fait pas** : elle ne crée aucune ligne pour un article du
ticket qu'aucune ligne de panier ne porte. Un article passé en caisse sans avoir été
scanné n'a ni EAN, ni article, ni produit, ni emplacement ; en fabriquer un depuis un
libellé abrégé produirait des doublons de catalogue à chaque voyage — exactement le
ré-appariement par nom qui a créé 35 doublons dans Grocy en avril 2026. Ces lignes
restent `unmatched`, visibles, et le panneau propose de scanner l'article pour les
rattacher. **Le ticket relit des prix ; ce n'est pas une seconde source d'entrée en
stock.**

### 10.5 Rien ne bloque

Contrat du lot 1 pour OFF et du lot 3 pour l'adaptation, appliqué sans changement.

| Situation | Comportement |
|---|---|
| Aucune entité `ai_task` configurée | Pas de bouton « Photographier » ; les réglages disent pourquoi |
| Réseau coupé à la photo | Le téléversement part dans la file hors ligne, comme toute écriture |
| Modèle injoignable, quota épuisé, délai dépassé | `state = 'failed'`, `attempts` incrémenté, `error` en français. La session se clôt, le rangement se fait |
| Réponse illisible ou vide | Idem. La photo reste, `home_stock.read_receipt` réessaie |
| Modèle qui rend n'importe quoi | Les gardes du § 10.3 écartent les lignes fautives ; l'écart au total est affiché |
| Ticket appliqué deux fois | `receipt_line.applied_at` rend la seconde application sans effet |

**Le rangement ne dépend jamais du ticket et le ticket jamais du rangement** : deux
fils parallèles à partir de la caisse. C'est ce qui permet de vider les sacs pendant
que le modèle lit, et de lire le lendemain matin si le réseau du parking était mauvais.

## 11. L'ordre des rayons par magasin

### 11.1 Le magasin

`store` (amendement A4) est la table des enseignes. Le panneau la gère dans les
réglages : renommer, désactiver, et **fusionner** deux magasins qui n'en font qu'un
(« Leclerc » et « E.Leclerc »). La fusion réaffecte `store_id` sur sessions, prix et
ordres de rayons, additionne les `observed_sessions`, et **ne touche pas à
`price.store`** — la chaîne d'origine reste ce qui a été observé.
`home_stock/stores/list` rend en plus l'identifiant et le nombre de sessions
observées ; le panneau garde ses pastilles.

### 11.2 Ce qu'on apprend, et de quoi

La donnée existe déjà et personne ne la lisait : `shopping_line.scanned_at`.
**L'ordre des scans est l'ordre du parcours**, à ceci près qu'on scanne parfois trois
articles du même rayon d'affilée et qu'on revient parfois sur ses pas.

`domain/route.py`, pur et déterministe :

1. Les lignes d'une session sont triées par `scanned_at` et ramenées au rayon de leur
   produit — une suite de rayons, avec répétitions.
2. Chaque rayon reçoit le **rang moyen** de ses apparitions, normalisé sur `[0,1]` par
   le nombre de lignes. Normaliser est indispensable : une session de 8 lignes et une
   de 40 doivent peser pareil.
3. L'ordre du magasin est la **moyenne de ces rangs moyens** sur ses sessions
   retenues ; les rayons non observés gardent `aisle.position`, qui départage aussi
   deux moyennes égales.

**Pourquoi une moyenne de rangs et pas un tri topologique.** Le tri topologique sur
les précédences observées est la solution élégante, et elle meurt sur le premier
cycle. Or les cycles sont la norme : on retourne à la boulangerie en fin de course, on
revient chercher le lait oublié. Un algorithme qui doit alors « casser une arête »
choisit arbitrairement laquelle, donc produit un ordre différent pour deux jeux de
données presque identiques. La moyenne de rangs n'a pas de cas dégénéré, se recalcule
en temps linéaire, s'explique en une phrase au propriétaire (« tu prends le pain vers
la fin ») et se corrige à la main sans surprise.

### 11.3 Trois sessions, et pourquoi trois

L'ordre appris ne remplace le défaut qu'à partir de **trois sessions closes dans ce
magasin**. En dessous, `store_aisle` est rempli et visible dans les réglages, mais
l'affichage utilise `aisle.position`.

Trois est le nombre de la médiane des trois dernières DLC (lot 1) et de la médiane des
trois dernières portions (lot 2). Ce n'est pas une coïncidence esthétique : avec une
observation, un détour exceptionnel devient la loi ; avec deux, rien ne distingue une
habitude d'une coïncidence ; à trois, une valeur aberrante est minoritaire. Le foyer
fait une grande course par semaine — un magasin devient donc fiable en trois semaines,
acceptable pour une information qui ne fait que trier une liste.

Un **rayon** vu dans moins de deux sessions garde sa place par défaut même dans un
magasin fiable : l'animalerie visitée une fois ne doit pas s'installer entre la
crémerie et les fromages.

Les sessions retenues sont les **dix dernières** de ce magasin : un magasin réaménage
ses rayons, et une moyenne sur toute l'histoire mettrait des mois à s'en apercevoir.

### 11.4 Corriger à la main, et rester corrigé

Les réglages offrent, par magasin, la poignée de réordonnancement que le lot 1 avait
posée pour l'ordre global. Déplacer un rayon écrit `store_aisle.source = 'manual'`.

**L'apprentissage ne déplace jamais une ligne `manual`** : c'est la règle
`article.manual_fields` du lot 0, transposée. Le calcul continue de tourner et
`mean_rank` reste visible — on voit donc que l'ordre appris contredit l'ordre épinglé
— mais `position` ne bouge pas. Un bouton « reprendre l'apprentissage » rend la ligne à
l'automatisme.

Le recalcul a lieu **à la clôture d'une session**, pas à chaque scan : on n'apprend pas
d'un parcours en cours.

### 11.5 Où l'ordre est lu

- `repo.list_lines` — le panier. `ORDER BY aisle_position` devient
  `ORDER BY COALESCE(sa.position, ai.position, 999)`, jointure gauche sur
  `store_aisle` filtrée par le `store_id` de la session.
- La liste, dans le panneau et dans `todo.home_stock_shopping` : magasin de la session
  ouverte, à défaut le dernier utilisé, à défaut l'ordre par défaut.
- L'écran de rangement — **non**. Il groupe par emplacement dans la maison, pas par
  rayon de magasin. C'est rappelé ici parce que c'est le genre de cohérence qu'on
  applique par réflexe là où elle n'a pas de sens.

## 12. Corriger un mouvement déjà écrit

C'est le morceau que les lots 2 et 3 ont tous les deux renvoyé ici, et c'est celui
qui touche le plus de choses. Le journal `movement` porte **toute** la comptabilité
kcal et euros du foyer, il est en ajout seul par déclencheur SQLite depuis le lot 0,
et le lot 2 a posé la formule : « une écriture fautive ne s'y corrige pas, elle se
compense par une écriture inverse ».

### 12.1 Ce qu'une contrepassation est, exactement

Un mouvement de correction est un mouvement ordinaire qui :

- porte le **même `reason`** (amendement A1), et les mêmes `product_id`,
  `article_id`, `batch_id`, `base_unit` ;
- porte les **mêmes `parts_total` et `parts_mine`** — recopiées, pas inversées : le
  facteur personnel est un ratio positif, et c'est le signe des valeurs qu'il
  multiplie qui porte l'annulation ;
- porte `quantity`, `cost` et les **neuf nutriments** au signe opposé, valeur pour
  valeur, `NULL` compris — un `NULL` s'annule par un `NULL`, jamais par un zéro
  (règle du lot 2 : zéro veut dire « mesuré à zéro ») ;
- porte `occurred_at` à l'instant de la **correction**, `corrects_id` vers la ligne
  annulée, et une `idempotency_key` dérivée (`correction:<movement_id>`) ;
- **remet le stock** : `batch.remaining` ajusté de `-quantity`, `closed_at` remis à
  `NULL` si le lot redevient non vide.

`domain/correction.py` produit cette ligne, en fonction pure : c'est une règle
d'algèbre, elle se teste sans base ni Home Assistant, et une erreur de signe y est
catastrophique et silencieuse.

**Ce qu'une correction ne compense pas** : le lot créé par un achat, une DLC, une
observation de prix, un repas passé à `done`. Ce sont des états, pas des écritures ;
ils se modifient là où ils vivent.

### 12.2 Ce qui est refusé

| Cas | Comportement |
|---|---|
| Mouvement déjà corrigé | Refusé. L'index unique sur `corrects_id` le garantit même en course |
| Correction d'une correction | Refusé : `corrects_id IS NOT NULL` sur la cible. Corriger la correction, c'est refaire la première écriture — le geste existe déjà, c'est la saisie normale |
| Contrepassation qui rendrait le stock d'un lot supérieur à son `initial` | **Autorisée.** Un lot peut légitimement dépasser son initial après annulation d'une sortie faite avant une conversion d'unité ; refuser bloquerait la correction du seul cas où elle est vraiment utile |
| Contrepassation qui rendrait `remaining` négatif | Refusée, message français disant ce qui reste : le stock a déjà été repris ailleurs, il faut corriger cet ailleurs |
| Lot supprimé ou introuvable | La ligne miroir s'écrit quand même, sans ajuster de stock, et le dit. Le journal doit rester juste même quand le stock ne peut plus l'être |
| Mouvement de motif `transfer` | Refusé : quantité nulle, rien à compenser. Un transfert se corrige par un transfert inverse |
| Mouvement de motif `conversion` ou `cooked` | Refusé au lot 4. Ces motifs viennent par paires transactionnelles (sortie ancienne unité / entrée nouvelle, ingrédients / plat) : les compenser un par un laisserait le stock incohérent. Voir les points différés |

### 12.3 L'effet sur les capteurs, et la rupture assumée

C'est l'amendement A2, redit ici parce que c'est le seul endroit où une correction
est visible depuis l'extérieur du composant.

`kcal_total`, `cost_total` et `cost_waste_total` sont des cumuls, et une
contrepassation les fait **baisser**. Déclarés `TOTAL_INCREASING`, Home Assistant lit
cette baisse comme la remise à zéro d'un compteur d'appareil — comportement documenté
de cette classe — et **ajoute** la nouvelle valeur au cumul au lieu de la soustraire :
une correction de 300 kcal produirait un saut de plusieurs milliers dans les
statistiques long terme. Les trois passent donc en `state_class: TOTAL`, sans
`last_reset` : Home Assistant somme alors les différences successives, et une
différence négative est une donnée valide.

Le prix : les statistiques déjà enregistrées gardent l'ancienne définition, un
`repair` « la classe d'état a changé » s'ouvre, et il faut les supprimer **une fois, à
la main**. Le lot 2 l'a déjà payé sur les deux premiers. Il y a désormais quelques
semaines d'histoire dessus ; le journal SQLite les contient toutes et les graphes du
panneau (lot 2, A1) se recalculent à partir de lui — seules les statistiques natives
redémarrent. **Procédure écrite dans `docs/exploitation.md`, exécutée par le
propriétaire.**

Les onze capteurs `_today` ne changent pas. Une correction d'un mouvement d'hier
s'impute au **jour de la correction**, pas au jour de l'erreur : `occurred_at` est
l'instant de l'écriture. C'est le comportement comptable normal, et c'est ce que le
panneau affiche — la barre d'hier ne bouge pas, celle d'aujourd'hui porte une entrée
négative nommée « Correction ».

### 12.4 Corriger un prix

Le lot 2 avait groupé « la correction de prix déjà différée » avec la correction de
mouvement ; la raison apparaît maintenant : c'est le même mécanisme sur un
sous-ensemble de colonnes. Un prix se corrige en deux moitiés, et il faut les deux.

**En avant.** `batch.price_per_base_unit` est mis à jour — ce n'est pas une écriture
de journal, c'est l'état courant d'un lot au frigo, et toutes ses sorties futures
seront chiffrées juste. Une observation `price` est écrite en parallèle.

**En arrière.** Pour chaque mouvement déjà pris sur ce lot : une contrepassation
(§ 12.1) puis une réécriture au coût corrigé. Deux lignes par mouvement affecté,
`corrects_id` sur la première, **une seule transaction**. Les neuf nutriments sont
inchangés — un prix faux n'a jamais faussé des calories — donc recopiés à l'identique,
compensés puis recompensés : **le solde nutritionnel est nul**, ce qu'un test épingle
explicitement.

**Le cas normal ne produit aucune écriture.** Un ticket lu le soir même corrige des
lots dont rien n'est sorti : la moitié « en arrière » est vide. C'est pour ça que le
ticket se photographie à la caisse et pas la semaine suivante — et le panneau annonce
« 3 mouvements déjà écrits seront corrigés » quand ce n'est pas le cas.

**Le mouvement `purchase` est corrigé comme les autres**, bien que son coût n'entre
dans aucun capteur : il entre dans l'export du journal et dans la valeur du stock, et
le laisser faux parce qu'aucun capteur ne le lit est le raisonnement qui produit une
base à deux vitesses.

### 12.5 Corriger un repas validé

Le lot 3 a écrit qu'une validation de repas n'a « aucune réversibilité » et a renvoyé
la question ici. Un repas validé produit, en une transaction : un mouvement `cooked`
négatif par ingrédient, un lot de plat et son `cooked` positif, puis un
`consumption` pour la part mangée.

Annuler ce bloc revient à contrepasser N+2 mouvements de trois motifs, dont deux
(`cooked`) que le § 12.2 refuse individuellement — précisément parce qu'ils ne
veulent rien dire seuls. **La correction d'un repas est donc une opération de haut
niveau, pas une somme de corrections unitaires** :
`home_stock.correct_meal(meal_id)` contrepasse le bloc **entier**, dans l'ordre
inverse, en une transaction, repasse le repas de `done` à `planned`, et **refuse si le
lot de plat a déjà été entamé** — une part mangée rend le passé non reconstituable. Le
refus dit quoi faire : consommer le reste, ou corriger la seule consommation fautive.
`application.correct_meal()` est le seul appelant autorisé à contrepasser un
`cooked`.

### 12.6 L'ergonomie : deux appuis, depuis le journal

La correction se déclenche là où l'erreur se voit : **l'écran « Journal » du lot 2**,
où chaque ligne porte déjà quantité, kcal et coût. Un appui ouvre le détail,
« Corriger » arme, un second appui confirme. Aucun appui long, aucune popup système.

Le détail dit **ce que la correction va faire, en clair, avant** : « Annule 200 g de
Pâtes — 310 kcal, 0,42 € — et remet 200 g dans le lot du 2026-08-14 ». Une opération
irréversible qui ne s'annonce pas est une opération qu'on déclenche par erreur.

Une ligne corrigée reste visible, barrée, contrepassation juste en dessous. **On ne
cache jamais une erreur du journal** : c'est ce qui permet de comprendre, six mois
plus tard, pourquoi une journée porte une valeur négative.

Le geste existe aussi en service (`home_stock.correct_movement`), pour le vocal du
lot 6 et la reprise en masse du lot 7.

## 13. Le panneau

`Ecran` gagne `'liste'` et `'ticket'`. La barre de navigation expose « Liste » ;
« Ticket » ne s'atteint que depuis la session ou depuis un bandeau de ticket en
attente — comme `recette` et `validation` au lot 3, on y entre par un contexte, pas
par un bouton nu. Le garde-fou du lot 1 sur le rangement en attente s'applique à ces
deux cibles comme aux autres.

| Écran | Ce qu'on y fait |
|---|---|
| **Liste** *(nouveau)* | Les lignes ouvertes, groupées par rayon dans l'ordre du magasin, avec quantité et origine. Cocher en un appui. Ajouter un produit (recherche catalogue) ou un texte libre. Les cochées se replient en bas. Un bandeau « *n* lignes, ≈ 62 € » |
| **Ticket** *(nouveau)* | Photographier ou choisir une image ; l'état de lecture ; les lignes lues face aux lignes de panier, chacune rapprochable en un appui ; l'écart au total ; « Appliquer » en deux appuis, avec le nombre de contrepassations annoncé |
| Panier *(modifié)* | Total « dont estimé », compteur « *n* hors liste », progression « 12 / 17 de la liste » |
| Courses *(modifié)* | Magasin en pastilles réelles (`store`), « emporter la liste », et à la clôture « photographier le ticket » |
| Journal *(modifié)* | Détail d'une ligne, correction en deux appuis, contrepassations affichées sous la ligne barrée (§ 12.6) |
| Réglages *(modifié)* | Ordre des rayons **par magasin**, fusion de magasins, lignes récurrentes, entité `ai_task`, taille du dossier des tickets |

Contraintes de rendu inchangées depuis le lot 1 : 412 × 915 et 1280 × 800, cibles
tactiles ≥ 48 px, contraste ≥ 4,5:1, aucun débordement horizontal, **aucun geste**,
tout au bouton. Les écritures passent par la file hors ligne avec leur clé
d'idempotence — y compris le cochage d'une ligne de liste et le téléversement d'une
photo, qui sont des écritures comme les autres et se font typiquement là où le réseau
est le plus mauvais.

## 14. Surface Home Assistant

### 14.1 Commandes websocket

| Commande | Effet |
|---|---|
| `home_stock/list/items` | La liste ouverte, triée pour le magasin donné ou celui de la session |
| `home_stock/list/add` | Ajoute une ligne `manual` (produit ou texte libre) |
| `home_stock/list/check` · `uncheck` | Coche / décoche (§ 7.5) |
| `home_stock/list/remove` | `removed_at` — la réconciliation le respecte |
| `home_stock/list/refresh` | Force une réconciliation |
| `home_stock/recurring/list` · `save` · `delete` | Les lignes récurrentes |
| `home_stock/stores/list` *(étendue)* | + `id`, `observed_sessions` |
| `home_stock/store/save` · `merge` | Renommer, désactiver, fusionner |
| `home_stock/store/aisles` · `reorder_aisles` | L'ordre appris, et son épinglage |
| `home_stock/receipt/submit` | Enregistre un `media_content_id` et lance la lecture |
| `home_stock/receipt/get` · `retry` · `discard` | État, réessai, abandon |
| `home_stock/receipt/line/match` | Rapproche ou ignore une ligne à la main |
| `home_stock/receipt/apply` | Applique les prix (§ 10.4) |
| `home_stock/movement/correct` | Contrepasse un mouvement (§ 12) |
| `home_stock/meal/correct` | Contrepasse un repas validé (§ 12.5) |
| `home_stock/session/start` *(étendue)* | Accepte `store_id` en plus du nom |
| `home_stock/session/add_line` *(étendue)* | Accepte `price_source`, coche la liste |

### 14.2 Services

| Service | Rôle |
|---|---|
| `home_stock.add_to_shopping_list` | Produit ou texte, quantité, note. La porte du vocal |
| `home_stock.refresh_shopping_list` | Réconciliation à la demande |
| `home_stock.query_shopping_list` | **Service à réponse** (`SupportsResponse.ONLY`), comme `query_stock` : « qu'est-ce qu'il faut acheter ? » sans créer d'entité |
| `home_stock.read_receipt` | Relance la lecture d'un ticket, ou du dernier en échec |
| `home_stock.correct_movement` | La contrepassation, en service |
| `home_stock.correct_meal` | Le bloc entier d'un repas validé |

**Validation aux deux surfaces.** La règle du lot 1, répétée au lot 2, tient sans
exception : *aucune des deux surfaces n'a le droit d'être la plus faible*. Ce que le
websocket refuse, le service le refuse, et réciproquement. Les helpers de
`validators.py` sont partagés ; les nouvelles bornes du lot 4 (quantité de liste,
`every_days`, prix de ticket, identifiant de mouvement) y sont ajoutées **une fois**
et utilisées des deux côtés. Un test épingle la parité, comme
`test_offline_queue_contract.py` épingle celle de la file hors ligne.

### 14.3 Entités

| Entité | Rôle |
|---|---|
| `todo.home_stock_shopping` | La liste, cochable, partout où Home Assistant va (§ 7.4) |
| `sensor.home_stock_shopping_list` | Nombre de lignes ouvertes. Attributs : par origine, par rayon, la liste |
| `sensor.home_stock_list_estimate` | Coût estimé de la liste (EUR). Attribut : `confidence` |
| `sensor.home_stock_receipts_pending` | Tickets en attente ou en échec. Attribut : la dernière erreur |
| `sensor.home_stock_cart_total` *(étendu)* | + `estimated`, `observed`, `unpriced_lines`, `off_list_lines`, `store` |
| `sensor.home_stock_kcal_total`, `cost_total`, `cost_waste_total` *(modifiés)* | `TOTAL_INCREASING` → `TOTAL` (§ 12.3) |

Quatre entités nouvelles pour un lot de cette taille, dont une `todo`. « Aucune
entité par produit » (lot 0 § 8) tient : la liste est **une** entité, pas quarante.

`entity_id` en anglais, noms affichés dans `translations/fr.json` et `en.json`, sans
exception — convention du lot 0 § 14.

### 14.4 Options

`receipt_agent` (§ 10.1) rejoint `expiration_alert_days`, `recipe_agent` et
`recipe_source_key`. Une cinquième option, `shopping_list_horizon_days`, défaut 7,
règle la fenêtre du planning qui alimente les revendications `meal_plan` — c'est
`MEAL_HORIZON_DAYS`, aujourd'hui en dur, qui devient réglable parce que « ce que je
prépare » et « ce pour quoi je fais les courses » ne sont pas forcément la même
durée.

## 15. Erreurs

| Situation | Comportement |
|---|---|
| Réconciliation pendant une session ouverte | Les lignes cochées sont intouchables (§ 7.3, règle 3) |
| Deux origines réclament le même produit | Une ligne, deux revendications, quantité au maximum (§ 7.2) |
| Produit supprimé du catalogue | Ses lignes de liste et ses revendications sont retirées ; ses lignes de ticket passent `unmatched` |
| Aucune session ouverte au moment d'un cochage | Autorisé : on coche une liste chez soi aussi |
| Magasin fusionné pendant une session ouverte | Refusé, message français : on ne déplace pas le sol sous une session |
| Moins de trois sessions dans un magasin | Ordre par défaut, et les réglages le disent (« 2 sessions sur 3 ») |
| Entité `ai_task` disparue depuis le réglage | `receipt.state = 'failed'`, message nommant l'entité manquante |
| Téléversement refusé (403, non-administrateur) | Message français dans le panneau, photo conservée dans la file |
| Correction d'un mouvement déjà corrigé | Refusée par l'index unique, même en course (§ 12.2) |
| Correction rendant `remaining` négatif | Refusée, message disant ce qui reste |
| Rejeu d'une écriture quelconque | La clé d'idempotence la rend sans effet |

## 16. Dette des lots précédents soldée ici

1. **`add_line` écrit une suggestion comme une observation** (amendement A3). Défaut
   réel, présent dans `shopping.py` depuis le lot 1, qui empoisonne le rang 1 de la
   cascade de prix à chaque voyage. Se solde **avant** l'écran « Ticket », qui écrit
   dans la même table.
2. **`sensor.home_stock_missing_ingredients` n'était qu'un compteur**, faute de
   session d'achat (lot 3 § 20). Il en reste un — c'est son rôle — mais son attribut
   alimente désormais une liste réellement cochable.
3. **Rien ne savait corriger le journal** (lots 2 et 3). Voir § 12.
4. **`MEAL_HORIZON_DAYS` en dur** devient une option (§ 14.4).
5. **La vue HTTP pour les images**, prévue au lot 0 et jamais écrite : elle n'est
   **toujours pas** écrite, et le lot 4 confirme qu'elle ne le sera pas ici. Le
   téléversement passe par la vue de Home Assistant (§ 10.2) ; la question des images
   d'articles et de recettes se posera une seule fois, au lot 7.

## 17. Stratégie de test

Suites existantes vertes : **`./scripts/test.sh`** (1 390 tests aujourd'hui),
**`npm test`** (405), **`node outils/verifier-rendu.mjs`** (39 scénarios). Aucune
régression tolérée sur les trois.

**Python pur, sans Home Assistant ni réseau — le gros du lot.**

- `domain/shoppinglist.py` : les trois cas du § 7.2 ; le maximum et non la somme ;
  une revendication sans quantité ; l'hystérésis à 15 % ; une ligne `manual`
  survivant à tout ; un item coché pendant une session ouverte, puis après clôture ;
  la donnée absente qui **maintient** au lieu de fermer.
- `domain/route.py` : un parcours propre ; un parcours avec retour en arrière ; un
  cycle complet (le cas qui tue un tri topologique) ; deux sessions de tailles très
  différentes qui doivent peser pareil ; un rayon vu une seule fois ; une ligne
  `manual` que l'apprentissage ne déplace pas ; moins de trois sessions.
- `domain/correction.py` : les neuf nutriments inversés valeur pour valeur ;
  `NULL` compensé par `NULL` et jamais par `0.0` ; parts recopiées et non inversées ;
  double correction refusée ; correction d'une correction refusée ; `transfer`,
  `conversion` et `cooked` refusés ; solde nutritionnel **nul** sur une correction de
  prix (§ 12.4).
- `receipt/parse.py` : sur des fixtures de réponses de modèle versionnées dans
  `tests/fixtures/receipts/` — un ticket propre, un ticket avec promotions et points
  de fidélité, une ligne à 4 000 €, une quantité nulle, une date en 1970, un total
  qui ne tombe pas juste, une réponse vide, une réponse tronquée. Chaque fois : ce
  qui est écarté, ce qui survit, ce qui est signalé.
- Rapprochement ticket → panier sur les libellés de caisse réels du catalogue.
- Cascade de prix : une source `open_prices` **ne remonte jamais** au rang 1.

**Couche Home Assistant** (conteneur `2026.8.2`) :

- `m006` appliquée à une **copie de la vraie base issue du lot 5**, pas à une base
  vide ; rejouabilité ; création des magasins sans rapprochement approximatif ;
  contiguïté des versions toujours verte.
- `todo.home_stock_shopping` : cocher, créer, supprimer, `uid` périmé sans erreur,
  `MOVE_TODO_ITEM` non déclaré.
- Le ticket avec une **entité `ai_task` double**, injectée : succès, échec, quota,
  réponse hors bornes, entité sans `SUPPORT_ATTACHMENTS` refusée au réglage. **Aucun
  test ne sort sur le réseau** et aucun n'appelle un vrai modèle.
- Pointage : un scan coche, un retrait décoche, un scan hors liste ne fait rien ;
  rejeu sans double cochage.
- Parité websocket / service sur les six services nouveaux.
- Capteurs : `TOTAL` et non `TOTAL_INCREASING` sur les trois cumuls ; attributs du
  panier ; `confidence` de l'estimation.

**Front** : `liste.test.ts` (groupement par rayon, cochage, ajout, repli),
`ticket.test.ts` (états de lecture, rapprochement, application en deux appuis),
`panier.test.ts` étendu (estimé / constaté / hors liste), contrat de la file hors
ligne mis à jour — et il doit **échouer** si une des nouvelles commandes d'écriture
refusait la clé d'idempotence. `outils/verifier-rendu.mjs` : deux scénarios de plus,
aux deux formats, écran attendu réellement atteint → **41**.

**Interdit, règle depuis le lot 1** : rien ne touche l'instance vivante — pas de
redémarrage du conteneur, pas de rechargement de l'intégration, pas de lecture du
jeton, aucune écriture dans `/opt/nivuus/HomeAssistant/config/`. Grocy est en lecture
seule.

## 18. Ce que le lot 4 pose pour la suite

- **Lot 6.** `todo.home_stock_shopping` et `home_stock.query_shopping_list` sont déjà
  les deux surfaces dont le vocal a besoin : « qu'est-ce qu'il faut acheter ? » et
  « ajoute du beurre » ne demanderont pas une ligne de composant. La tablette de la
  cuisine affiche la liste avec la carte `todo-list` native.
- **Lot 7.** L'historique d'achats de Grocy se reprendra en mouvements `purchase`
  avec leurs prix ; `corrects_id` et la contrepassation donnent enfin le moyen de
  réparer une reprise qui se serait trompée, sans repartir d'une base vide.

## 19. Points différés

| Sujet | Lot | Raison |
|---|---|---|
| **Correction unitaire d'un `cooked` ou d'une `conversion`** | ultérieur | Ces motifs viennent par blocs transactionnels. `correct_meal` couvre le seul bloc qui arrive vraiment ; une conversion d'unité fautive se refait par une conversion inverse |
| **Correction d'un repas dont le plat est entamé** | ultérieur | Reconstituer un lot partiellement mangé suppose de savoir qui a mangé quoi. Refusé explicitement, avec le message qui dit quoi faire |
| **Budget mensuel et alerte de dépassement** | ultérieur | `cost_today` et les statistiques existent ; un objectif est une décision du foyer, pas une donnée du garde-manger. Groupé avec les objectifs nutritionnels différés au lot 2 |
| **Création d'un article depuis une ligne de ticket** | — | Un libellé de caisse abrégé est exactement la matière qui a produit 35 doublons dans Grocy. Le ticket relit des prix, il n'alimente pas le catalogue |
| **Purge automatique des photos de tickets** | — | La photo est la pièce justificative de tout ce qui en a été tiré. Effacer la preuve automatiquement est le contraire de ce qu'un journal en ajout seul cherche à garantir |
| **Liste par magasin** | — | Utile si deux courses se préparaient en parallèle ; le foyer en fait une par semaine |
| **Plusieurs personnes qui font les courses ensemble** | — | Une seule session ouverte à la fois, invariant tenu par index depuis le lot 1. Le foyer suit une personne |
| **Contribution de prix vers Open Prices** | — | Demande un compte, ne sert pas la maison. Décision du lot 1, inchangée |
| **Écriture vers Grocy** | jamais | L'import est à sens unique. Décision du lot 0 |

*Validé le 2026-08-21.*
