# home_stock — Lot 1 : scan, enrichissement et entrée en stock

*Conception validée le 2026-08-19. Suite du lot 0 (`2026-08-18-home-stock-lot0-design.md`),
dont ce document reprend les conventions : identifiants et code en anglais, textes affichés
en français, quantités en unité de base, journal en ajout seul.*

## 1. Objectif et livrable

Le lot 0 a prouvé le modèle : 299 produits, 35 codes-barres, un journal qui ne ment pas.
Il se manipule par services Home Assistant, ce qui est inutilisable au quotidien.

Le lot 1 rend l'entrée en stock utilisable **au téléphone, sans clavier** :

> Ranger trente articles au retour des courses sans jamais taper au clavier, et faire une
> session de courses de bout en bout — scanner en rayon, relever les prix, puis ranger.

C'est le critère de recette. Tout ce qui ne sert pas ces deux phrases attend un autre lot.

## 2. Périmètre

**Dans le lot :** le panneau SPA et son build ; le scan par trois voies ; le client Open Food
Facts sur les quatre bases sœurs ; l'appariement article → produit ; les rayons et leur
ordre ; la conversion d'unité assistée ; les prix et leur cascade ; la session de courses
côté serveur ; l'écran de rangement ; les commandes websocket d'écriture ; la migration
`m002` ; deux capteurs de session.

**Hors du lot :** la liste des manques, le ticket de caisse et l'ordre des rayons par magasin
(lot 4) ; la consommation partielle depuis le panneau et la comptabilité par jour (lot 2) ;
les recettes (lot 3) ; les piles et équipements (lot 5) ; les tablettes murales et le vocal
(lot 6) ; la reprise du stock Grocy (lot 7).

## 3. Décisions validées

| Sujet | Décision |
|---|---|
| Mode magasin | Session de courses **côté serveur**, ligne par scan, triée par rayon ; le lot 4 y branchera la liste et le ticket |
| DLC | Boutons de raccourci alimentés par une durée de conservation par produit, affinée sur les saisies passées |
| Unités | Quand OFF donne un poids net plausible, le panneau **propose** la conversion `piece` → `g`/`ml` ; jamais d'office |
| Scan | Scanner natif de l'application HA, sinon `BarcodeDetector`, sinon clavier |
| Prix | Saisie du moment > dernier prix dans ce magasin > Open Prices > dernier prix connu |
| Front | Sources dans `meal/frontend/`, build vers `custom_components/home_stock/panel/` |
| Réseau | Aucun appel réseau en test ; le client OFF est injecté |

## 4. Amendements au spec du lot 0

Trois points du lot 0 changent. Ils sont normatifs.

1. **§5.2 — emplacement du front.** Le lot 0 annonçait `data/tools/home-stock-app/`. Ce chemin
   est hors du dépôt git et hors du paquet HACS : le front n'y serait ni versionné ni
   installable. Les sources vont dans **`meal/frontend/`**, dans le même dépôt que le
   composant.
2. **§6.2 — le journal fige son unité.** `movement` reçoit une colonne `base_unit`. Convertir
   un produit de `piece` en `g` change le sens de toutes ses quantités passées ; le journal
   étant en ajout seul, l'unité doit être figée sur chaque mouvement, comme le sont déjà les
   kcal et le coût.
3. **§10 — les conditionnements sortent du différé.** Le lot 0 les avait repoussés faute de
   poids nets. OFF les fournit : la table `packaging` est enfin alimentée.

## 5. Architecture

```
custom_components/home_stock/
├── off/
│   ├── client.py        # cascade des 4 bases, User-Agent, délais, timeouts
│   ├── mapping.py       # fiche OFF → colonnes article. AUCUN accès réseau, AUCUN hass
│   └── aisles.py        # categories_tags → rayon
├── domain/
│   ├── matching.py      # article → produit : candidats et scores. Pur, déterministe
│   ├── conversion.py    # plan de conversion d'unité. Pur
│   └── pricing.py       # cascade de prix. Pur
├── shopping.py          # cycle de vie de la session de courses
├── storage/migrations/m002_scan.py
├── websocket_api.py     # + commandes d'écriture
├── panel.py             # enregistrement du panneau et du statique
└── panel/               # ARTEFACT DE BUILD — jamais édité à la main

frontend/                # TypeScript, lit, rollup, vitest — même outillage que wallpanel-app
├── src/
│   ├── connexion.ts     # objet hass fourni par HA, websocket, file d'attente hors ligne
│   ├── scan/            # les trois voies de scan
│   ├── ecrans/          # scanner, fiche, panier, rangement, catalogue, réglages
│   └── styles/
└── outils/verifier-rendu.mjs
```

`off/mapping.py`, `domain/matching.py`, `domain/conversion.py` et `domain/pricing.py` ne
connaissent ni `hass` ni le réseau ni SQLite : ce sont des fonctions pures sur des
dictionnaires. C'est là que vivent les règles qui ont fait souffrir Grocy, et c'est là
qu'elles se testent sans démarrer quoi que ce soit.

Le panneau est enregistré dans la barre latérale et reçoit l'objet `hass` : il réutilise la
connexion websocket et l'authentification de Home Assistant. Aucun second jeton.

## 6. Migration `m002`

```sql
ALTER TABLE product ADD COLUMN default_shelf_life_days INTEGER;
ALTER TABLE movement ADD COLUMN base_unit TEXT;

UPDATE movement SET base_unit = (
  SELECT p.base_unit FROM product p WHERE p.id = movement.product_id
) WHERE base_unit IS NULL;

CREATE TABLE shopping_session (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  closed_at TEXT,
  store TEXT,
  state TEXT NOT NULL CHECK (state IN ('shopping','to_store','done'))
);

CREATE TABLE shopping_line (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES shopping_session(id),
  article_id INTEGER NOT NULL REFERENCES article(id),
  quantity REAL NOT NULL,          -- unité de base
  unit_price REAL,                 -- € par unité de base, relevé en rayon
  scanned_at TEXT NOT NULL,
  stored_at TEXT,
  batch_id INTEGER REFERENCES batch(id),
  idempotency_key TEXT UNIQUE
);

CREATE INDEX idx_line_session ON shopping_line(session_id, stored_at);
CREATE UNIQUE INDEX idx_one_open_session ON shopping_session(state) WHERE state = 'shopping';
```

`movement.base_unit` est rempli rétroactivement depuis le produit : c'est correct puisque
aucune conversion n'a encore eu lieu. À partir de `m002`, toute écriture de mouvement
renseigne la colonne, et le déclencheur d'ajout-seul du lot 0 continue d'interdire l'`UPDATE`.

L'index partiel `idx_one_open_session` fait respecter par la base l'invariant « une seule
session de courses ouverte à la fois ».

## 7. Le client Open Food Facts

### 7.1 Cascade

Quatre bases, même API, même code-barres, interrogées dans cet ordre jusqu'à trouver :

| Ordre | Base | `off_source` | Ce qu'elle couvre |
|---|---|---|---|
| 1 | `world.openfoodfacts.org` | `food` | l'alimentaire |
| 2 | `world.openproductsfacts.org` | `products` | éponges, sacs, piles |
| 3 | `world.openbeautyfacts.org` | `beauty` | savon, shampooing, lessive |
| 4 | `world.openpetfoodfacts.org` | `petfood` | les croquettes de Soraya |

`GET https://{base}/api/v2/product/{code}.json?fields=…` — `status: 1` signifie trouvé,
`status: 0` ou HTTP 404 signifie absent et on passe à la base suivante.

**En-tête `User-Agent` obligatoire** : `home_stock/<version> (Home Assistant; maxime@allanic.me)`.
OFF bloque les clients anonymes.

Timeout de 10 s par base, budget total de 20 s pour la cascade : au-delà, on rend ce qu'on a.

**Le débit d'OFF a été mesuré, pas supposé.** En capturant les fixtures le 2026-08-19, un
rythme d'une requête toutes les 1,5 s a déclenché un `HTTP 429` au bout d'une vingtaine
d'appels. Les règles qui en découlent : un scan interactif part immédiatement (c'est un appel
isolé) ; une resynchronisation en masse respecte **8 s entre deux fiches** ; un `429` déclenche
une attente de 45 s et jusqu'à cinq tentatives, après quoi la fiche est laissée pour la fois
suivante plutôt que d'échouer bruyamment.

### 7.2 Champs demandés

`code`, `product_name`, `product_name_fr`, `generic_name`, `generic_name_fr`, `brands`,
`quantity`, `product_quantity`, `product_quantity_unit`, `serving_size`, `serving_quantity`,
`nutriments`, `nutrition_data_per`, `nutrition_data_prepared_per`, `nutriscore_grade`,
`nova_group`, `ecoscore_grade`, `categories_tags`, `labels_tags`, `allergens_tags`,
`traces_tags`, `additives_tags`, `ingredients_text_fr`, `ingredients_text`,
`image_front_url`, `image_nutrition_url`, `image_ingredients_url`, `obsolete`,
`completeness`, `last_modified_t`.

L'objet `product` de la réponse est stocké tel quel dans `article.off_raw`. Ajouter un champ
dans six mois devient une relecture locale, pas trois cents requêtes.

### 7.3 Nutrition : la conversion, et son refus

Toutes les colonnes nutritionnelles sont **par unité de base** (kcal par gramme, grammes de
protéines par gramme). OFF donne des valeurs pour 100 g.

- Base `g` ou `ml` : `valeur_par_unité_de_base = valeur_100g / 100`.
- Base `piece` : `valeur_par_pièce = valeur_100g / 100 × poids_net`. **Sans poids net
  plausible, la nutrition est refusée** — colonnes laissées à `NULL`. Un `NULL` se voit et se
  corrige ; un facteur mille ne se voit pas.

Les champs `*_100g` sont la source. S'ils manquent et que `nutrition_data_per` vaut `serving`,
on reconstruit depuis `*_serving` et `serving_quantity`. Si les deux chemins échouent, la
nutrition est refusée.

**Les valeurs `*_prepared_100g` sont ignorées.** Elles décrivent le produit reconstitué
(soupe, purée) ; on stocke le produit sec.

Gardes de vraisemblance, appliquées avant écriture. Un dépassement refuse **toute** la
nutrition de la fiche, pas seulement le champ fautif :

| Contrôle | Seuil |
|---|---|
| kcal / 100 g | `0 ≤ v ≤ 900` (le corps gras pur plafonne à 884) |
| protéines, glucides, lipides, sucres, fibres, sel / 100 g | `0 ≤ v ≤ 100` |
| protéines + glucides + lipides / 100 g | `≤ 105` (tolérance d'arrondi) |

### 7.4 Poids net : accepté ou rejeté

`product_quantity` avec `product_quantity_unit`, converti en unité de base (`g`, `kg`, `ml`,
`l`, `cl`, `dl`). Rejeté — donc ni poids net, ni proposition de conversion, ni nutrition sur un
produit à la pièce — si la valeur n'est pas un nombre strictement positif, si elle sort de
`[0,5 ; 50 000]`, ou si l'unité contredit l'unité de base du produit — une masse pour un
produit en `ml`, un volume pour un produit en `g`. Un produit en `piece` accepte les deux :
c'est l'unité OFF qui détermine alors la cible d'une éventuelle conversion. OFF est
collaboratif : « 1,kg » a déjà été rencontré.

## 8. Rattacher un article à un produit

Un EAN scanné pour la première fois doit rejoindre un produit du catalogue — ou en créer un.
La fonction est pure et déterministe, donc testable sur tes 299 produits réels.

1. **Code-barres connu** → l'article existe, rien à décider.
2. Sinon, chaque produit actif reçoit un score : similarité de chaîne (`SequenceMatcher`) plus
   une prime de recouvrement de mots, calculée entre le nom du produit et, tour à tour,
   `generic_name_fr`, `product_name_fr`, et `product_name_fr` amputé de la marque. Le meilleur
   des trois l'emporte — c'est ce dernier qui rattache « Bjorg Muesli Raisin Figue » à
   « Muesli ».
   La normalisation reprend celle du lot 0 : minuscules, accents et ligatures repliés
   (« Œufs » doit trouver « oeufs »), ponctuation retirée, pluriel simple ignoré.
3. Les cinq meilleurs candidats sont renvoyés avec leur score. **Le panneau ne présélectionne
   que si le premier dépasse 0,75 et devance le second de plus de 0,10** — une hésitation ne
   se tranche pas toute seule.
4. Créer un produit reste toujours possible : nom pré-rempli depuis `generic_name_fr`, unité
   de base déduite de l'unité OFF (`g`→`g`, `ml`→`ml`, sinon `piece`), rayon déduit des
   `categories_tags`, catégorie laissée vide.

## 9. Rayons

Seize rayons, dans l'ordre d'un parcours de magasin :

Fruits et légumes · Boucherie · Poissonnerie · Charcuterie et traiteur · Crémerie · Fromages ·
Boulangerie · Épicerie salée · Épicerie sucrée · Petit-déjeuner · Boissons · Surgelés ·
Hygiène et beauté · Entretien et maison · Animalerie · Autre.

Tes 21 catégories existantes y sont rattachées une fois pour toutes, par la migration :

| Catégorie | Rayon |
|---|---|
| Viande | Boucherie |
| Poisson | Poissonnerie |
| Légume, Fruit | Fruits et légumes |
| Fromage | Fromages |
| Œufs, Produit laitier | Crémerie |
| Charcuterie | Charcuterie et traiteur |
| Épicerie, Condiment, Épice, Pâtes, Matière grasse | Épicerie salée |
| Boulangerie | Boulangerie |
| Céréale | Petit-déjeuner |
| Boisson | Boissons |
| Surgelé | Surgelés |
| Snack | Épicerie sucrée |
| Ménage, Équipement | Entretien et maison |
| Pharmacie/Parapharmacie | Hygiène et beauté |

Un article scanné dont le produit n'a pas de rayon en hérite un depuis ses `categories_tags`.
OFF les classe du plus général au plus précis : **on parcourt la liste à l'envers et le premier
tag reconnu gagne**. Si aucun ne l'est, le rayon vient de la base d'origine — `beauty` →
Hygiène et beauté, `petfood` → Animalerie, `products` → Entretien et maison, `food` →
Épicerie salée.

L'ordre des rayons se réordonne dans les réglages du panneau. L'ordre **par magasin** et
l'apprentissage du parcours restent au lot 4.

## 10. Conversion d'unité assistée

239 de tes 299 produits sont stockés à la pièce. Tant qu'ils y restent, « j'ai pris 200 g sur
le paquet » est impossible et les kcal d'un paquet sont une devinette.

**Déclenchement.** Le produit est en `piece`, l'article scanné a un poids net plausible, et
l'unité cible (`g` ou `ml`) en découle. Le panneau propose alors : « Pâtes : passer de pièce à
g — 1 paquet = 500 g ». Rien ne se fait sans cet appui.

**Poids de référence.** La conversion est paramétrée par un poids par pièce, pré-rempli avec
celui de l'article scanné. Chaque article converti utilise **son propre** poids net quand il en
a un, et ce poids de référence sinon. L'écran de confirmation le dit en toutes lettres : « les
lots dont le poids est inconnu seront convertis à 500 g par pièce ».

**Ce qui est écrit, dans une seule transaction :**

- `product.base_unit` passe à l'unité cible ; `min_quantity` et `reference_kcal` sont
  recalculés avec le poids de référence, ou mis à `NULL` si le recalcul est impossible ;
- chaque article voit ses valeurs nutritionnelles divisées par son poids (kcal par pièce
  → kcal par gramme), et reçoit un `packaging` « 1 <nom> = N g » marqué achat par défaut ;
- chaque lot ouvert voit `remaining` et `initial` multipliés par le poids de son article ;
- le journal reçoit, par lot, **une sortie dans l'ancienne unité et une entrée dans la
  nouvelle**, motif `conversion`, `base_unit` figée sur chacune. Le motif `conversion`
  rejoint `REASONS` dans `const.py` mais **pas** `COUNTED_REASONS` : rien n'a été consommé ni
  acheté, donc rien n'entre dans les kcal ni dans le coût.

Une conversion se simule avant de s'exécuter (`dry_run`) : le rapport dit combien d'articles,
de lots et de mouvements sont concernés, et lesquels utiliseront le poids de référence.

## 11. Prix

Chaque prix relevé écrit une ligne dans `price`. Rien n'est jamais renvoyé vers Open Prices.

La valeur proposée au scan est la première disponible dans cet ordre :

1. le dernier prix connu de cet article **dans le magasin de la session en cours** ;
2. **Open Prices** — `GET https://prices.openfoodfacts.org/api/v1/prices?product_code=<ean>&order_by=-date&size=5`,
   la plus récente en euros, **ramenée à l'unité de base selon l'unité de suivi du produit**
   (voir ci-dessous). Timeout 5 s, échec silencieux : un prix suggéré n'est pas une donnée
   dont dépend le rangement ;
3. le dernier prix connu, tous magasins confondus ;
4. rien — et c'est le seul moment où le pavé numérique s'ouvre.

**Open Prices donne le prix d'un PAQUET.** Le diviseur qui le ramène à l'unité de base dépend
de `product.base_unit`, jamais de la simple présence d'un poids net :

- `g` / `ml` : prix du paquet **divisé par le poids net** (celui d'Open Prices s'il en porte
  un, sinon celui de l'article). Sans poids utilisable, aucune suggestion — on ne devine pas
  un diviseur ;
- `piece` : **le paquet EST l'unité, aucun diviseur.** Diviser ici transformait 2,50 € de
  yaourts (`net_quantity` 125) en une suggestion de 0,02 € le pot ; accepter cette suggestion
  écrivait un coût 125 fois trop petit dans un journal en ajout seul, où un chiffre faux ne se
  corrige pas, il se compense.

C'est exactement la règle que le panneau applique déjà à son champ de prix
(`frontend/src/ecrans/fiche.ts`) : les deux côtés doivent dire la même chose, sans quoi le
chiffre affiché et le chiffre enregistré divergent.

**Un prix n'est jamais négatif**, sur aucune surface d'écriture — `stock/add`,
`session/add_line`, `session/update_line`, le service `home_stock.add_stock`, et la lecture
d'Open Prices. Zéro reste valide : un article gratuit est une observation réelle.

**Un prix corrigé corrige son observation.** `add_line` inscrit dans `price` le prix relevé en
rayon ; `update_line` en inscrit une nouvelle dès que la valeur change — sans quoi une
suggestion acceptée à 0,004 €/g et corrigée à 0,006 €/g en caisse laissait 0,004 enregistré
contre ce magasin, en tête de la cascade, pour tous les voyages suivants.

Le magasin se choisit parmi ceux déjà utilisés, présentés en pastilles, ou se saisit —
`home_stock/stores/list` les rend (voir 13.1).

## 12. La session de courses

Elle vit côté serveur : l'écran éteint, l'application fermée et le sous-sol sans réseau ne
perdent rien.

**États.** `shopping` en magasin, `to_store` après le passage en caisse, `done` quand toutes
les lignes sont rangées. Une seule session `shopping` à la fois, garanti par index.

**En magasin.** Un scan ajoute une ligne : article, quantité, prix relevé. Le panier s'affiche
trié par rayon dans l'ordre du parcours, avec le total courant. Une ligne se corrige ou se
supprime — supprimer une ligne non rangée n'écrit aucun mouvement, puisque rien n'est encore
entré en stock.

**Au retour.** L'écran « Ranger » liste les lignes en attente, groupées par emplacement
suggéré (`product.default_location_id`). Chaque ligne se range en un appui : emplacement
pré-sélectionné, DLC au bouton. C'est **là**, et pas avant, que le lot est créé et que le
mouvement `purchase` est écrit — clé d'idempotence `shopping_line:<id>`.

**Hors session.** Un scan à la maison sans session ouverte va directement au rangement : lot
créé sur-le-champ. C'est le mode le plus court, celui d'un article rapporté seul. Son rangement
porte une clé d'idempotence **stable**, dérivée de l'identité locale de la ligne : un réessai
après une coupure réseau est la même action, jamais un second lot.

**Abandonner un voyage.** `session/close` clôt la session en cours, quelles que soient ses
lignes non rangées — c'est le seul moyen d'en rouvrir une, l'index partiel refusant une
seconde session `shopping`. Les lignes ainsi abandonnées **ne comptent plus** dans le contrôle
qui interdit une conversion d'unité tant qu'un scan attend son rangement : elles ne pourront
jamais être ni rangées ni supprimées, et bloquaient sinon la conversion de leur produit pour
toujours.

**Durées de conservation.** Les boutons de DLC proposent `product.default_shelf_life_days`
quand il existe, sinon `+3 j / +1 sem / +1 mois / sans DLC`. Chaque saisie met à jour la durée
par défaut du produit avec la **médiane** des trois dernières DLC posées, arrondie au jour :
une saisie aberrante ne déplace pas le défaut.

## 13. Surface Home Assistant

### 13.1 Commandes websocket

Lecture (lot 0, inchangées) : `products/list`, `product/get`, `batches/list`, `movements/list`,
`locations/list`, `aisles/list`, `subscribe`. Le lot 1 ajoute une lecture :
`home_stock/stores/list` — les enseignes déjà utilisées, pour les pastilles de l'écran
« Courses ». (`session/current` porte la même liste, mais répond `null` quand aucune session
n'existe, c'est-à-dire précisément au moment où il faut en choisir une.)

Écriture, ajoutées par le lot 1 :

| Commande | Effet |
|---|---|
| `home_stock/lookup` | Résout un EAN : local, puis cascade OFF. **N'écrit rien.** Rend l'article s'il existe, la fiche OFF sinon, les candidats de rattachement, le prix suggéré et la proposition de poids net |
| `home_stock/article/create` | Crée l'article, son code-barres, son `off_raw` ; rattache à un produit existant ou en crée un |
| `home_stock/article/update` | Corrige un article à la main ; les champs touchés sont inscrits dans `manual_fields` et ne seront plus jamais écrasés par une resynchronisation |
| `home_stock/product/update` | Nom, rayon, catégorie, emplacement par défaut, seuil, durée de conservation |
| `home_stock/product/convert_unit` | Conversion d'unité, avec `dry_run` |
| `home_stock/session/start` · `current` · `add_line` · `update_line` · `remove_line` · `checkout` · `store_line` · `close` | Cycle de vie de la session |
| `home_stock/stock/add` | Rangement direct, hors session |
| `home_stock/aisles/reorder` | Ordre du parcours |
| `home_stock/off/resync` | Rafraîchit un article depuis OFF |

Toute commande qui écrit porte une `idempotency_key` fournie par le panneau. C'est ce qui rend
la file d'attente hors ligne rejouable sans doublon.

### 13.2 Services et entités

Un seul service nouveau : `home_stock.resync_off` — un article, un produit, ou tout le
catalogue, au rythme de 6 s par fiche, en tâche de fond.

Deux capteurs nouveaux, pour Lovelace et pour le vocal du lot 6 :

- `sensor.home_stock_cart_total` — total du panier en cours (€), attributs : magasin, nombre
  de lignes ;
- `sensor.home_stock_to_store` — nombre de lignes achetées et pas encore rangées.

## 14. Le panneau

Sept écrans, un seul geste par action, **aucun appui long** — la contrainte est celle des
tablettes de la maison et elle vaut ici aussi.

| Écran | Ce qu'on y fait |
|---|---|
| Scanner | Le bouton de scan, la dernière fiche lue, la bannière de session si elle est ouverte |
| Fiche | Photo, nom, marque, poids net, Nutri-Score, kcal ; rattachement au produit ; prix ; quantité ; l'action principale suit le mode — « Au panier » ou « Ranger » |
| Panier | Les lignes triées par rayon, le total courant, la correction d'une ligne, le passage en caisse |
| Courses | Ouvrir une session (magasin en pastilles ou saisi) et clore celle en cours, en deux appuis |
| Rangement | Les lignes en attente, groupées par emplacement, DLC au bouton |
| Catalogue | Recherche, liste dense, édition d'un produit — c'est l'écran du PC |
| Réglages | Ordre des rayons, emplacements, resynchronisation OFF |

**Le scan, trois voies, dans cet ordre :**

1. **Le scanner natif de l'application Home Assistant**, par le bus externe
   (`bar_code/scan`, réponses `bar_code/scan_result`, `bar_code/close`, `bar_code/aborted`).
   Vérifié présent dans le frontend 2026.8.2. C'est l'appareil photo du système : mise au
   point, torche, lecture en rafale.
2. **`BarcodeDetector`** sur `getUserMedia` dans un navigateur ordinaire. Exige un contexte
   sécurisé — `home.allanic.me` est en HTTPS.
3. **Le clavier**, avec recherche par nom, quand rien d'autre n'est disponible ou que
   l'étiquette est illisible.

**Hors ligne.** Toute écriture part dans une file en `localStorage` avec sa clé d'idempotence
générée côté client. La file se rejoue dans l'ordre à la reconnexion. Le panneau affiche le
nombre d'actions en attente : on ne découvre pas au retour que dix scans ont disparu.

**Contraintes de rendu**, vérifiées automatiquement comme pour `wallpanel-app` : format
téléphone 412 × 915 (Pixel) et format PC 1280 × 800 ; cibles tactiles ≥ 48 px ; contraste
≥ 4,5:1 ; aucun débordement horizontal. Les seuils diffèrent de `wallpanel-app` (62 px, 5:1)
et c'est délibéré : une tablette murale se touche à bout de bras, un téléphone se tient en
main.

## 15. Erreurs

| Situation | Comportement |
|---|---|
| OFF injoignable | L'article est créé avec ce qu'on a ; `off_synced_at` reste vide ; `resync_off` le complétera |
| EAN absent des quatre bases | Saisie du nom, article créé, `off_source` à `NULL`. Le code-barres est mémorisé : le prochain scan le reconnaîtra |
| Nutrition invraisemblable ou inconvertible | Colonnes nutritionnelles à `NULL`, le reste de la fiche est conservé |
| Poids net aberrant | Poids rejeté, aucune proposition de conversion, nutrition refusée si le produit est à la pièce |
| Réseau perdu en magasin | Les scans s'empilent localement et se rejouent ; la session côté serveur reste la vérité |
| Conversion d'unité interrompue | Transaction unique : elle passe entièrement ou pas du tout |
| Deux sessions ouvertes | Impossible — l'index partiel refuse la seconde |
| Rejeu d'une écriture | La clé d'idempotence la rend sans effet |

## 16. Tests

**En `pytest` pur, sans Home Assistant ni réseau** — c'est le gros du lot.

Les fixtures sont déjà capturées et versionnées dans `tests/fixtures/off/` :

- `catalogue.json` — **34 des 35 codes-barres réels du garde-manger**, tels qu'OFF les rend au
  2026-08-19. Le cache historique `data/tools/grocy-off/cache_off.json` ne servait pas : il a
  été tronqué à la capture et ne contient ni `categories_tags` ni `generic_name_fr`.
  Couverture mesurée sur ces 34 fiches : `nutriscore_grade` 34, `nutriments` 31,
  `categories_tags` 29, `product_quantity` 26, `generic_name_fr` 22, `serving_quantity` 13 ;
- `soeurs.json` — six fiches des trois bases sœurs (dégraissant, crème pour les mains,
  biscuits pour chien), pour que la cascade soit testée sur du vrai ;
- `anomalies.json` — dix fiches écrites à la main pour les cas qu'OFF produit et que le
  catalogue ne contient pas : « 1,kg », poids nul, palette de 80 kg, 5 000 kcal, somme de
  macros à 150 g, valeurs par portion seulement, valeurs « préparé » seulement, absence totale
  de nutrition, volume en centilitres, `categories_tags` purement génériques.

Ces fixtures alimentent : le mapping OFF ; les gardes de vraisemblance ; le rattachement article → produit sur le catalogue réel des 299 produits ;
le classement par rayon ; la cascade de prix ; le plan de conversion d'unité.

**Dans le conteneur Home Assistant** : les commandes websocket, le cycle de vie de la session,
les deux capteurs, le service de resynchronisation, et la migration `m002` appliquée à une
**copie de la vraie base du lot 0** — pas à une base vide.

**Le client OFF est injecté.** Aucun test ne sort sur le réseau ; les doubles rendent les
fixtures. Un test marqué `network` et désactivé par défaut vérifie que le contrat d'OFF n'a
pas bougé.

**Le front** : `vitest` sur la file d'attente, la machine à états de la session et le rendu ;
`verifier-rendu.mjs` sur les deux formats.

## 17. Points différés

| Sujet | Lot | Raison |
|---|---|---|
| Liste des manques, ticket de caisse, ordre des rayons par magasin | 4 | Rien à apprendre tant qu'aucune session réelle n'a été observée |
| Sortie partielle depuis le panneau, compta par jour | 2 | Le lot 1 fait entrer ; le lot 2 fait sortir |
| Contribution de prix vers Open Prices | — | Demande un compte, ne sert pas la maison |
| Matériau d'emballage, tri des déchets | ultérieur | Conservé gratuitement dans `off_raw` |
| Lecture de la DLC par photo | — | Écarté au profit des raccourcis : un appel réseau par article pour une date qui se pose en un appui |

*Validé le 2026-08-19.*
