# Supprimer un produit ou un article

*Spec de conception — 2026-09-28*

## Le besoin

> « Il faudrait ajouter une méthode delete product et article dans home stock. »

Deux usages, retenus tous les deux : **nettoyer des erreurs** (doublons, fautes
de saisie, fiches créées pour rien) et **retirer un produit qui n'est plus
acheté** mais qui a un historique.

## Les arbitrages du propriétaire (2026-09-28)

| Question | Choix |
|---|---|
| Produit avec historique | **Masqué partout, historique gardé, réversible** ; effacement réel seulement s'il n'a jamais servi |
| Stock encore ouvert | **Refus**, en listant les lots |
| Usages à venir (recettes, repas planifiés, courses…) | **Refus**, en listant les usages |
| Surfaces | **Commandes websocket + services HA** ; pas de bouton dans le panneau |
| Approche | S'appuyer sur `active` (produit, et nouvel `article.active`) |

Approches écartées : une colonne `deleted_at` distincte de `active` (deux
notions de « caché » qui se recouvrent) ; une table corbeille (quatorze
références orphelines).

## Ce qui existe

- `product.active` existe (`m001_initial`), modifiable par `product/update`
  (`vol.In((0, 1))`), mais ne masque presque rien : `repo.list_products`
  (défaut `active_only=True`), les alertes de stock bas (`min_quantity … AND
  p.active = 1`) et une recherche par identifiants (`repositories.py` ~2028).
  **Ne le filtrent pas** : `home_stock/products/list` (appelle
  `active_only=False`), le scan (`home_stock/lookup` →
  `storage/products.py::find_by_barcode`), la reconnaissance d'ingrédients
  (`domain/matching.py::candidates`), les suggestions de courses.
- `article` n'a pas de colonne `active`.
- Références à `product` : `article`, `movement`, `recipe_ingredient`,
  `recipe.leftover_product_id`, `ingredient_alias`, `meal`,
  `shopping_list_item`, `shopping_recurring`, `battery`,
  `equipment_consumable`. Références à `article` : `barcode`, `packaging`,
  `price`, `batch`, `movement`, `shopping_line`, `receipt_line`.
- Le journal des mouvements est **en ajout seul** (spec des lots 3–7) : aucun
  mouvement n'est jamais effacé ni réécrit.
- Dernière migration : `m008_migration`.

## Conception

### 1. Ce qui bloque (refus, rien n'est modifié)

**Produit** — l'un de ces cas suffit :
- un lot **ouvert** (`closed_at IS NULL`) sur l'un de ses articles ;
- un ingrédient d'une recette **active** ;
- un repas **planifié** (`state = 'planned'`) ;
- un élément **ouvert** de la liste de courses ;
- une course récurrente **active** ;
- un consommable d'équipement, ou une pile dont il est la rechange ;
- le « reste » (`leftover_product_id`) d'une recette active.

**Article** : un lot ouvert, ou une ligne d'une session de courses **en
cours**.

Le refus porte le code `delete_blocked` et un message **en français** qui
nomme chaque blocage avec son nombre et, pour les recettes/repas, leurs noms
(tronqués aux trois premiers + « … »). Exemple : « Encore 2 lots en stock
(Frigo) ; utilisé dans 3 recettes : Curry…, Riz…, Tajine ».

### 2. Effacer ou masquer

- **Effacé pour de bon** si l'élément **n'a jamais servi** : aucun lot (même
  clos), aucun mouvement, aucune ligne de ticket ni de courses, aucun repas
  (quel qu'en soit l'état), aucune recette (même inactive), aucune course
  récurrente, aucun équipement ni pile. Partent avec lui, dans la même
  transaction : ses articles, codes-barres, conditionnements, prix et alias
  d'ingrédient.
- **Masqué** (`active = 0`) dans tous les autres cas ; l'historique est
  intact.
- **Masquer un produit masque ses articles** (le filtre joint sur
  `product.active`). Masquer le dernier article actif d'un produit laisse le
  produit en place.
- Supprimer un élément **déjà masqué** répond `hidden`, sans erreur ; un
  identifiant inconnu est refusé comme ailleurs.
- Réponse : `{"outcome": "deleted" | "hidden"}`. Les capteurs sont
  rafraîchis (`coordinator.async_request_refresh()`).

### 3. Ce que « masqué » change

- Masqué : listes par défaut (dont `products/list`, qui passera à
  `active_only` avec une option `include_hidden` pour qui veut tout voir),
  reconnaissance d'ingrédients, suggestions de courses, alertes de stock bas.
- **Exception, le scan** : `lookup` **retrouve** un article masqué et le
  signale (`active: false`, pour l'article et son produit) au lieu de répondre
  « inconnu » — sinon racheter un produit masqué ferait créer un doublon au
  scan. À l'appelant de proposer la restauration.
- **Restaurer** : `product/update` / `article/update` avec `active = 1`.
  Restaurer un article dont le produit est masqué restaure aussi le produit.

### 4. Surfaces

- Websocket : `home_stock/product/delete {product_id}` et
  `home_stock/article/delete {article_id}`, **`@websocket_api.require_admin`**.
- Services : `home_stock.delete_product` et `home_stock.delete_article`,
  `supports_response`, **services d'administration**
  (`homeassistant.helpers.service.async_register_admin_service`). Décrits dans
  `services.yaml` et les traductions ; ajoutés au test de parité
  (`tests/test_surface_parity.py`) et, si la file hors ligne les concerne, à
  son contrat (`tests/test_offline_queue_contract.py`).
- `article/update` accepte `active` (`vol.In((0, 1))`), comme `product/update`.
- Migration `m009` : `ALTER TABLE article ADD COLUMN active INTEGER NOT NULL
  DEFAULT 1`.

## Tests

Décors à deux sujets ; chaque test prouvé capable d'échouer.

- Chaque blocage, un par un : refus `delete_blocked`, **aucune ligne
  modifiée**, le message nomme le blocage.
- Effacé contre masqué : un produit jamais utilisé disparaît avec ses
  dépendances ; un produit ayant un lot clos ou un mouvement est masqué,
  **même nombre de mouvements et même journal** avant/après.
- Masquer un produit masque ses articles ; le scan retrouve l'article masqué
  avec `active: false` ; reconnaissance d'ingrédients, suggestions, alertes et
  liste par défaut l'ignorent.
- Restaurer un article restaure son produit.
- **Un utilisateur non administrateur est refusé**, websocket
  (`hass_read_only_access_token`) comme service.
- Parité services/websocket et contrat de la file hors ligne verts.
- Migration sur une base existante : tous les articles ressortent actifs.

## Livraison

Après la PR du garde-manger (mêmes fichiers). Un agent implémente, ouvre la
PR, fusionne une fois la CI verte (le job `security` de `main` est rouge pour
une raison amont, `cryptography` épinglé par Home Assistant), attend la
release. **La mise en production se fait avec le propriétaire.**
