# home_stock — Lot 2 : consommation et comptabilité par jour

> Spec du lot 2. Le découpage en huit lots est fixé par
> `2026-08-18-home-stock-lot0-design.md` § 3 ; le panneau, la file d'attente
> hors-ligne et l'enrichissement Open Food Facts viennent de
> `2026-08-19-home-stock-lot1-design.md`.

## 1. Objectif et livrable

Déclarer ce qu'on mange en un ou deux appuis, et lire ce que ça fait par jour,
par semaine et par mois — en kilocalories, en nutriments et en euros.

Livrable vérifiable : déclarer un repas depuis le panneau du téléphone, y
compris hors réseau ; retrouver ce repas dans le journal de la journée ; voir la
barre du jour monter, celle de la semaine suivre, et le stock avoir baissé
d'exactement ce qui a été déclaré.

## 2. Périmètre

**Dans le lot :** l'écran de sortie de stock et l'écran de journal dans le
panneau ; les parts (partager un repas) ; le gel des neuf nutriments dans le
journal des mouvements ; la journée alimentaire de 4 h à 4 h ; les capteurs du
jour ; la séparation du consommé et du gaspillé ; l'entité `event` de
péremption et son blueprint ; la portion proposée.

**Hors du lot :** les restes cuisinés comme objet en stock et les recettes
(lot 3) ; la correction d'un mouvement déjà écrit (lot 4, avec la correction de
prix déjà différée) ; les objectifs nutritionnels et leur dépassement ; les
tablettes murales et le vocal (lot 6).

## 3. Décisions validées

| Question | Réponse retenue |
|---|---|
| Sens des kilocalories | **Suivi personnel** : ce que *tu* as mangé, pas ce que la maison a sorti |
| Quantité | **Raccourcis appris** (1 portion / la moitié / tout le reste) + pavé numérique en secours |
| Nutriments comptés | **Les neuf**, dont quatre activés d'office : kcal, protéines, sucres, sel |
| Frontière du jour | **4 h → 4 h** |
| Alertes de péremption | **Entité `event` + blueprint** pour Bleuenn ; le composant ne notifie pas de lui-même |

Conséquence directe du premier choix, posée ici parce qu'elle cadre tout le
reste : **au lot 2, déclarer c'est manger**. Cuisiner 200 g de pâtes pour deux
repas se déclare 100 g aujourd'hui et 100 g demain. Les restes ne deviennent un
objet en stock qu'au lot 3, quand une recette validée produira un plat dont on
consomme les parts une par une. Les parts du lot 2 ne partagent qu'**un même
repas entre plusieurs assiettes**.

## 4. Amendements au spec du lot 0

**A1 — Le livrable du lot 2 change de forme.** Le § 3 du lot 0 promettait des
« graphes HA natifs jour/semaine/mois ». Les statistiques long terme de Home
Assistant découpent toujours à minuit et aucune carte native n'accepte de
décalage : la frontière de 4 h les rend impossibles telles quelles. Les graphes
jour / semaine / mois sont donc **dessinés par le panneau**, calculés sur le
journal SQLite avec le décalage. Effet de bord favorable : ils sont exacts et
survivent à la purge du `recorder`, qui efface l'historique détaillé au bout de
dix jours par défaut. Les compteurs cumulés `total_increasing` restent publiés
et gardent leurs statistiques natives éternelles, découpées à minuit.

**A2 — `sensor.home_stock_kcal_total` change de sens.** Le lot 0 le définissait
sur `COUNTED_REASONS`, donc `consumption + waste + expired` confondus. Il ne
compte plus que `consumption`, pondéré par la part mangée. Le coût du gaspillage
part dans un compteur à lui, `cost_waste_total`. `cost_total` suit le même
partage et ne compte plus que `consumption`, de sorte que `cost_total +
cost_waste_total` redonne exactement ce que `COUNTED_REASONS` totalisait.
`COUNTED_REASONS` reste défini et utilisé là où l'ensemble des sorties fait
sens — l'export du journal, la valeur sortie du stock — mais n'est plus la base
du calcul nutritionnel ni celle des deux compteurs d'euros.

**A3 — Le journal fige neuf nutriments, plus seulement les kcal et le coût.**
Le lot 0 avait prévu `movement.kcal` et `movement.cost`. Les huit macros
rejoignent la table pour la même raison qui a fait figer les kcal : une
resynchronisation Open Food Facts ne doit pas réécrire ce qui a été mangé le
mois dernier.

## 5. Architecture

Aucun module nouveau côté Home Assistant hors des entités : le calcul vit dans
le domaine pur, la lecture dans les dépôts, la surface dans le websocket.

| Fichier | Rôle |
|---|---|
| `domain/foodday.py` | **Nouveau.** Frontières de la journée alimentaire, pur, sans dépendance HA |
| `domain/nutrition.py` | `movement_values()` étendu aux neuf nutriments |
| `storage/migrations/m003_consumption.py` | **Nouveau.** Colonnes et remplissage rétroactif |
| `storage/repositories.py` | Agrégats du jour, séries, portion apprise, étape d'annonce |
| `application.py` | `consume()` / `consume_batch()` acceptent les parts et une clé |
| `sensor.py` | Onze capteurs de plus |
| `event.py` | **Nouveau.** `event.home_stock_expiration` |
| `websocket_api.py` | Trois commandes de plus, une étendue |
| `blueprints/automation/home_stock/dlc_bleuenn.yaml` | **Nouveau.** Livré, jamais installé par le composant |
| `frontend/src/ecrans/consommation.ts` | **Nouveau.** L'écran « manger » |
| `frontend/src/ecrans/journal.ts` | **Nouveau.** Journée et barres |

Le front garde ses identifiants et ses commentaires **en français**, le Python
les siens **en anglais**, comme aux lots 0 et 1.

## 6. Migration `m003`

Aucune manipulation de trigger cette fois : rien n'écrit dans `movement` en
`UPDATE`. Les colonnes ajoutées sont nullables, donc l'historique existant reste
lisible sans être réécrit.

```sql
ALTER TABLE movement ADD COLUMN parts_total INTEGER;
ALTER TABLE movement ADD COLUMN parts_mine INTEGER;
ALTER TABLE movement ADD COLUMN proteins REAL;
ALTER TABLE movement ADD COLUMN carbohydrates REAL;
ALTER TABLE movement ADD COLUMN sugars REAL;
ALTER TABLE movement ADD COLUMN added_sugars REAL;
ALTER TABLE movement ADD COLUMN fat REAL;
ALTER TABLE movement ADD COLUMN saturated_fat REAL;
ALTER TABLE movement ADD COLUMN fiber REAL;
ALTER TABLE movement ADD COLUMN salt REAL;

ALTER TABLE article ADD COLUMN serving_quantity REAL;
ALTER TABLE batch ADD COLUMN expiry_announced_stage TEXT;

CREATE INDEX idx_movement_reason_day ON movement(reason, occurred_at);
```

`m003` expose aussi un hook `apply(conn)` — le mécanisme existe depuis `m002` —
qui **remplit `article.serving_quantity` depuis les fiches Open Food Facts déjà
stockées** dans `article.off_raw`. Le lot 1 stocke la réponse brute ; la portion
y dort déjà, il n'y a aucune raison de la redemander au réseau.

Règles de ce remplissage, identiques à celles de l'ingestion (§ 10) :

- ne rien écrire si le produit n'est pas suivi en `g` ou en `ml` — une portion
  d'un produit à la pièce vaut une pièce, la colonne n'a rien à dire ;
- lire `serving_quantity` avec la même discipline que `off/mapping.py` : le
  champ arrive parfois en chaîne (`"30"`), parfois avec une virgule, parfois
  absurde ;
- refuser hors de `]0 ; 5000]`, et refuser une portion strictement supérieure au
  poids net de l'article quand celui-ci est connu ;
- un `off_raw` illisible ou tronqué laisse `NULL` et ne fait pas échouer la
  migration : la colonne est un confort, pas une donnée dont dépend le stock.

La migration est **rejouable** : la relancer sur une base déjà migrée ne doit
rien changer.

**Mesuré le 2026-08-20 sur la base du foyer : `article.off_raw` est vide sur
les 299 produits.** Le lot 1 n'est pas encore déployé et aucune
resynchronisation Open Food Facts n'a tourné. Le remplissage rétroactif ne
trouvera donc rien le jour de la migration : il sert aux articles déjà
enrichis, et à ceux qui le seront ensuite. `serving_quantity` se remplira au
fil des scans et de la première resynchronisation complète. Aucun test ne doit
dépendre de la base du foyer ; les cas du § 16 se construisent sur des
fixtures.

## 7. Les parts, et la règle des euros

`parts_total` et `parts_mine` ne sont écrites que pour le motif `consumption`.
Ailleurs elles restent `NULL`.

- `NULL` vaut **1 / 1**. Tout l'historique du lot 0, du lot 1 et de l'import
  Grocy se lit donc « entièrement pour moi », qui est la bonne hypothèse.
- Bornes validées aux deux surfaces : `1 ≤ parts_total ≤ 24`, et
  `0 ≤ parts_mine ≤ parts_total`.
- `parts_mine = 0` avec le motif `consumption` est **légitime** : le plat est
  parti du stock, quelqu'un d'autre l'a mangé, ton journal n'en porte rien.
  C'est le cas « j'ai servi mes invités ».
- Le gaspillage sort du calcul personnel **par le filtre de motif**, pas par une
  part à zéro. Rien à rétro-écrire dans un journal qui refuse l'`UPDATE`.

**Facteur personnel** : `COALESCE(parts_mine, 1) / COALESCE(parts_total, 1)`.

**Règle des euros, à ne jamais confondre avec celle des nutriments : l'argent
n'est jamais divisé par les parts.** Le paquet a coûté ce qu'il a coûté, que tu
l'aies mangé seul ou à quatre. Seuls les kilocalories et les huit macros
portent le facteur personnel.

| Grandeur | Motifs comptés | Facteur personnel |
|---|---|---|
| kcal et les huit macros | `consumption` | oui |
| `cost_total`, `cost_today` | `consumption` | non |
| `cost_waste_total` | `waste`, `expired` | non |

## 8. Les neuf nutriments figés

`movement_values()` prend désormais la quantité, le prix unitaire et un
dictionnaire de taux par unité de base, et renvoie le coût plus les neuf
valeurs. Les règles du lot 0 tiennent :

- **jamais d'arrondi** à l'écriture ;
- `NULL` reste distinct de zéro. Un article sans table nutritionnelle produit
  `NULL`, pas `0.0` : un journal alimentaire qui compte un repas inconnu comme
  zéro calorie ment silencieusement, ce qui est pire que d'admettre un trou ;
- les taux viennent de l'article, **en unité de base**, colonnes remplies par le
  lot 1. Seules les kcal ont une roue de secours au niveau produit
  (`KCAL_RATE_SQL` = `COALESCE(a.kcal_per_base_unit, p.reference_kcal)`). Les
  huit macros n'en ont aucune : pas de valeur sur l'article, pas de valeur.

Tout mouvement fige ce qu'il peut, y compris un achat : c'est le filtre de motif
qui décide ensuite ce qui compte. Un `purchase` porte donc des macros qu'aucun
capteur ne somme — c'est voulu, ça coûte huit colonnes déjà présentes et ça
rendra le lot 4 (coût du panier par nutriment) gratuit.

Le capteur `kcal_today` publie en attribut `unvalued_movements` : le nombre de
sorties de la journée dont les kcal sont inconnues. Une journée à 1 800 kcal
dont trois sorties non chiffrées n'est pas la même information qu'une journée à
1 800 kcal complète.

## 9. La journée alimentaire

`domain/foodday.py`, pur, testable sans Home Assistant :

```python
FOOD_DAY_START_HOUR = 4

def food_day_bounds(moment: datetime, tz: ZoneInfo) -> tuple[str, str]:
    """(début, fin) de la journée alimentaire contenant `moment`, en ISO UTC naïf."""

def food_day_of(moment: datetime, tz: ZoneInfo) -> date:
    """La date à laquelle ce moment est imputé."""

def bucket_bounds(granularity, count, now, tz) -> list[tuple[date, str, str]]:
    """Les `count` derniers seaux jour / semaine / mois, bornes en ISO UTC naïf."""
```

`occurred_at` est stocké en **UTC naïf** (`datetime.now(UTC)` sans microsecondes
ni fuseau, décidé au lot 0). Les bornes se calculent donc en local puis se
convertissent, et la comparaison SQL reste une comparaison de chaînes ISO.

Le fuseau vient de `homeassistant.util.dt.DEFAULT_TIME_ZONE`, passé en argument
par la couche HA. Le domaine ne connaît pas `hass`.

**Changements d'heure.** 04:00 n'est ni ambigu ni manquant à Paris : le saut de
printemps va de 02:00 à 03:00, celui d'automne de 03:00 à 02:00. La frontière
existe donc toujours exactement une fois — mais la journée dure 23 h ou 25 h,
et c'est ce que les tests doivent épingler. Attention au décalage d'un jour :
les changements d'heure de 2026 tombent dans les nuits du 28 au 29 mars et du
24 au 25 octobre, donc les journées alimentaires anormales sont celles du
**28 mars** (23 h) et du **24 octobre** (25 h), pas celles des dimanches.

**Où se calculent les seaux.** SQLite ne connaît aucune base de fuseaux
horaires : un `GROUP BY` sur une date locale décalée y serait faux deux jours
par an. Les bornes se calculent donc en Python, et l'agrégation d'une série se
fait sur les lignes rapportées par une seule requête bornée par le premier seau.
Le volume le permet largement — un foyer produit une quinzaine de mouvements par
jour, donc de l'ordre de 5 000 lignes pour douze mois. Les totaux du jour, eux,
restent un agrégat SQL : une seule journée, deux bornes, aucune boucle.

Les capteurs du jour se rafraîchissent sur le tic de 15 minutes du coordinateur
**et** sur un rendez-vous posé à la prochaine frontière de 4 h
(`async_track_point_in_time`), reposé après chaque déclenchement. Sans ce
rendez-vous, une journée sans activité afficherait le total de la veille jusqu'à
sa première sortie de stock.

## 10. La portion proposée

Aucune colonne `default_portion` : la portion se calcule à l'ouverture de la
fiche, dans cet ordre.

1. **La médiane des trois dernières quantités** consommées de ce produit, motif
   `consumption` uniquement — même mécanisme que la durée de conservation
   apprise du lot 1. Il faut au moins trois consommations : en dessous, on ne
   sait pas encore.
2. **`article.serving_quantity`**, la portion d'Open Food Facts, remplie à
   l'ingestion et rétroactivement par `m003` (§ 6).
3. **Rien.** Le bouton « 1 portion » ne s'affiche pas. Il ne propose jamais un
   chiffre inventé.

L'habitude passe avant la fiche : ce que tu manges vraiment vaut mieux que ce
que le fabricant appelle une portion.

`off/ingest.py` remplit `serving_quantity` à la création et à la
resynchronisation d'un article, sous les mêmes bornes qu'au § 6. La fonction de
validation est **partagée** entre l'ingestion et la migration — deux copies
divergeraient, et c'est exactement le genre de divergence qu'on ne voit pas.

## 11. Les entités

Onze capteurs de plus, une entité `event`.

| Clé | Unité | `state_class` | Activé d'office |
|---|---|---|---|
| `kcal_today` | kcal | `TOTAL` + `last_reset` | oui |
| `proteins_today` | g | `TOTAL` + `last_reset` | oui |
| `sugars_today` | g | `TOTAL` + `last_reset` | oui |
| `salt_today` | g | `TOTAL` + `last_reset` | oui |
| `cost_today` | EUR | `TOTAL` + `last_reset` | oui |
| `carbohydrates_today`, `added_sugars_today`, `fat_today`, `saturated_fat_today`, `fiber_today` | g | `TOTAL` + `last_reset` | **non** |
| `cost_waste_total` | EUR | `TOTAL_INCREASING` | oui |

`last_reset` porte le début de la journée alimentaire courante. C'est la
déclaration honnête d'un compteur qui se remet à zéro : Home Assistant sait
alors qu'une chute de 1 800 à 0 n'est pas un débordement de compteur. Son
agrégat natif « par jour » reste découpé à minuit — le panneau est l'autorité
pour la journée de 4 h (§ 4, A1).

Les cinq capteurs éteints existent dans le registre et s'allument d'un clic ;
leur historique long terme ne commence qu'à leur allumage, ce qui est le prix
annoncé.

`sensor.home_stock_kcal_total` et `cost_total` conservent leur `entity_id` et
changent de calcul (§ 4, A2). Le changement est **documenté dans
`docs/exploitation.md`** : un compteur `total_increasing` dont la valeur baisse
est interprété par Home Assistant comme une remise à zéro, et les statistiques
déjà enregistrées gardent l'ancienne définition. C'est une rupture assumée, une
fois, sur un compteur qui n'a encore jamais servi à rien.

Noms affichés dans `translations/fr.json`, `entity_id` en anglais.

## 12. Le panneau

### 12.1 L'écran « manger »

Atteignable depuis le scanner — on rescanne l'emballage — et depuis le
catalogue, pour le fond d'huile dont l'emballage n'est pas sous la main.

L'écran vise le **lot désigné par le FIFO** : le plus ancien lot ouvert du
produit. Il affiche son reste et sa date limite.

- **Quantité** : trois raccourcis, `1 portion` (§ 10), `la moitié` et
  `tout le reste`, calculés sur le reste de **ce lot**. Un pavé numérique
  s'ouvre d'un appui. Une quantité supérieure au lot déborde sur les suivants
  par `consume()`, exactement comme le service HA.
- **Produit à la pièce** : « 1 » est déjà armé. Un appui suffit, et c'est le cas
  de 239 des 299 produits du catalogue.
- **Motif** : `Mangé` / `Jeté` / `Périmé`. Les deux derniers escamotent les
  parts — personne ne mange une poubelle.
- **Parts** : « pour moi » par défaut. Un contrôle discret « je partage » ouvre
  « sur ⟨2⟩ parts, j'en ai mangé ⟨1⟩ ».
- **Séparateur décimal** : la virgule est acceptée partout, comme au lot 1 où
  son absence effaçait silencieusement un seuil de réapprovisionnement.

L'écriture passe par la **file d'attente hors-ligne** du lot 1, clé
d'idempotence comprise. `tests/test_offline_queue_contract.py` dérive la liste
des commandes du source TypeScript : une commande mise en file dont le schéma
refuse la clé fait échouer ce test le jour où elle est écrite.

### 12.2 L'écran « journal »

Les sorties de la journée alimentaire courante — heure, produit, quantité,
kcal, part quand elle n'est pas 1/1 — et le total qui court, avec le nombre de
sorties non chiffrées quand il y en a.

Un sélecteur `jour / semaine / mois` dessine les barres : 14 jours, 12 semaines
ou 12 mois. Toucher une barre ouvre le détail de ce seau. Les barres sont
dessinées en SVG inline, sans dépendance nouvelle.

### 12.3 Navigation

`Ecran` gagne `'consommation'` et `'journal'`. La barre de navigation existante
les expose. Le garde-fou du lot 1 — quitter le rangement avec des lignes en
attente demande une confirmation — reste inchangé et s'applique à ces deux
cibles comme aux autres.

## 13. Alertes de péremption

### 13.1 L'entité `event`

`event.home_stock_expiration`, `event_types = ["approaching", "expired"]`.

- `approaching` : un lot entre dans la fenêtre `expiration_alert_days`.
- `expired` : sa date limite est passée.

`batch.expiry_announced_stage` (`NULL` → `approaching` → `expired`) retient
l'étape atteinte, **en base** : un redémarrage de Home Assistant ne réannonce
pas les mêmes yaourts, là où un ensemble gardé en mémoire les réannoncerait
tous. L'étape ne recule jamais.

Une seule émission par étape et par rafraîchissement, portant la **liste** des
lots concernés (`batches`, `count`). Grouper évite deux problèmes d'un coup :
des horodatages d'état qui se marchent dessus quand plusieurs lots basculent à
la même seconde, et une annonce vocale qui répéterait trois phrases là où une
seule dit « trois choses périment ».

### 13.2 Le blueprint

`blueprints/automation/home_stock/dlc_bleuenn.yaml`, livré dans le dépôt,
**jamais installé par le composant**.

- Entrées : l'heure de l'annonce (défaut 18:00), l'agent conversationnel
  (défaut `conversation.personas_studio_home_manager`).
- Déclencheur : horaire. C'est ce qu'un foyer veut vraiment — « chaque soir,
  dis-moi ce qui périme » — et non une annonce à 3 h du matin au moment où le
  coordinateur constate le basculement. L'entité `event` reste là pour qui veut
  écrire l'automation immédiate.
- Condition : `binary_sensor.home_stock_expirations` est à `on`.
- Action : `conversation.process`, phrase construite depuis l'attribut
  `batches`.

L'installation est **le geste du propriétaire**. Aucune automation existante
n'est touchée, et le composant, qui part sur HACS, ne code pas un assistant
vocal en dur.

## 14. Surface Home Assistant

### 14.1 Commandes websocket

| Commande | Entrée | Sortie |
|---|---|---|
| `home_stock/stock/consume` | `product_id`, `quantity`, `reason?`, `batch_id?`, `parts_total?`, `parts_mine?`, `idempotency_key?` | `{movement_ids}` |
| `home_stock/journal/day` | `date?` — **date de journée alimentaire** au sens du § 9, défaut : la journée courante | `{start, end, entries, totals}` |
| `home_stock/journal/series` | `granularity` (`day`\|`week`\|`month`), `count` | `{buckets}` |
| `home_stock/product/get` | *étendu* | gagne `suggested_portion` et `serving_quantity` |

`product_id` reste obligatoire même quand `batch_id` est fourni, et le lot doit
appartenir à ce produit : la commande refuse le couple incohérent plutôt que de
faire confiance à l'un des deux. Sans `batch_id`, la sortie traverse les lots
par ordre FIFO.

Validation par les helpers partagés de `validators.py` (lot 1). La règle du lot
1 tient : **aucune des deux surfaces n'a le droit d'être la plus faible** — ce
que le websocket refuse, le service le refuse aussi, et réciproquement.

`consume_batch()` gagne une clé d'idempotence : le chemin « ce lot précis »
passe par la même file hors-ligne que le reste, et une file sans clé rejoue.

### 14.2 Services

`home_stock.consume` gagne `parts_total`, `parts_mine` et `batch_id`, avec
leurs sélecteurs et leurs libellés français dans `services.yaml`.

## 15. Erreurs

| Cas | Comportement |
|---|---|
| Stock insuffisant | `InsufficientStock`, message français disant ce qui reste |
| `parts_mine > parts_total` | Refusé aux deux surfaces, avant toute écriture |
| Parts sur un motif autre que `consumption` | Refusé : la donnée n'aurait aucun sens |
| Produit sans lot ouvert | « Plus rien en stock », l'écran ne propose pas de quantité |
| Article sans table nutritionnelle | Le mouvement s'écrit, les nutriments restent `NULL`, la journée le signale |
| `off_raw` illisible en migration | `serving_quantity` reste `NULL`, la migration réussit |
| Rejeu d'une déclaration | La clé d'idempotence rend les mêmes `movement_ids`, aucun double décrément |

## 16. Tests

Suites existantes vertes, plus :

**Python**

- `m003` : colonnes créées, migration rejouable, remplissage de
  `serving_quantity` depuis `off_raw` — valeur propre, chaîne `"30"`, virgule,
  valeur absurde, portion supérieure au poids net, produit à la pièce, `off_raw`
  absent, `off_raw` tronqué.
- `domain/foodday.py` : 03:59 et 04:01 tombent dans deux journées différentes ;
  les deux changements d'heure de 2026 ; les seaux semaine et mois.
- Parts : facteur personnel, `parts_mine = 0`, `NULL` valant 1/1, bornes
  refusées, parts interdites hors `consumption`.
- Comptabilité : le gaspillage **absent** des kcal et présent dans
  `cost_waste_total` ; les euros **non divisés** par les parts.
- Gel : les neuf nutriments écrits à la valeur du moment ; une
  resynchronisation Open Food Facts qui change l'article ne change **aucun**
  mouvement déjà écrit ; `NULL` préservé, jamais transformé en `0.0`.
- Capteurs : les cinq éteints par défaut le sont, `last_reset` porte bien le
  début de la journée alimentaire, `unvalued_movements` compte juste.
- `event` : une émission par étape, aucune réémission après redémarrage
  simulé, l'étape ne recule pas.
- Websocket et services : `batch_id` étranger au `product_id` refusé, rejeu
  d'une clé rendant les mêmes `movement_ids`, série demandée avec une
  granularité inconnue refusée.
- Contrat de la file hors-ligne : liste attendue mise à jour, et le test doit
  **échouer** si `home_stock/stock/consume` refusait la clé.

**Front**

- `consommation.test.ts` : raccourcis, débordement sur le lot suivant, virgule
  décimale, escamotage des parts sur `Jeté`, un seul appui pour un produit à la
  pièce.
- `journal.test.ts` : totaux, seaux, sélection d'une barre.
- `outils/verifier-rendu.mjs` : deux scénarios de plus, en 412×915 et en
  1280×800, et l'écran attendu réellement atteint.

**Interdit :** rien ne touche l'instance vivante. Pas de redémarrage du
conteneur, pas de rechargement de l'intégration, pas de lecture du jeton. La
vérification s'arrête à ce qui s'observe sans déranger la maison — règle posée
au lot 1 après un redémarrage non demandé du Home Assistant du foyer.

## 17. Dette du lot 1 reprise ici

`frontend/src/file-attente.ts` porte un commentaire qui nomme une course
restée ouverte et la reporte explicitement à ce lot : quand le rejeu générique
du panneau démarre avant l'écriture d'un écran, son nettoyage efface le sort
que l'écran attendait, et l'écran croit son action encore en file alors que le
serveur l'a reçue.

La correction est celle que ce commentaire décrit : **un passage de relais par
clé**. `ajouter` rend une promesse que l'entrée de file résout elle-même au
moment où son sort est connu ; `resultatDe` et `viderResultats` disparaissent,
et avec eux la table partagée. Une panne de transport résout `en-attente` sans
vider la file — sans quoi un écran resterait bloqué indéfiniment sur son bouton.

Cette dette se solde **avant** l'écran « manger », qui s'appuie sur ce retour
pour savoir s'il peut se refermer.

## 18. Points différés

- **Corriger un mouvement déjà écrit.** Le journal est append-only ; corriger
  demandera un motif `correction` et une migration. Regroupé avec la correction
  de prix déjà différée au lot 4.
- **Objectifs nutritionnels** et alertes de dépassement.
- **Restes cuisinés** comme objet en stock : lot 3.
- **Portion manuelle** par produit, si la médiane apprise se révèle décevante.
- **Qui d'autre a mangé** : les parts comptent des assiettes, pas des convives
  nommés. Le foyer ne suit qu'une personne.
