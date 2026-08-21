# home_stock — Lot 4 : liste de courses, ticket de caisse et correction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une session de courses complète, des deux bouts : partir avec une liste que personne n'a écrite à la main, la parcourir dans l'ordre du magasin où l'on est, cocher en scannant, savoir ce que le chariot coûte avant la caisse, photographier le ticket pour que la maison relise les prix — et, le lendemain, pouvoir corriger une ligne fausse sans réécrire l'histoire.

**Architecture:** Aucune couche nouvelle. Quatre modules de domaine purs (`shoppinglist`, `route`, `correction`, `receipt/parse`) portent les règles ; les dépôts lisent ; `application.py` et `shopping.py` orchestrent ; le websocket et les services exposent. Un seul module qui sort du processus : `receipt/task.py`, qui appelle une entité `ai_task` de la maison — comme `off/client.py` est le seul à parler à Open Food Facts. La contrepassation est une **écriture ordinaire de motif identique** à celle qu'elle annule, plus `movement.corrects_id` : les onze capteurs et les quatre requêtes d'agrégat se corrigent alors sans qu'une seule ligne de SQL bouge.

**Tech Stack:** Python 3.13 / Home Assistant 2026.8.2 / SQLite (WAL, écrivain unique) / `pytest-homeassistant-custom-component` — TypeScript / `lit` / rollup / vitest / playwright-core.

**Spec:** `docs/superpowers/specs/2026-08-21-home-stock-lot4-design.md`

## Global Constraints

Ces règles lient **toutes** les tâches. Elles sont recopiées telles quelles depuis la spec.

- **Nommage.** Code, schéma et identifiants Python **en anglais** ; textes affichés **en français** (`translations/fr.json`, messages d'erreur). Le front garde ses identifiants et ses commentaires **en français**, comme aux lots 0 à 3.
- **`correction` est un lien, jamais un motif** (amendement A1). Une contrepassation porte le **`reason` de la ligne qu'elle annule** et `movement.corrects_id`. `REASONS` ne gagne **aucune** valeur au lot 4. `reason` est le compte comptable que lisent `repo.totals_between`, `repo._PERSONAL_SUMS`, `repo.journal_entries`, `repo.counted_movements` et onze capteurs : un motif `correction` serait invisible des quatre et annulerait le stock sans annuler les kilocalories ni les euros.
- **Un mouvement ne s'annule qu'une fois**, garanti par `CREATE UNIQUE INDEX idx_movement_corrects ON movement(corrects_id) WHERE corrects_id IS NOT NULL` — pas par une lecture préalable.
- **`NULL` reste distinct de `0.0`.** Un `NULL` s'annule par un `NULL`, jamais par un zéro. Les parts (`parts_total`, `parts_mine`) sont **recopiées**, jamais inversées : ce sont des ratios positifs, et c'est le signe des valeurs qu'elles multiplient qui porte l'annulation.
- **`kcal_total`, `cost_total` et `cost_waste_total` passent de `TOTAL_INCREASING` à `TOTAL`**, sans `last_reset` (amendement A2). Les onze capteurs `_today` ne bougent pas. Le composant ne supprime **jamais** de statistiques : la procédure est écrite dans `docs/exploitation.md` et exécutée par le propriétaire.
- **Un prix suggéré n'est pas un prix observé** (amendement A3). `shopping_line.price_source` et `price.source` disent d'où vient la valeur ; `repo.latest_price_in_store` ne considère que les sources **observées** (`manual`, `receipt`, `import`).
- **`Database._lock` n'est pas réentrant.** Imbriquer deux `db.write()` **fige le processus sans lever d'exception ni écrire de trace**. Toute écriture composée passe par les corps déjà extraits — `_consume_within`, `_consume_batch_within`, `_add_stock_within` (lot 3) — et par les nouveaux `_within` de ce lot. **Ne créez aucune variante** de ces trois corps. Tout test qui écrit plusieurs mouvements en une transaction porte `--timeout=60`, pour qu'un blocage sorte en échec plutôt qu'en attente infinie.
- **Aucune table n'est aliasée `b`.** Un test scanne littéralement `custom_components/` à la recherche de `SELECT b.*` (`tests/storage/test_repositories.py`) ; il ne distingue pas les tables. Aliasez `br` pour `receipt`, `sl` pour `shopping_list_item`, `sa` pour `store_aisle` — jamais `b`.
- **Aucune des deux surfaces n'a le droit d'être la plus faible** : ce que le websocket refuse, le service le refuse, et réciproquement. Les bornes nouvelles vivent **une seule fois** dans `validators.py` et sont utilisées des deux côtés.
- **Aucun test ne sort sur le réseau.** L'entité `ai_task` est un **double injecté**, exactement comme le transport OFF l'est déjà. Aucun test n'appelle un vrai modèle, aucun ne lit une clé d'API.
- **Rien ne touche l'instance vivante.** Pas de `docker compose`, pas de rechargement de l'intégration, pas de lecture du jeton dans `.mcp.json`, aucune écriture dans `/opt/nivuus/HomeAssistant/config/` (base comprise). Grocy est en **lecture seule**.
- **`npm run build` est interdit** avant la dernière tâche. `custom_components/home_stock/` est bind-monté dans le conteneur Home Assistant : le bundle construit est servi tel quel. Une seule construction, à la toute fin, quand tout le reste est vert.
- **Commandes de test.** Python : `./scripts/test.sh` depuis la **racine** du dépôt (image Docker alignée sur HA 2026.8.2 — le Python de l'hôte ne peut pas charger le plugin). Front : `npm test` puis `node outils/verifier-rendu.mjs`, **depuis `frontend/`**.
- **État de départ, à ne pas régresser** : 1 390 tests Python, 405 tests front, 39 scénarios de rendu, tout vert.
- **La photo d'un ticket n'est jamais sous `config/www/`** : `www/` est servi sur `/local/` **sans authentification**, et un ticket porte un magasin, une heure et des habitudes. `validators.media_path` refuse déjà `www/` ; le ticket réutilise ce validateur.
- **Le composant n'écrit aucune vue HTTP.** Le téléversement passe par `/api/media_source/local_source/upload`, fourni par Home Assistant.

## Fusion avec le lot 2bis — fichiers à conflit

Le lot 2bis (`docs/superpowers/specs/2026-08-21-home-stock-lot2bis-design.md`) est écrit **en parallèle**, dans un worktree séparé, et prend **`m007`**. Le lot 4 prend **`m006`, `VERSION = 6`**. Sur les fichiers ci-dessous la consigne de fusion est unique et sans exception : **ajouter en fin de liste, ne jamais réordonner** — un tuple réordonné décale silencieusement des valeurs déjà écrites en base, et le dépôt en a déjà fait l'expérience avec `REASONS` au lot 3.

| Fichier | Ce que le lot 4 y ajoute | Consigne de fusion |
|---|---|---|
| `storage/migrations/__init__.py` | `m006_shopping` dans les deux tuples | Ajouter **après** `m005_equipment`, dans l'import et dans `MIGRATIONS`. Si 2bis a déjà posé `m007`, `m006` se place **avant** lui — l'ordre du tuple est l'ordre d'application. |
| `const.py` | Bloc `# --- lot 4` en **fin de fichier** | Ne toucher à aucun tuple existant. `REASONS` et `CONSUME_REASONS` restent **inchangés**. |
| `sensor.py` | 3 classes nouvelles + `state_class` de 3 capteurs + attributs de `CartTotalSensor` | Ajouter les entités **en fin** de la liste `async_add_entities`. Le changement de `state_class` porte sur trois lignes précises ; ne pas le réécrire ailleurs. |
| `binary_sensor.py` | Rien de nouveau ; lecture seule de `shortages` | Si 2bis ajoute une entité, l'ajouter **en fin** de `async_add_entities`. |
| `coordinator.py` | Clés `shopping_list`, `list_estimate`, `receipts` dans `_async_update_data` | Ajouter les clés **en fin** du `dict` rendu ; ne pas déplacer les lectures existantes. |
| `application.py` | Méthodes nouvelles **en fin** de `StockManager` et helpers `_within` | Ne jamais modifier la signature de `_consume_within`, `_consume_batch_within`, `_add_stock_within`. |
| `websocket_api.py` | Commandes nouvelles + import de `websocket_receipts` | Ajouter les fonctions **en fin** de fichier et leurs noms **en fin** du tuple d'`async_register_websocket`. |
| `services.py` / `services.yaml` | 6 services | Enregistrement **en fin** de `async_setup_services` ; entrées **en fin** de `services.yaml`. |
| `validators.py` | Bornes du lot 4 | Fonctions **en fin** de fichier. Ne pas modifier `bounded_text`, `finite_float`, `iso_date`, `media_path`. |
| `messages.py` | Motifs français du lot 4 | **En fin** de `DOMAIN_ERROR_PATTERNS` — le **premier** motif qui correspond gagne, une insertion au milieu change la phrase d'un message plus ancien. |
| `translations/fr.json`, `en.json` | Noms des 4 entités nouvelles | Clés **ajoutées**, aucune clé existante renommée. |
| `frontend/src/panneau.ts` | `'liste'` et `'ticket'` dans `Ecran`, deux imports, deux boutons | Ajouter **en fin** de l'union `Ecran` et **en fin** de la barre de navigation. |
| `frontend/outils/verifier-rendu.mjs` | 2 scénarios (39 → 41) | Ajouter **en fin** de `SCENARIOS`. |
| `docs/exploitation.md` | Sections « Liste de courses », « Ticket », « Corriger une ligne », « Statistiques à supprimer » | Ajouter **en fin** de document. |

---

## Structure des fichiers

**Python — créés**

| Fichier | Responsabilité |
|---|---|
| `custom_components/home_stock/storage/migrations/m006_shopping.py` | Tables `store`, `store_aisle`, `shopping_list_item`, `shopping_list_claim`, `shopping_recurring`, `receipt`, `receipt_line` ; colonnes `movement.corrects_id`, `shopping_session.store_id`, `shopping_line.price_source`, `price.store_id` ; remplissage rétroactif rejouable. |
| `custom_components/home_stock/domain/correction.py` | L'algèbre d'une contrepassation : ce qui change de signe, ce qui se recopie, ce qui se refuse. Pur. |
| `custom_components/home_stock/domain/shoppinglist.py` | Fusion des quatre origines, revendications, réconciliation, hystérésis. Pur. |
| `custom_components/home_stock/domain/route.py` | Rang moyen normalisé, ordre appris d'un magasin, épinglage manuel respecté. Pur, déterministe. |
| `custom_components/home_stock/receipt/__init__.py` | Paquet du ticket. |
| `custom_components/home_stock/receipt/parse.py` | Réponse structurée du modèle → lignes validées, ligne par ligne. Aucun réseau, aucun `hass`. |
| `custom_components/home_stock/receipt/task.py` | Le seul appel à `ai_task.async_generate_data`. Aucun accès SQLite. |
| `custom_components/home_stock/websocket_receipts.py` | Les commandes du ticket, comme `websocket_recipes.py` et `websocket_batteries.py`. |

**Python — modifiés**

| Fichier | Ce qui change |
|---|---|
| `const.py` | Bloc lot 4 : options, sources de prix, bornes du ticket, seuils de parcours, origines de liste |
| `validators.py` | `list_quantity`, `every_days`, `receipt_price`, `receipt_total`, `movement_ref`, `store_name` |
| `messages.py` | Les phrases françaises des refus du lot 4 |
| `domain/pricing.py` | `PriceSuggestion.observed` : une suggestion se distingue d'une observation |
| `domain/matching.py` | `receipt_candidates` : similarité de libellé **plus** prime de proximité de prix |
| `storage/repositories.py` | Dépôts de la liste, des revendications, des récurrences, du magasin, de `store_aisle`, du ticket ; `list_lines` trié par l'ordre du magasin ; `latest_price_in_store` restreint aux sources observées ; `session_totals` enrichi ; `get_movement`, `movements_of_batch` |
| `application.py` | `correct_movement`, `correct_price`, `correct_meal`, `reconcile_shopping_list`, `add_to_shopping_list`, `apply_receipt`, `learn_store_route`, et leurs corps `_within` |
| `shopping.py` | `price_source` à l'écriture, pointage au scan, décochage au retrait, apprentissage du parcours à la clôture, `store_id` |
| `coordinator.py` | Trois clés de plus, réconciliation sur le tic de 15 minutes |
| `sensor.py` | `shopping_list`, `list_estimate`, `receipts_pending` ; `cart_total` enrichi ; trois `state_class` |
| `todo.py` | Une seconde liste : `todo.home_stock_shopping` |
| `websocket_api.py` | Liste, récurrences, magasins, ordre des rayons, corrections ; `session/start` et `session/add_line` étendues |
| `services.py`, `services.yaml` | Six services de plus |
| `config_flow.py` | Options `receipt_agent` et `shopping_list_horizon_days` |
| `translations/fr.json`, `en.json` | Les quatre entités nouvelles |
| `docs/exploitation.md` | Liste, ticket, correction, statistiques à supprimer une fois |

**Front — créés**

| Fichier | Responsabilité |
|---|---|
| `frontend/src/ecrans/liste.ts` | La liste ouverte, groupée par rayon dans l'ordre du magasin. |
| `frontend/src/ecrans/ticket.ts` | Photographier, suivre la lecture, rapprocher, appliquer en deux appuis. |
| `frontend/tests/liste.test.ts` | Groupement, cochage, ajout, repli des cochées. |
| `frontend/tests/ticket.test.ts` | États de lecture, rapprochement, application en deux appuis. |

**Front — modifiés**

| Fichier | Ce qui change |
|---|---|
| `frontend/src/panneau.ts` | `'liste'` et `'ticket'` dans `Ecran`, deux imports, la navigation |
| `frontend/src/ecrans/panier.ts` | « dont estimé », « *n* hors liste », progression « 12 / 17 de la liste » |
| `frontend/src/ecrans/session.ts` | Pastilles de magasins réels (`store.id`), « emporter la liste », « photographier le ticket » |
| `frontend/src/ecrans/journal.ts` | Détail d'une ligne, correction en deux appuis, contrepassation sous la ligne barrée |
| `frontend/src/ecrans/reglages.ts` | Ordre des rayons par magasin, fusion, récurrences, entité `ai_task`, taille du dossier |
| `frontend/outils/verifier-rendu.mjs` | Deux scénarios de plus (39 → 41) |

---

## Task 1: Migration `m006`, contiguïté des `VERSION`, et les constantes du lot

**Files:**
- Create: `custom_components/home_stock/storage/migrations/m006_shopping.py`
- Modify: `custom_components/home_stock/storage/migrations/__init__.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/storage/test_migrations.py`

**Interfaces:**
- Produit : `m006_shopping.VERSION = 6`, `m006_shopping.SQL`, `m006_shopping.apply(conn)`.
- Tables : `store`, `store_aisle`, `shopping_list_item`, `shopping_list_claim`, `shopping_recurring`, `receipt`, `receipt_line`.
- Colonnes : `movement.corrects_id`, `shopping_session.store_id`, `shopping_line.price_source`, `price.store_id`.
- Index : `idx_list_open_product` (UNIQUE partiel), `idx_movement_corrects` (UNIQUE partiel), `idx_list_open`, `idx_receipt_line_receipt`, `idx_store_aisle_order`.
- `const` (bloc lot 4, en fin de fichier) :
  - `CONF_RECEIPT_AGENT = "receipt_agent"`, `CONF_SHOPPING_LIST_HORIZON_DAYS = "shopping_list_horizon_days"`, `DEFAULT_SHOPPING_LIST_HORIZON_DAYS = 7`
  - `LIST_ORIGINS = ("shortage", "meal_plan", "manual", "recurring")`
  - `PRICE_SOURCES = ("manual", "receipt", "import", "open_prices", "last_known", "store")`
  - `OBSERVED_PRICE_SOURCES = ("manual", "receipt", "import")`
  - `SHORTAGE_KEEP_FACTOR = 1.15`
  - `ROUTE_MIN_SESSIONS = 3`, `ROUTE_SESSION_WINDOW = 10`, `ROUTE_MIN_AISLE_SESSIONS = 2`
  - `RECEIPT_STATES = ("pending", "read", "failed", "applied", "discarded")`
  - `MAX_RECEIPT_LINES = 200`, `MAX_RECEIPT_LINE_PRICE = 1000.0`, `MAX_RECEIPT_TOTAL = 3000.0`, `MAX_RECEIPT_LINE_QUANTITY = 500.0`, `RECEIPT_TOTAL_TOLERANCE = 0.02`, `RECEIPT_BACKDATE_DAYS = 2`
  - `MAX_LIST_QUANTITY = 100_000.0`, `MAX_EVERY_DAYS = 365`
  - `RECEIPT_MEDIA_FOLDER = "home_stock/receipts"`

**Pourquoi `m006` et pas `m007`.** L'état réel de `storage/migrations/` est `m001` … `m005` : le lot 5, fusionné avant celui-ci, a pris le premier numéro libre. Le lot 2bis prendra `m007`. Un dépassement de version saute une migration **définitivement** et **sans bruit** (`apply_migrations` ne redescend jamais).

- [x] **Step 1: Écrire les tests de la migration**

Lire d'abord le haut de `tests/storage/test_migrations.py` pour reprendre les helpers déjà présents (`_migrated`, `_migrated_to`) plutôt que d'en écrire d'autres. Ajouter **à la fin** du fichier :

```python
def test_m006_creates_the_seven_tables(tmp_path):
    conn = _migrated(tmp_path)
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"store", "store_aisle", "shopping_list_item", "shopping_list_claim",
            "shopping_recurring", "receipt", "receipt_line"} <= tables


def test_m006_adds_the_four_columns(tmp_path):
    conn = _migrated(tmp_path)
    def columns(table):
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    assert "corrects_id" in columns("movement")
    assert "store_id" in columns("shopping_session")
    assert "price_source" in columns("shopping_line")
    assert "store_id" in columns("price")


def test_m006_keeps_price_store_as_a_free_string(tmp_path):
    """`price` est un journal d'observations : chaque ligne dit ce qui a été
    vu le jour où ça l'a été. `store_id` s'AJOUTE, `store` n'est pas réécrite."""
    assert "store" in {r["name"] for r in _migrated(tmp_path).execute(
        "PRAGMA table_info(price)")}


def test_a_movement_can_only_be_corrected_once(tmp_path):
    """L'index unique partiel, pas une lecture préalable : deux corrections
    concurrentes de la même ligne rembourseraient deux fois."""
    conn = _migrated(tmp_path)
    _seed_one_movement(conn)                       # helper déjà présent (m003)
    conn.execute("INSERT INTO movement (occurred_at, product_id, article_id,"
                 " quantity, reason, base_unit, corrects_id)"
                 " VALUES ('2026-08-21T10:00:00', 1, 1, 200, 'consumption', 'g', 1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO movement (occurred_at, product_id, article_id,"
                     " quantity, reason, base_unit, corrects_id)"
                     " VALUES ('2026-08-21T11:00:00', 1, 1, 200, 'consumption', 'g', 1)")


def test_two_uncorrected_movements_do_not_collide(tmp_path):
    """Le garde-fou du test précédent : l'index est PARTIEL. Sans le
    `WHERE corrects_id IS NOT NULL`, le deuxième mouvement ordinaire du foyer
    serait refusé — panne totale, en silence, à la première consommation."""
    conn = _migrated(tmp_path)
    _seed_one_movement(conn)
    conn.execute("INSERT INTO movement (occurred_at, product_id, article_id,"
                 " quantity, reason, base_unit)"
                 " VALUES ('2026-08-21T11:00:00', 1, 1, -50, 'consumption', 'g')")
    assert conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"] == 3


def test_only_one_open_list_item_per_product(tmp_path):
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Lait', 'ml')")
    conn.execute("INSERT INTO shopping_list_item (product_id, added_at)"
                 " VALUES (1, '2026-08-21T09:00:00')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO shopping_list_item (product_id, added_at)"
                     " VALUES (1, '2026-08-21T09:05:00')")
    # Cochée ou retirée, la ligne sort de l'index : une ligne neuve est possible.
    conn.execute("UPDATE shopping_list_item SET checked_at = '2026-08-21T10:00:00'")
    conn.execute("INSERT INTO shopping_list_item (product_id, added_at)"
                 " VALUES (1, '2026-08-21T10:05:00')")


def test_a_free_text_line_needs_no_product(tmp_path):
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO shopping_list_item (free_text, added_at)"
                 " VALUES ('Piles télécommande salon', '2026-08-21T09:00:00')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO shopping_list_item (added_at)"
                     " VALUES ('2026-08-21T09:00:00')")


def test_a_claim_is_unique_per_origin(tmp_path):
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO shopping_list_item (free_text, added_at)"
                 " VALUES ('Pain', '2026-08-21T09:00:00')")
    for origin in ("shortage", "meal_plan"):
        conn.execute("INSERT INTO shopping_list_claim (item_id, origin, claimed_at)"
                     " VALUES (1, ?, '2026-08-21T09:00:00')", (origin,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO shopping_list_claim (item_id, origin, claimed_at)"
                     " VALUES (1, 'shortage', '2026-08-21T09:10:00')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO shopping_list_claim (item_id, origin, claimed_at)"
                     " VALUES (1, 'envie', '2026-08-21T09:10:00')")


def test_m006_backfills_stores_by_exact_equality_only(tmp_path):
    """Fusionner « Leclerc » et « E.Leclerc » est une DÉCISION, pas une
    migration. Une migration qui devine réunit un jour deux magasins
    réellement différents, sans laisser de trace."""
    conn = _migrated_to(tmp_path, version=5)
    conn.execute("INSERT INTO shopping_session (started_at, state, store)"
                 " VALUES ('2026-08-01T09:00:00', 'done', 'Leclerc')")
    conn.execute("INSERT INTO shopping_session (started_at, state, store)"
                 " VALUES ('2026-08-08T09:00:00', 'done', 'E.Leclerc')")
    conn.execute("INSERT INTO shopping_session (started_at, state, store)"
                 " VALUES ('2026-08-15T09:00:00', 'done', NULL)")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Lait', 'ml')")
    conn.execute("INSERT INTO article (product_id, label) VALUES (1, 'Lait 1 L')")
    conn.execute("INSERT INTO price (article_id, observed_on, price_per_base_unit,"
                 " store, source) VALUES (1, '2026-08-01', 0.001, 'Lidl', 'manual')")
    conn.commit()
    migrations.apply_migrations(conn)

    names = [r["name"] for r in conn.execute("SELECT name FROM store ORDER BY name")]
    assert names == ["E.Leclerc", "Leclerc", "Lidl"]
    rows = dict(conn.execute(
        "SELECT s.store, st.name FROM shopping_session s"
        " LEFT JOIN store st ON st.id = s.store_id").fetchall())
    assert rows == {"Leclerc": "Leclerc", "E.Leclerc": "E.Leclerc", None: None}
    assert conn.execute("SELECT store, store_id FROM price").fetchone()["store"] == "Lidl"


def test_m006_marks_existing_lines_manual(tmp_path):
    """Faux dans le détail, et le choix le moins nuisible : `manual` CONSERVE
    le comportement actuel de la cascade. Marquer `open_prices` rétroactivement
    supposerait de deviner, et effacerait des prix réellement tapés."""
    conn = _migrated_to(tmp_path, version=5)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Lait', 'ml')")
    conn.execute("INSERT INTO article (product_id, label) VALUES (1, 'Lait 1 L')")
    conn.execute("INSERT INTO shopping_session (started_at, state) VALUES ('x', 'done')")
    conn.execute("INSERT INTO shopping_line (session_id, article_id, quantity,"
                 " unit_price) VALUES (1, 1, 1000, 0.001)")
    conn.execute("INSERT INTO shopping_line (session_id, article_id, quantity)"
                 " VALUES (1, 1, 1000)")
    conn.commit()
    migrations.apply_migrations(conn)
    sources = [r["price_source"] for r in conn.execute(
        "SELECT price_source FROM shopping_line ORDER BY id")]
    assert sources == ["manual", "manual"]


def test_m006_creates_no_list_line(tmp_path):
    """Une migration qui sème 40 lignes ferait apparaître au premier
    redémarrage une liste que personne n'a demandée — et la première
    impression d'une liste de courses décide si on s'en sert."""
    conn = _migrated(tmp_path)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM shopping_list_item").fetchone()["n"] == 0


def test_m006_apply_is_replayable(tmp_path):
    from custom_components.home_stock.storage.migrations import m006_shopping
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO shopping_session (started_at, state, store)"
                 " VALUES ('2026-08-01T09:00:00', 'done', 'Leclerc')")
    conn.commit()
    m006_shopping.apply(conn)
    m006_shopping.apply(conn)                # rejouée à la main, deux fois
    assert conn.execute("SELECT COUNT(*) AS n FROM store").fetchone()["n"] == 1


def test_m006_applies_to_a_copy_of_the_real_lot5_database(tmp_path):
    """Sur une COPIE de la vraie base, jamais sur l'originale et jamais sur
    une base vide : une base vide ne prouve rien d'un remplissage rétroactif.
    Sautée si la base n'est pas lisible — un test ne fait pas échouer une
    suite parce qu'une machine n'a pas le garde-manger du foyer."""
    source = Path("/opt/nivuus/HomeAssistant/config/home_stock.db")
    if not source.exists():
        pytest.skip("base réelle absente")
    copy = tmp_path / "copie.db"
    copy.write_bytes(source.read_bytes())
    conn = sqlite3.connect(copy)
    conn.row_factory = sqlite3.Row
    assert migrations.apply_migrations(conn) == 6
    assert migrations.apply_migrations(conn) == 6      # rejouée : sans effet
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q`
Expected: FAIL — `ImportError: cannot import name 'm006_shopping'`

- [x] **Step 3: Écrire `m006_shopping.py`, l'enregistrer, poser les constantes**

Créer `custom_components/home_stock/storage/migrations/m006_shopping.py` avec `VERSION = 6` et le DDL **exact** du § 6.2 de la spec, puis un `apply(conn)` rejouable qui fait les trois choses du § 6.3 :

1. `INSERT OR IGNORE INTO store (name)` depuis les chaînes distinctes non vides de `shopping_session.store` puis `price.store` ; `UPDATE` des deux `store_id` par **égalité exacte** du nom.
2. `UPDATE shopping_line SET price_source = 'manual' WHERE price_source IS NULL`.
3. **Rien** dans `shopping_list_item`.

`apply()` est rejouable de bout en bout : `INSERT OR IGNORE` sur un `name UNIQUE`, `UPDATE … WHERE store_id IS NULL`, `UPDATE … WHERE price_source IS NULL`.

Dans `storage/migrations/__init__.py`, ajouter `m006_shopping` à l'import **et** à `MIGRATIONS`, **après** `m005_equipment`.

Dans `const.py`, ajouter le bloc `# --- lot 4 : liste de courses, ticket, correction` **en fin de fichier**, avec les constantes listées plus haut. **`REASONS` et `CONSUME_REASONS` ne bougent pas** — amendement A1.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q`
Expected: PASS, y compris `test_migration_versions_are_contiguous_from_one` et `test_migration_modules_are_named_after_their_version`, **sans les avoir touchés**.

- [x] **Step 5: Vérifier que le test de contiguïté a des dents**

Passer temporairement `VERSION = 7` dans `m006_shopping.py` (sans renommer le fichier) et relancer : `test_migration_versions_are_contiguous_from_one` **et** `test_migration_modules_are_named_after_their_version` doivent tomber tous les deux. Si un seul tombe, l'autre ne couvre pas ce qu'il prétend. Remettre `VERSION = 6`.

- [x] **Step 6: Suite complète**

Run: `./scripts/test.sh -q`
Expected: 1 390 tests + les nouveaux, tout vert.

- [x] **Step 7: Commit**

```bash
git add custom_components/home_stock/storage/migrations/ custom_components/home_stock/const.py tests/storage/test_migrations.py
git commit -m "feat: m006 brings the list, the receipt, the store and the reversal link"
```

---

## Task 2: `domain/correction.py`, et les trois cumuls en `state_class: TOTAL`

**Files:**
- Create: `custom_components/home_stock/domain/correction.py`
- Modify: `custom_components/home_stock/sensor.py`
- Modify: `docs/exploitation.md`
- Test: `tests/domain/test_correction.py`, `tests/test_entities.py`

**Interfaces:**
- Produit :
  - `class CorrectionError(ValueError)` — un mouvement qui ne se contrepasse pas.
  - `CORRECTABLE_REASONS: tuple[str, ...]` = `REASONS` moins `transfer`, `conversion`, `cooked`.
  - `reversal(movement: Mapping[str, Any], *, moment: str) -> dict[str, Any]` — la ligne miroir, prête pour `repo.insert_movement`.
  - `reprice(movement: Mapping[str, Any], *, price_per_base_unit: float | None, moment: str) -> dict[str, Any]` — la réécriture au coût corrigé (§ 12.4), **nutriments identiques**.
  - `correction_key(movement_id: int) -> str` → `f"correction:{movement_id}"`.
  - `check_correctable(movement, *, allow_cooked: bool = False) -> None`.

**Pourquoi ces deux choses dans la même tâche.** La spec les groupe, et pour une raison : `domain/correction.py` est ce qui fait **baisser** un cumul, et un cumul déclaré `TOTAL_INCREASING` lit une baisse comme la remise à zéro d'un appareil — il **ajoute** alors la nouvelle valeur au lieu de la soustraire. Écrire l'un sans l'autre laisse une bombe amorcée dans les statistiques long terme.

**Pourquoi ce module est pur.** Une erreur de signe y est catastrophique et **silencieuse** : elle ne lève rien, elle fausse une comptabilité. Un test doit pouvoir l'épingler sans base ni Home Assistant.

- [x] **Step 1: Écrire les tests du domaine**

Créer `tests/domain/test_correction.py` :

```python
"""Une écriture de contrepassation porte le COMPTE de l'écriture qu'elle
annule, avec le signe inverse. Règle comptable plus ancienne que ce
composant, et reprise telle quelle (amendement A1) : `reason` reste
identique, `corrects_id` porte le lien, et aucune des quatre requêtes
d'agrégat n'a besoin d'apprendre quoi que ce soit."""
from custom_components.home_stock.const import MACRO_COLUMNS
from custom_components.home_stock.domain.correction import (
    CorrectionError, check_correctable, correction_key, reprice, reversal,
)

import pytest

MOVEMENT = {
    "id": 42, "occurred_at": "2026-08-14T18:00:00", "product_id": 7,
    "article_id": 11, "batch_id": 3, "quantity": -200.0, "reason": "consumption",
    "base_unit": "g", "kcal": 310.0, "cost": 0.42,
    "parts_total": 4, "parts_mine": 1, "corrects_id": None,
    "proteins": 11.0, "carbohydrates": 62.0, "sugars": 2.0, "added_sugars": None,
    "fat": 1.5, "saturated_fat": 0.3, "fiber": 3.0, "salt": 0.01,
}


def test_the_reversal_carries_the_same_reason():
    """Le coeur de l'amendement A1. Un motif `correction` serait invisible de
    totals_between, _PERSONAL_SUMS, journal_entries et counted_movements."""
    assert reversal(MOVEMENT, moment="2026-08-21T09:00:00")["reason"] == "consumption"


def test_the_reversal_copies_the_identifiers():
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert (line["product_id"], line["article_id"], line["batch_id"],
            line["base_unit"]) == (7, 11, 3, "g")
    assert line["corrects_id"] == 42
    assert line["occurred_at"] == "2026-08-21T09:00:00"
    assert line["idempotency_key"] == "correction:42"


def test_the_reversal_flips_quantity_cost_and_the_nine_nutrients():
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert line["quantity"] == 200.0
    assert line["cost"] == -0.42
    assert line["kcal"] == -310.0
    assert line["macros"]["proteins"] == -11.0
    assert line["macros"]["fat"] == -1.5
    assert line["macros"]["salt"] == -0.01
    assert set(line["macros"]) == set(MACRO_COLUMNS)


def test_a_null_nutrient_is_reversed_by_a_null_never_by_a_zero():
    """Zéro veut dire « mesuré à zéro » (règle du lot 2). Compenser un NULL
    par 0.0 inventerait une mesure, et le prouverait faux dans les neuf sommes
    pondérées de _PERSONAL_SUMS."""
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert line["macros"]["added_sugars"] is None
    muet = {**MOVEMENT, "kcal": None, "cost": None}
    autre = reversal(muet, moment="2026-08-21T09:00:00")
    assert autre["kcal"] is None and autre["cost"] is None


def test_the_parts_are_copied_never_inverted():
    """Le facteur personnel est un RATIO positif : c'est le signe des valeurs
    qu'il multiplie qui porte l'annulation. Inverser les parts diviserait des
    calories négatives par un nombre négatif."""
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert (line["parts_total"], line["parts_mine"]) == (4, 1)


def test_reversing_a_positive_movement_gives_a_negative_one():
    achat = {**MOVEMENT, "reason": "purchase", "quantity": 1000.0, "cost": 2.10,
             "parts_total": None, "parts_mine": None}
    line = reversal(achat, moment="2026-08-21T09:00:00")
    assert line["quantity"] == -1000.0 and line["cost"] == -2.10
    assert line["reason"] == "purchase"
    assert line["parts_total"] is None and line["parts_mine"] is None


def test_a_movement_already_corrected_is_refused():
    with pytest.raises(CorrectionError):
        check_correctable({**MOVEMENT, "corrects_id": 41})


def test_transfer_conversion_and_cooked_are_refused():
    """`transfer` : quantité nulle, rien à compenser. `conversion` et `cooked`
    viennent par PAIRES transactionnelles — les compenser un par un laisserait
    le stock incohérent."""
    for reason in ("transfer", "conversion", "cooked"):
        with pytest.raises(CorrectionError):
            check_correctable({**MOVEMENT, "reason": reason})


def test_correct_meal_may_reverse_a_cooked_and_only_it():
    """`application.correct_meal()` est le SEUL appelant autorisé : il
    contrepasse le bloc entier, dans l'ordre inverse, en une transaction."""
    check_correctable({**MOVEMENT, "reason": "cooked"}, allow_cooked=True)
    with pytest.raises(CorrectionError):
        check_correctable({**MOVEMENT, "reason": "conversion"}, allow_cooked=True)


def test_every_correctable_reason_is_a_real_reason():
    from custom_components.home_stock.const import REASONS
    from custom_components.home_stock.domain.correction import CORRECTABLE_REASONS
    assert set(CORRECTABLE_REASONS) < set(REASONS)
    assert "correction" not in REASONS        # amendement A1, épinglé ici


def test_reprice_keeps_the_nutrients_and_moves_only_the_cost():
    """Un prix faux n'a jamais faussé des calories. Le solde nutritionnel de
    la paire contrepassation + réécriture doit être NUL."""
    ligne = reprice(MOVEMENT, price_per_base_unit=0.003, moment="2026-08-21T09:00:00")
    assert ligne["kcal"] == 310.0
    assert ligne["macros"]["proteins"] == 11.0
    assert ligne["quantity"] == -200.0
    assert ligne["cost"] == pytest.approx(0.6)          # 200 g × 0,003 €/g
    assert ligne["reason"] == "consumption"
    assert ligne["corrects_id"] is None                 # ce n'est pas une annulation


def test_the_nutritional_balance_of_a_reprice_pair_is_zero():
    annule = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    refait = reprice(MOVEMENT, price_per_base_unit=0.003, moment="2026-08-21T09:00:00")
    for column in MACRO_COLUMNS:
        gauche, droite = annule["macros"][column], refait["macros"][column]
        if gauche is None:
            assert droite is None
        else:
            assert gauche + droite == pytest.approx(0.0)
    assert annule["kcal"] + refait["kcal"] == pytest.approx(0.0)
    assert annule["quantity"] + refait["quantity"] == pytest.approx(0.0)


def test_a_reprice_without_a_price_writes_a_null_cost():
    ligne = reprice(MOVEMENT, price_per_base_unit=None, moment="2026-08-21T09:00:00")
    assert ligne["cost"] is None


def test_correction_key_is_derived_and_stable():
    assert correction_key(42) == "correction:42"
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_correction.py -q`
Expected: FAIL — `ModuleNotFoundError: custom_components.home_stock.domain.correction`

- [x] **Step 3: Écrire les tests des trois `state_class`**

Dans `tests/test_entities.py`, à la fin :

```python
async def test_the_three_cumulative_counters_are_total_not_total_increasing(hass, ...):
    """Une correction les fait BAISSER. Déclarés TOTAL_INCREASING, Home
    Assistant lit cette baisse comme la remise à zéro d'un compteur
    d'appareil et AJOUTE la nouvelle valeur : une correction de 300 kcal
    produirait un saut de plusieurs milliers dans les statistiques."""
    for entity_id in ("sensor.home_stock_kcal_total",
                      "sensor.home_stock_cost_total",
                      "sensor.home_stock_cost_waste_total"):
        state = hass.states.get(entity_id)
        assert state.attributes["state_class"] == "total"
        # Sans last_reset : HA somme alors les DIFFÉRENCES successives, et
        # une différence négative est une donnée valide.
        assert "last_reset" not in state.attributes


async def test_the_eleven_daily_sensors_do_not_move(hass, ...):
    """Le garde-fou : seuls trois capteurs changent de classe. Les `_today`
    étaient déjà TOTAL et le restent."""
    state = hass.states.get("sensor.home_stock_kcal_today")
    assert state.attributes["state_class"] == "total"
```

- [x] **Step 4: Écrire le module et changer les trois lignes**

Créer `custom_components/home_stock/domain/correction.py` : pur, aucun `hass`, aucun SQLite, docstring rappelant que `reason` est le **compte comptable** et pourquoi un motif `correction` casserait les quatre requêtes qui le lisent. `reversal()` construit un `dict` aux clés de `repo.insert_movement` (`macros` étant un sous-`dict` couvrant **tout** `MACRO_COLUMNS`, `None` compris). `_flip(value)` rend `None` pour `None` et `-value` sinon — une seule fonction, utilisée pour les onze valeurs signées.

Dans `sensor.py`, remplacer `SensorStateClass.TOTAL_INCREASING` par `SensorStateClass.TOTAL` sur `KcalTotalSensor`, `CostTotalSensor` et `CostWasteTotalSensor`, avec le commentaire qui dit pourquoi (une baisse est légitime depuis le lot 4). **Ne rien changer d'autre** dans ce fichier à ce stade.

Dans `docs/exploitation.md`, ajouter **en fin** une section « Statistiques à supprimer une fois » : Home Assistant ouvrira un `repair` « la classe d'état a changé » sur ces trois entités ; la résolution est **un geste du propriétaire** (Outils de développement → Statistiques → supprimer les statistiques de `sensor.home_stock_kcal_total`, `cost_total`, `cost_waste_total`). Rappeler que le journal SQLite contient toute l'histoire et que les graphes du panneau se recalculent depuis lui : seules les statistiques natives repartent.

- [x] **Step 5: Lancer les tests, vérifier qu'ils passent**

```bash
./scripts/test.sh tests/domain/test_correction.py tests/test_entities.py -q
```
Expected: PASS

- [x] **Step 6: Vérifier que les tests ont des dents (mutation)**

Dans `_flip`, remplacer `return None if value is None else -value` par `return 0.0 if value is None else -value`. `test_a_null_nutrient_is_reversed_by_a_null_never_by_a_zero` doit tomber. Puis inverser les parts (`-parts_total`) : `test_the_parts_are_copied_never_inverted` doit tomber. Remettre le code correct.

- [x] **Step 7: Commit**

```bash
git add custom_components/home_stock/domain/correction.py custom_components/home_stock/sensor.py docs/exploitation.md tests/domain/test_correction.py tests/test_entities.py
git commit -m "feat: a reversal carries the reason it cancels, and three counters become TOTAL"
```

---

## Task 3: Le dépôt de la correction et `application.correct_movement()`

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/messages.py`
- Test: `tests/storage/test_repositories_journal.py`, `tests/test_application_correction.py` *(nouveau)*, `tests/test_messages.py`

**Interfaces:**
- Dépôts : `get_movement(conn, movement_id)`, `movements_of_batch(conn, batch_id)` (ordre `id`), `correction_of(conn, movement_id)`.
- `StockManager.correct_movement(movement_id: int) -> dict[str, Any]` → `{"movement_id", "correction_id", "batch_id", "restored"}`.
- `StockManager._correct_movement_within(conn, movement, *, moment, allow_cooked=False) -> int` — le corps, sur une connexion que l'appelant possède déjà.
- `StockManager.preview_correction(movement_id) -> dict[str, Any]` — ce que la correction fera, **avant** : produit, quantité, kcal, coût, lot visé. Alimente le § 12.6 (« Annule 200 g de Pâtes — 310 kcal, 0,42 € — et remet 200 g dans le lot du 2026-08-14 »).

**Le piège à ne pas redécouvrir.** `Database._lock` n'est pas réentrant. `_correct_movement_within` existe **pour ça** : `correct_price` et `correct_meal` (tâche 4) écrivent plusieurs corrections dans une seule transaction. `correct_movement` public ouvre le `db.write()`, appelle le corps, et rien d'autre. Ne créez aucune variante de `_consume_within`, `_consume_batch_within` ou `_add_stock_within` : ce lot les réutilise telles quelles.

- [x] **Step 1: Écrire les tests**

Créer `tests/test_application_correction.py`. Ce que chacun prouve :

```python
def test_correcting_a_consumption_gives_the_stock_back(manager):
    """Le journal gagne une ligne, le lot retrouve sa quantité, et
    `closed_at` repasse à NULL si le lot redevient non vide."""

def test_the_correction_is_a_second_row_never_an_update(manager):
    """`movement` est en ajout seul par déclencheur depuis le lot 0 : le test
    compte deux lignes et vérifie que la première est intacte."""

def test_the_daily_totals_absorb_the_correction_without_a_single_query_change(manager):
    """LA preuve de l'amendement A1 : après correction, `totals_between` sur
    la journée de la correction rend -310 kcal et -0,42 €, SANS que
    _PERSONAL_SUMS, journal_entries ou counted_movements aient été touchés."""

def test_the_correction_is_booked_on_the_day_it_is_made(manager):
    """`occurred_at` est l'instant de l'ÉCRITURE. La barre d'hier ne bouge
    pas ; celle d'aujourd'hui porte une entrée négative."""

def test_a_movement_cannot_be_corrected_twice(manager):
    """Refus, et refus porté par l'index unique — pas seulement par la
    lecture préalable : le test provoque l'IntegrityError et vérifie qu'elle
    ressort en message français, pas en trace."""

def test_correcting_a_correction_is_refused(manager):
    """`corrects_id IS NOT NULL` sur la cible. Corriger la correction, c'est
    refaire la première écriture : le geste existe déjà, c'est la saisie."""

def test_a_reversal_that_would_make_remaining_negative_is_refused(manager):
    """Le stock a déjà été repris ailleurs. Le message dit ce qui reste."""

def test_a_reversal_may_push_a_batch_above_its_initial_quantity(manager):
    """AUTORISÉE, explicitement : un lot peut légitimement dépasser son
    initial après annulation d'une sortie faite avant une conversion d'unité.
    Refuser bloquerait le seul cas où la correction est vraiment utile."""

def test_a_missing_batch_still_gets_its_journal_line(manager):
    """Le journal doit rester juste même quand le stock ne peut plus l'être :
    la ligne miroir s'écrit, aucun stock n'est ajusté, et le résultat le dit
    (`restored is False`)."""

def test_a_transfer_a_conversion_and_a_cooked_are_refused(manager):
    """Trois motifs, trois refus, trois messages français distincts."""

def test_a_purchase_is_corrected_like_any_other(manager):
    """Son coût n'entre dans aucun capteur — et il entre dans l'export du
    journal et dans la valeur du stock. Le laisser faux « parce qu'aucun
    capteur ne le lit » est le raisonnement qui produit une base à deux
    vitesses."""

def test_replaying_the_same_correction_returns_the_first_one(manager):
    """`idempotency_key = correction:<id>` : la file hors ligne rejoue."""

def test_preview_says_what_will_happen_before_it_happens(manager):
    """Nom du produit, quantité, kcal, coût, date du lot visé. Une opération
    irréversible qui ne s'annonce pas est une opération qu'on déclenche par
    erreur."""
```

Dans `tests/test_messages.py`, ajouter les six phrases françaises nouvelles et **rejouer les messages des lots antérieurs** pour prouver qu'aucun motif nouveau n'en masque un ancien (le premier motif qui correspond gagne).

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_application_correction.py -q --timeout=60`
Expected: FAIL — `AttributeError: 'StockManager' object has no attribute 'correct_movement'`

- [x] **Step 3: Écrire les dépôts, le corps et la méthode publique**

Dans `repositories.py` : `get_movement` (`SELECT * FROM movement WHERE id = ?`, alias **`m`**, jamais `b`), `movements_of_batch`, `correction_of`.

Dans `application.py`, **en fin** de `StockManager` :

```python
def _correct_movement_within(self, conn, movement, *, moment,
                             allow_cooked: bool = False) -> int:
    """Le corps d'une contrepassation, sur une connexion déjà tenue.

    Extrait pour `correct_price` et `correct_meal`, qui en écrivent
    plusieurs dans UNE transaction. `Database._lock` n'est pas réentrant :
    appeler `correct_movement` depuis l'intérieur d'un `db.write()` fige le
    processus, sans exception et sans trace.
    """
```

Il : appelle `check_correctable`, construit la ligne par `reversal()`, l'insère par `repo.insert_movement(..., corrects_id=...)`, puis ajuste `batch.remaining` de `-quantity` — `closed_at` remis à `NULL` si le lot redevient non vide, refus si `remaining` deviendrait négatif, **aucun ajustement** si le lot est introuvable.

`correct_movement()` public : lecture hors verrou, `db.write()`, `_correct_movement_within`, `repo.get_movement` du résultat. L'`sqlite3.IntegrityError` de l'index unique est **laissée remonter** : elle est traduite en français par la surface, et c'est elle qui tient la course.

Dans `messages.py`, **en fin** de `DOMAIN_ERROR_PATTERNS`, les motifs des refus.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_application_correction.py tests/test_messages.py tests/storage -q --timeout=60`
Expected: PASS

- [x] **Step 5: Vérifier l'absence de verrou imbriqué**

Écrire volontairement une version de `correct_movement` qui appelle `self.consume_batch(...)` depuis l'intérieur de son `db.write()`, relancer avec `--timeout=60` : le test doit sortir en **timeout**, pas en attente infinie. C'est la preuve que le garde-fou de temps est en place. Remettre le code correct.

- [x] **Step 6: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py custom_components/home_stock/application.py custom_components/home_stock/messages.py tests/
git commit -m "feat: correct_movement writes the mirror row and gives the stock back"
```

---

## Task 4: Corriger un prix, corriger un repas

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/messages.py`
- Test: `tests/test_application_correction.py`, `tests/test_meal_validate.py`

**Interfaces:**
- `StockManager.correct_price(batch_id: int, *, price_per_base_unit: float | None, observed_on: str | None = None, store_id: int | None = None) -> dict[str, Any]` → `{"batch_id", "corrected_movements", "price_id"}`.
- `StockManager._correct_price_within(conn, batch, *, price_per_base_unit, moment, store_id)`.
- `StockManager.correct_meal(meal_id: int) -> dict[str, Any]` → `{"meal_id", "reversed_movements", "state": "planned"}`.
- `StockManager.preview_price_correction(batch_id, *, price_per_base_unit) -> dict[str, Any]` — « 3 mouvements déjà écrits seront corrigés », ou zéro.

**Deux moitiés, et il faut les deux (§ 12.4).** *En avant* : `batch.price_per_base_unit` mis à jour — ce n'est pas une écriture de journal, c'est l'état courant d'un lot au frigo — plus une observation `price`. *En arrière* : pour chaque mouvement déjà pris sur ce lot, une contrepassation **puis** une réécriture au coût corrigé. Deux lignes par mouvement, `corrects_id` sur la première, **une seule transaction**.

**Le cas normal ne produit aucune écriture arrière** : un ticket lu le soir même corrige des lots dont rien n'est sorti.

- [x] **Step 1: Écrire les tests**

```python
def test_correcting_a_price_updates_the_batch_and_records_an_observation(manager):
    """La moitié « en avant » : toutes les sorties FUTURES seront chiffrées
    juste, sans rien réécrire."""

def test_the_normal_case_writes_no_journal_line_at_all(manager):
    """Un lot dont rien n'est sorti : `corrected_movements == 0`. C'est pour
    ça que le ticket se photographie à la caisse et pas la semaine d'après."""

def test_each_affected_movement_gets_a_reversal_then_a_rewrite(manager):
    """Deux lignes par mouvement, dans cet ordre, `corrects_id` sur la
    première seulement, toutes dans la même transaction."""

def test_the_nutritional_balance_of_a_price_correction_is_zero(manager):
    """Épinglé explicitement (§ 12.4) : un prix faux n'a jamais faussé des
    calories. Sur les neuf nutriments, somme des trois lignes == valeur de
    l'originale, au flottant près."""

def test_only_the_cost_moves(manager):
    """`cost_today` bouge de la différence exacte ; `kcal_today` ne bouge pas
    d'un iota."""

def test_the_purchase_movement_is_corrected_too(manager):
    """Il entre dans l'export du journal et dans la valeur du stock."""

def test_correcting_a_price_twice_is_refused_on_the_already_corrected_rows(manager):
    """L'index unique tient : la seconde correction ne peut pas contrepasser
    ce qui l'est déjà, et le message le dit."""

def test_correcting_a_meal_reverses_the_whole_block_in_reverse_order(manager):
    """N mouvements `cooked` négatifs, le lot de plat et son `cooked` positif,
    puis la `consumption` : contrepassés dans l'ordre INVERSE, en une
    transaction, et le repas repasse de `done` à `planned`."""

def test_correct_meal_is_the_only_caller_allowed_to_reverse_a_cooked(manager):
    """`correct_movement` sur un `cooked` de ce même repas reste refusé."""

def test_correcting_a_meal_whose_dish_batch_was_started_is_refused(manager):
    """Une part mangée rend le passé non reconstituable. Le refus DIT quoi
    faire : consommer le reste, ou corriger la seule consommation fautive."""

def test_correcting_a_meal_leaves_the_stock_exactly_as_before(manager):
    """Le critère de recette : quantités de tous les lots d'ingrédients
    identiques à l'octet près avant validation et après correction."""

def test_correcting_a_meal_is_idempotent_on_replay(manager):
    """Clé dérivée par mouvement ; un rejeu rend le même résultat."""
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_application_correction.py -q --timeout=60`
Expected: FAIL — `AttributeError: … 'correct_price'`

- [x] **Step 3: Écrire les deux méthodes**

`correct_price` : un seul `db.write()`, `repo.set_batch_price`, `repo.insert_price(source="receipt"|"manual", store_id=…)`, puis boucle sur `repo.movements_of_batch` non encore corrigés → `_correct_movement_within` puis `repo.insert_movement(**reprice(...))`. Clés d'idempotence dérivées : `correction:<id>` pour la première, `reprice:<id>` pour la seconde.

`correct_meal` : lit le repas et ses mouvements par `ref_type='meal'` / `ref_id`, **refuse** si le lot de plat a `remaining < initial` (entamé), puis contrepasse `reversed(movements)` avec `allow_cooked=True`, ferme le lot de plat, et `repo.update_meal_fields(conn, meal_id, {"state": "planned"})` — le tout dans **un seul** `db.write()`.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_application_correction.py tests/test_meal_validate.py -q --timeout=60`
Expected: PASS

- [x] **Step 5: Suite complète**

Run: `./scripts/test.sh -q --timeout=120`
Expected: tout vert. Aucun test antérieur ne doit avoir changé de comportement : la comptabilité se corrige **sans qu'une requête soit touchée**, c'est le critère de l'amendement A1.

- [x] **Step 6: Commit**

```bash
git add custom_components/home_stock/application.py custom_components/home_stock/storage/repositories.py custom_components/home_stock/messages.py tests/
git commit -m "feat: correcting a price and correcting a meal, both in one transaction"
```

---

## Task 5: Amendement A3 — un prix suggéré n'est pas un prix observé

**Files:**
- Modify: `custom_components/home_stock/shopping.py`
- Modify: `custom_components/home_stock/domain/pricing.py`
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/websocket_api.py`
- Modify: `custom_components/home_stock/validators.py`
- Test: `tests/domain/test_pricing.py`, `tests/test_shopping.py`, `tests/storage/test_repositories_shopping.py`, `tests/test_websocket_session.py`

**Le défaut, vérifié dans le code.** `ShoppingService.add_line` (`shopping.py:113`) et `update_line` (`shopping.py:150`) écrivent aujourd'hui une observation `price` de source `manual` **dès que la ligne porte un prix** — y compris quand ce prix est la suggestion Open Prices que le panneau avait pré-remplie et que personne n'a touchée. `manual` occupe le rang 1 de la cascade **dans ce magasin** : dès le deuxième voyage, la supposition écrase l'étiquette du rayon, et la cascade se nourrit de ses propres suppositions.

**Pourquoi cette tâche vient avant l'écran Ticket.** Ils écrivent dans la **même table**. Solder la dette après aurait gravé des suppositions comme observations pendant toute la durée du lot.

**Interfaces:**
- `PriceSuggestion` gagne `observed: bool` — `True` pour `store`, `False` pour `open_prices` et `last_known`.
- `validators.price_source(value) -> str | None` — l'une de `PRICE_SOURCES`, ou `None`.
- `ShoppingService.add_line(..., price_source: str | None = None)` et `update_line(..., price_source: str | None = None)`.
- `repo.latest_price_in_store(conn, article_id, store)` filtre `source IN OBSERVED_PRICE_SOURCES`.

- [x] **Step 1: Écrire les tests**

```python
# tests/domain/test_pricing.py
def test_a_store_price_is_observed_and_open_prices_is_not():
    assert suggest_price(in_store=0.002, open_prices=None, last_known=None,
                         store="Leclerc").observed is True
    assert suggest_price(in_store=None, open_prices=0.003, last_known=None,
                         store="Leclerc").observed is False
    assert suggest_price(in_store=None, open_prices=None, last_known=0.004,
                         store=None).observed is False

# tests/test_shopping.py
def test_a_price_accepted_without_being_touched_is_written_as_open_prices():
    """Le coeur de A3 : `price_source='open_prices'` en entrée produit une
    observation `price` de source `open_prices`, pas `manual`."""

def test_a_price_typed_by_a_human_is_written_as_manual():
    """Et le rang 1 de la cascade lui appartient."""

def test_an_absent_price_source_defaults_to_manual():
    """Compatibilité : un appelant qui ne dit rien décrit un prix tapé —
    c'est ce que faisait le lot 1, et c'est le choix qui ne perd rien."""

def test_correcting_a_price_at_the_till_always_writes_manual():
    """`update_line` avec une valeur DIFFÉRENTE est une saisie humaine, quelle
    que soit la source annoncée : on vient de la corriger devant l'étiquette."""

def test_the_shopping_line_remembers_where_its_price_came_from():
    """`shopping_line.price_source` est écrite, et relue par le panier."""

# tests/storage/test_repositories_shopping.py
def test_an_open_prices_observation_never_reaches_rank_one():
    """LE test de la dette : deux observations dans le même magasin, l'une
    `open_prices` plus récente, l'autre `manual` plus ancienne.
    `latest_price_in_store` rend la MANUELLE."""

def test_a_receipt_and_an_import_observation_do_reach_rank_one():
    """`receipt` et `import` sont des observations : le ticket et la reprise
    Grocy disent ce qui a réellement été payé."""

def test_a_store_with_only_suggested_prices_answers_nothing():
    """Et la cascade retombe alors sur Open Prices puis sur le dernier prix
    connu — comportement du lot 1, préservé."""
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_pricing.py tests/test_shopping.py -q`
Expected: FAIL

- [x] **Step 3: Écrire le code**

`pricing.suggest_price` : ajouter `observed` au `dataclass` (défaut `False`) et le poser à `True` sur la seule branche `in_store`.

`shopping.add_line` / `update_line` : accepter `price_source`, l'écrire dans `shopping_line.price_source`, la transmettre à `repo.insert_price(source=…)`. `update_line` **force `manual`** quand la valeur change réellement (le garde-fou sur le changement de valeur du lot 1 reste en place, il empêche un rejeu d'empiler des lignes identiques).

`repo.latest_price_in_store` : `AND source IN (…OBSERVED_PRICE_SOURCES…)` via un `_reasons_sql`-like local — pas de littéral dupliqué, la liste vit dans `const.py`.

`websocket_api.session_add_line` et `session_update_line` : `vol.Optional("price_source"): _price_source`. `_suggest_price` rend déjà `asdict(...)`, qui porte donc `observed` : le panneau n'a qu'à le relayer.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/domain/test_pricing.py tests/test_shopping.py tests/storage tests/test_websocket_session.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "fix: a suggested price no longer records itself as observed in this shop"
```

---

## Task 6: Le magasin promu en table

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/shopping.py`
- Modify: `custom_components/home_stock/validators.py`
- Modify: `custom_components/home_stock/messages.py`
- Test: `tests/storage/test_repositories_shopping.py`, `tests/test_shopping.py`

**Interfaces:**
- `repo.list_stores(conn, *, active_only=True) -> list[dict]` — `{id, name, position, active, observed_sessions, last_seen}`. **Change de forme** : rendait une `list[str]`.
- `repo.upsert_store(conn, *, name, store_id=None, position=None, active=None) -> int`
- `repo.get_store(conn, store_id)`, `repo.find_store_by_name(conn, name)`
- `repo.merge_stores(conn, *, keep_id: int, merge_id: int) -> dict` — réaffecte `shopping_session.store_id`, `price.store_id`, `store_aisle` ; additionne les `observed_sessions` ; **ne touche pas `price.store`**.
- `ShoppingService.start(*, store: str | None = None, store_id: int | None = None)` — le nom crée le magasin s'il n'existe pas (égalité exacte, casse comprise) ; `store_id` prime.

**`price.store` n'est jamais réécrite.** `price` est un journal d'observations : chaque ligne dit ce qui a été vu le jour où ça l'a été. Réécrire le texte pour faire joli, c'est exactement ce que le lot 0 refuse au journal des mouvements.

- [x] **Step 1: Écrire les tests**

```python
def test_list_stores_now_carries_an_id_and_a_session_count():
    """Forme changée : les appelants du lot 1 (session.ts, websocket) sont
    tous mis à jour dans ce lot. Le test épingle les cinq clés."""

def test_starting_a_session_by_name_creates_the_store_once():
    """Deux voyages « Leclerc » = un seul magasin, deux sessions observées."""

def test_starting_a_session_by_id_ignores_the_name():
    """`store_id` prime : le panneau envoie une pastille, pas une chaîne."""

def test_two_spellings_stay_two_stores():
    """« Leclerc » et « E.Leclerc » restent distincts. Les réunir est une
    décision du propriétaire, prise dans les réglages, jamais devinée."""

def test_merging_reassigns_sessions_prices_and_aisle_orders():
    """Et additionne les `observed_sessions` : un magasin fiable ne
    redevient pas incertain parce qu'on a corrigé son nom."""

def test_merging_leaves_the_free_text_of_price_untouched():
    """`price.store` garde « E.Leclerc » : c'est ce qui a été observé."""

def test_merging_a_store_with_an_open_session_is_refused():
    """« On ne déplace pas le sol sous une session. » Message français."""

def test_deactivating_a_store_keeps_its_history():
    """`active = 0` le retire des pastilles, pas des prix ni des parcours."""

def test_a_store_name_is_bounded_and_stripped():
    """`validators.store_name` : vide → refus, 300 caractères → refus,
    espaces de bord retirés."""
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/storage/test_repositories_shopping.py tests/test_shopping.py -q`
Expected: FAIL

- [x] **Step 3: Écrire les dépôts et le raccord**

Dans `repositories.py` : les six fonctions, `list_stores` comptant les sessions par `LEFT JOIN shopping_session s ON s.store_id = st.id AND s.state = 'done'`. Alias **`st`**, jamais `b`.

Dans `shopping.py` : `start` résout le magasin (`store_id` d'abord, sinon `find_store_by_name` puis `upsert_store`), écrit `shopping_session.store_id` **et** conserve `shopping_session.store` (le texte reste, comme `price.store`).

`merge_stores` refuse si `repo.current_session(conn)` porte l'un des deux identifiants.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage tests/test_shopping.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: the shop becomes a row, and two spellings stay two shops"
```

---

## Task 7: `domain/shoppinglist.py` — la réconciliation, pure

**Files:**
- Create: `custom_components/home_stock/domain/shoppinglist.py`
- Test: `tests/domain/test_shoppinglist.py`

**Interfaces:**
- `@dataclass(frozen=True) class Claim: origin: str; quantity: float | None; detail: str | None`
- `@dataclass(frozen=True) class WantedItem: product_id: int | None; free_text: str | None; claims: tuple[Claim, ...]`
- `@dataclass(frozen=True) class Plan: to_create; to_update; to_remove; claims_to_add; claims_to_drop`
- `reconcile(*, wanted: Sequence[WantedItem], existing: Sequence[Mapping], session_open: bool) -> Plan` — pur.
- `item_quantity(claims) -> float | None` — **le maximum** des quantités non nulles, `None` si aucune.
- `shortage_claim(row, *, already_claimed: bool) -> Claim | None` — porte l'hystérésis à `SHORTAGE_KEEP_FACTOR`.

**Pourquoi un module pur, et pourquoi la même forme que `maintenance_plan()`.** La macro `maintenance.jinja` de la maison a exactement ce problème et sa solution est connue du foyer : `items` (seuil d'apparition) et `keep` (seuil de maintien), et **jamais de fermeture sur une donnée absente**. Le lot 4 reprend la sémantique mot pour mot, dans un module qu'un test peut interroger sans base.

**Le maximum, jamais la somme.** Un seuil de réapprovisionnement et un besoin de recette décrivent le **même stock manquant** vu de deux côtés, pas deux stocks. On n'achète pas deux fois le même litre.

- [x] **Step 1: Écrire les tests**

```python
def test_two_origins_make_one_line_with_two_claims():
    """Le lait sous son seuil ET manquant pour le gratin de jeudi."""

def test_the_quantity_is_the_maximum_never_the_sum():
    """Seuil = 2 L, recette = 1,5 L → 2 L. Pas 3,5 L."""

def test_a_claim_without_a_quantity_never_erases_a_known_one():
    """« Prends du pain » n'écrase pas « 500 g » et ne s'y ajoute pas."""

def test_an_item_with_no_quantity_at_all_says_what_it_takes():
    """Aucune revendication chiffrée → `quantity is None`, « ce qu'il faut »."""

def test_the_shortage_disappears_but_the_meal_keeps_the_line_alive():
    """On rachète du lait : la revendication `shortage` s'éteint, celle du
    planning tient, la LIGNE survit — et sa quantité retombe à celle du repas."""

def test_an_item_with_no_claim_left_is_removed():
    """`removed_at`, jamais un DELETE."""

def test_a_manual_line_is_never_removed_by_the_robot():
    """Seule dérogation à « la liste appartient au composant », et
    indispensable : sans elle, « prends des piles pour la télécommande du
    salon » disparaîtrait en quinze minutes."""

def test_a_checked_item_is_left_alone_while_the_session_is_open():
    """La fenêtre entre le chariot et le placard : la rupture existe encore
    en base, et rien ne doit remettre la ligne pendant qu'on est à la caisse."""

def test_a_checked_item_is_purged_once_the_session_is_closed():
    """Et une ligne NEUVE est recréée si la rupture persiste : on a coché
    sans acheter, ou pas assez. La liste dit ce qui manque MAINTENANT."""

def test_the_hysteresis_keeps_a_line_up_to_fifteen_percent_above_the_threshold():
    """Seuil 500 g : apparaît sous 500, se maintient jusqu'à 575, disparaît
    au-delà. Sans cette marge, un produit qui oscille fait clignoter sa ligne
    tous les quarts d'heure — et une liste qui clignote est une liste qu'on
    n'ouvre plus."""

def test_the_hysteresis_boundaries_are_exact():
    """499,9 → apparaît. 500,0 → n'apparaît pas. 575,0 → maintenue.
    575,1 → fermée. Les quatre, pas seulement les deux du milieu."""

def test_a_missing_measurement_maintains_instead_of_closing():
    """Seuil supprimé, produit désactivé, appariement de recette défait : la
    revendication est MAINTENUE. On ne retire une ligne que sur une mesure
    qui prouve que le besoin a disparu, jamais sur une absence de mesure.
    C'est ce qui évite les disparitions fantômes au redémarrage, quand les
    entités sont encore muettes."""

def test_a_removed_line_is_not_put_back_by_the_next_pass():
    """Barrée à la main : la réconciliation s'en souvient."""

def test_a_free_text_line_never_merges_with_a_product_line():
    """Pas d'appariement par nom : c'est ce qui a produit 35 doublons dans
    Grocy en avril 2026."""

def test_reconcile_is_deterministic_and_writes_nothing():
    """Deux appels sur les mêmes entrées rendent le même Plan ; le Plan est
    un `frozen dataclass`, il ne porte aucune connexion."""
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_shoppinglist.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 3: Écrire le module**

Pur : ni `hass`, ni SQLite, ni horloge (l'instant est passé en argument). Les cinq règles du § 7.3 sont écrites dans la docstring, numérotées, avec la raison de chacune.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/domain/test_shoppinglist.py -q`
Expected: PASS

- [x] **Step 5: Vérifier que les tests ont des dents (mutation)**

Remplacer le `max(...)` de `item_quantity` par `sum(...)` : `test_the_quantity_is_the_maximum_never_the_sum` doit tomber. Puis retirer le facteur d'hystérésis (`keep = threshold`) : les deux tests de bornes doivent tomber. Remettre.

- [x] **Step 6: Commit**

```bash
git add custom_components/home_stock/domain/shoppinglist.py tests/domain/test_shoppinglist.py
git commit -m "feat: one line per product, one claim per reason, and a 15 % hysteresis"
```

---

## Task 8: Les dépôts de la liste, des revendications et des récurrences

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/validators.py`
- Test: `tests/storage/test_repositories_list.py` *(nouveau)*, `tests/test_validators.py`

**Interfaces:**
- `list_items(conn, *, store_id: int | None = None, include_checked: bool = True) -> list[dict]` — jointure gauche sur `store_aisle` filtrée par `store_id`, `ORDER BY COALESCE(sa.position, ai.position, 999), p.name, sl.id`. Alias **`sl`**, **`sa`**, **`ai`** — jamais `b`.
- `insert_list_item`, `update_list_item`, `check_list_item(conn, item_id, *, at, session_id, line_id)`, `uncheck_list_item`, `remove_list_item`, `purge_list_item`
- `open_item_for_product(conn, product_id) -> dict | None`
- `set_claim(conn, *, item_id, origin, quantity, detail, claimed_at)`, `drop_claim`, `claims_of(conn, item_id)`
- `list_recurring(conn, *, active_only=True)`, `upsert_recurring`, `delete_recurring`, `due_recurring(conn, today) -> list[dict]`, `mark_recurring_added(conn, recurring_id, on)`
- `list_estimate_rows(conn) -> list[dict]` — pour chaque ligne ouverte, l'article d'achat habituel (le **dernier acheté**, à défaut l'article générique du produit) et son dernier prix connu.
- `validators.list_quantity(value) -> float | None` — `]0 ; MAX_LIST_QUANTITY]` ou `None`
- `validators.every_days(value) -> int` — `[1 ; MAX_EVERY_DAYS]`

- [x] **Step 1: Écrire les tests**

```python
def test_the_list_is_ordered_by_the_store_route_when_there_is_one():
    """`store_aisle.position` d'abord, `aisle.position` en repli, 999 pour
    un produit sans rayon."""

def test_the_list_falls_back_to_the_default_order_without_a_store():
    """Aucun `store_id` : l'ordre par défaut du lot 1, inchangé."""

def test_checking_an_item_records_who_checked_it():
    """`session_id` et `line_id` : c'est le SCAN qui coche, et la ligne de
    panier doit rester retrouvable pour pouvoir décocher."""

def test_unchecking_clears_the_three_columns_together():
    """Sinon un item décoché garderait un `line_id` mort, et le décochage
    suivant viserait une ligne qui n'existe plus."""

def test_removing_is_a_timestamp_never_a_delete():
    """La réconciliation doit se SOUVENIR qu'on n'en veut pas."""

def test_a_claim_is_upserted_per_origin():
    """Deux passages de la même origine mettent à jour, n'empilent pas."""

def test_dropping_the_last_claim_leaves_the_item_intact():
    """Le dépôt ne décide rien : c'est `reconcile()` qui décide, le dépôt
    exécute. Deux responsabilités, deux couches."""

def test_deleting_a_product_takes_its_items_and_claims_with_it():
    """`ON DELETE CASCADE` sur les revendications ; les items du produit
    supprimé sont retirés (§ 15)."""

def test_due_recurring_uses_last_added_on_plus_every_days():
    """Jamais ajoutée → due. Ajoutée il y a `every_days − 1` → pas due.
    Ajoutée il y a exactement `every_days` → due. Les trois."""

def test_an_inactive_recurring_line_is_never_due():

def test_list_estimate_rows_prefers_the_last_bought_article():
    """« ça va faire combien ? » se répond avec l'article qu'on achète
    d'habitude, pas avec le moins cher du catalogue."""

def test_list_estimate_rows_reports_lines_it_could_not_price():
    """C'est ce qui alimente `confidence` : la proportion de lignes
    réellement chiffrées, dite en clair plutôt que noyée dans un total."""

def test_no_query_in_this_module_aliases_a_table_as_b():
    """Le test existant scanne `SELECT b.*` littéralement dans tout
    `custom_components/` : il ne distingue pas les tables, et un alias `b`
    sur `receipt` le ferait tomber sans rapport avec `batch`."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/storage/test_repositories_list.py tests/test_validators.py -q`
Expected: FAIL puis PASS.

- [x] **Step 5: Vérifier le garde-fou `SELECT b.*`**

Run: `./scripts/test.sh tests/storage/test_repositories.py -q -k "select_b or alias"`
Expected: PASS — aucune requête de ce lot n'aliase une table en `b`.

- [x] **Step 6: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py custom_components/home_stock/validators.py tests/
git commit -m "feat: the list, its claims and its recurring lines, at the repository level"
```

---

## Task 9: `application.reconcile_shopping_list()` et les quatre origines

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/const.py`
- Modify: `custom_components/home_stock/config_flow.py`
- Test: `tests/test_application_shopping_list.py` *(nouveau)*, `tests/test_config_flow.py`

**Interfaces:**
- `StockManager.reconcile_shopping_list(*, today: date, horizon_days: int = DEFAULT_SHOPPING_LIST_HORIZON_DAYS) -> dict` → `{"created", "updated", "removed", "open"}`
- `StockManager.add_to_shopping_list(*, product_id=None, free_text=None, quantity=None, note=None, idempotency_key=None) -> dict`
- `StockManager.check_list_item`, `uncheck_list_item`, `remove_list_item`
- `StockManager.shopping_list(*, store_id=None) -> list[dict]`
- `StockManager.list_estimate() -> dict` → `{"amount", "confidence", "priced", "total"}`
- Option `CONF_SHOPPING_LIST_HORIZON_DAYS` (défaut 7) dans le flux d'options ; `MEAL_HORIZON_DAYS` reste la valeur par défaut mais n'est plus lue en dur par cette voie.

**Les quatre origines.** `shortage` ← `repo.shortage_rows` (avec l'hystérésis appliquée dans le domaine) ; `meal_plan` ← `repo.missing_products_between` sur `horizon_days` jours, **déjà mis à l'échelle des convives** ; `manual` ← le panneau, l'entité `todo`, le service ; `recurring` ← `repo.due_recurring`.

**Aucune ligne de ce lot ne connaît le mot « pile ».** Le lot 5 a fait de la CR2032 de rechange un `product` avec `edible = 0` ; une rechange sous son seuil est un produit sous son seuil, produit une revendication `shortage`, et apparaît au rayon « Entretien et maison ». Le filtre du purificateur et les sacs de l'aspirateur suivent le même chemin.

**Une seule transaction.** Lecture des quatre origines et de l'existant, `reconcile()` en Python **hors verrou**, puis **un** `db.write()` qui applique le `Plan`. `Database._lock` n'est pas réentrant : aucune des méthodes appelées ici ne peut ouvrir sa propre transaction.

- [x] **Step 1: Écrire les tests**

```python
def test_a_shortage_creates_a_line_with_its_missing_quantity():
def test_a_missing_ingredient_creates_a_line_scaled_to_the_guests():
def test_the_same_product_from_two_origins_stays_one_line():
def test_a_recurring_line_appears_when_it_is_due_and_marks_itself_added():
def test_a_spare_battery_below_its_threshold_appears_like_any_other_product():
    """Aucun code spécifique : le résultat le plus satisfaisant du découpage.
    La ligne se distingue seulement par son rayon, « Entretien et maison » —
    ce qui est exactement l'information utile."""
def test_reconciling_twice_changes_nothing():
    """Idempotence : la deuxième passe rend `created == 0`."""
def test_reconciling_while_a_session_is_open_leaves_checked_items_alone():
def test_reconciling_after_the_session_closes_purges_and_may_recreate():
def test_a_manual_line_survives_every_pass():
def test_the_horizon_option_changes_the_meal_window():
    """3 jours ne réclame pas les ingrédients du dîner de dimanche ;
    14 jours si. « Ce que je prépare » et « ce pour quoi je fais les
    courses » ne sont pas forcément la même durée."""
def test_the_whole_reconciliation_runs_in_one_write_transaction():
    """Avec `--timeout=60` : un verrou imbriqué figerait le processus SANS
    lever, et ce test est ce qui le transforme en échec lisible."""
def test_add_to_shopping_list_refuses_a_line_that_names_nothing():
def test_add_to_shopping_list_is_idempotent_on_its_key():
def test_list_estimate_reports_its_confidence():
    """Entièrement estimé, et il le dit. Ce capteur répond à « ça va faire
    combien ? » et à rien d'autre : il n'entre dans aucune comptabilité."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/test_application_shopping_list.py tests/test_config_flow.py -q --timeout=60`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: four origins, one list, reconciled in a single transaction"
```

---

## Task 10: `todo.home_stock_shopping`, deux capteurs et le coordinateur

**Files:**
- Modify: `custom_components/home_stock/todo.py`
- Modify: `custom_components/home_stock/sensor.py`
- Modify: `custom_components/home_stock/coordinator.py`
- Modify: `custom_components/home_stock/translations/fr.json`, `en.json`
- Test: `tests/test_todo_shopping.py` *(nouveau)*, `tests/test_entities.py`

**Interfaces:**
- `ShoppingTodoList` — `_attr_supported_features = CREATE_TODO_ITEM | UPDATE_TODO_ITEM | DELETE_TODO_ITEM`.
- `sensor.home_stock_shopping_list` — nombre de lignes ouvertes ; attributs `by_origin`, `by_aisle`, `items`.
- `sensor.home_stock_list_estimate` — EUR ; attribut `confidence`.
- Coordinateur : clés `shopping_list`, `list_estimate` ; la réconciliation tourne **sur le tic de 15 minutes**, après les lectures et avant le rendu du `dict`.

**Pourquoi une entité `todo` native, et pas un écran de plus.** Une liste de courses **se consulte ailleurs** (carte `todo-list`, application mobile, tablette murale au lot 6, automation) et **se dit à la voix** — `todo.add_item` et `todo.get_items` sont des services standards que les agents de la maison comprennent déjà, donc « Bleuenn, ajoute du beurre à la liste » marche sans que le lot 6 écrive un intent. Le précédent existe et marche : `todo.home_stock_expirations`.

**Ni `SET_DUE_DATE` ni `MOVE_TODO_ITEM`.** Une ligne de courses n'a pas d'échéance, et en annoncer une promettrait un tri qui n'existe pas. Et **l'ordre de la liste est celui du magasin**, calculé : laisser une carte Lovelace le réordonner ferait diverger les deux surfaces sur la seule chose que ce lot passe son temps à apprendre.

- [x] **Step 1: Écrire les tests**

```python
async def test_the_shopping_list_declares_exactly_three_features(hass):
    """CREATE | UPDATE | DELETE. Ni SET_DUE_DATE, ni MOVE_TODO_ITEM —
    et le test épingle leur ABSENCE, pas seulement la présence des trois."""

async def test_checking_an_item_marks_it_got_not_stocked(hass):
    """« Je l'ai », jamais « c'est en stock ». AUCUN lot, AUCUN mouvement,
    AUCUNE entrée en stock : une case cochée ne porte qu'un BIT, et ne peut
    dire ni quel article, ni quelle quantité, ni quel prix, ni quel
    emplacement, ni quelle DLC — exactement les cinq informations qu'il
    faut pour créer un lot."""

async def test_creating_from_the_card_creates_a_manual_line(hass):
    """Avec un `free_text` quand aucun produit ne dépasse le seuil de
    présélection du lot 1 (0,75, et 0,10 d'avance sur le second)."""

async def test_deleting_from_the_card_is_a_removal_never_a_delete(hass):

async def test_a_stale_uid_is_a_no_op_not_an_error(hass):
    """Même garde-fou que `todo.home_stock_expirations` : le coordinateur
    rafraîchit toutes les 15 minutes, une ligne cochée ailleurs entre-temps
    peut encore être cochable sur une tablette. L'intention est déjà vraie."""

async def test_a_non_numeric_uid_surfaces_as_a_home_assistant_error(hass):
    """Il ne peut pas venir de nos propres `todo_items` : c'est un vrai bug."""

async def test_the_summary_reads_like_a_shopping_line(hass):
    """« Lait — 2 L » via `format_quantity` ; la description dit les origines
    en clair : « sous le seuil · dîner de jeudi »."""

async def test_the_two_new_sensors_publish_their_attributes(hass):
async def test_the_expirations_list_is_untouched(hass):
    """Garde-fou : deux entités `todo` coexistent, la première ne change ni
    de nom, ni de fonctionnalités, ni de comportement."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/test_todo_shopping.py tests/test_entities.py -q`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: todo.home_stock_shopping, and two sensors that answer how much"
```

---

## Task 11: Le pointage au scan

**Files:**
- Modify: `custom_components/home_stock/shopping.py`
- Test: `tests/test_shopping.py`, `tests/test_websocket_session.py`

**La règle, et une seule.** Greffée sur `add_line`, **dans la même transaction** que l'insertion de la ligne : si un item de liste ouvert porte le **produit** de l'article scanné, il est coché — `checked_at` prend l'instant, `session_id` et `line_id` retiennent qui l'a coché.

**Sur le produit, pas sur l'article** — même règle qu'au lot 3 pour les ingrédients, et même raison : la liste dit « du lait », le rayon propose une brique de telle marque.

**Le pointage n'est jamais une condition du scan.** Liste vide, produit absent, table verrouillée : la ligne de panier s'écrit quand même. Règle générale du composant depuis le lot 1 — ce qui est accessoire ne bloque jamais ce qui est essentiel.

- [x] **Step 1: Écrire les tests**

```python
def test_scanning_a_listed_product_checks_its_line():
def test_the_check_records_the_session_and_the_line():
def test_scanning_an_article_of_another_brand_still_checks_the_product_line():
    """Un article inconnu créé au scan et rattaché à « Lait » coche la ligne
    « Lait » sans rien de plus."""
def test_scanning_something_not_on_the_list_does_nothing_at_all():
    """Acheter ce qu'on n'avait pas prévu est le comportement normal d'un
    être humain dans un magasin, pas une anomalie à signaler."""
def test_removing_a_line_unchecks_what_it_had_checked():
    """Retirer une ligne du panier, c'est reposer l'article sur l'étagère."""
def test_update_line_touches_nothing():
def test_a_stored_line_no_longer_unchecks():
    """`remove_line` y est déjà refusé par le lot 1 (« corrigez le lot, pas
    la liste ») ; l'item est purgé ou recréé par la réconciliation."""
def test_a_replayed_add_line_does_not_check_twice():
    """`add_line` rejoué avec la même clé rend la ligne DÉJÀ créée sans rien
    réécrire, donc sans re-cocher."""
def test_a_remove_replayed_after_an_add_leaves_the_item_unchecked():
    """La file hors ligne rejoue DANS L'ORDRE : décoche après avoir coché,
    et l'état final est le bon."""
def test_a_failing_check_never_blocks_the_cart_line():
    """Item verrouillé, produit supprimé entre-temps : la ligne de panier
    s'écrit quand même. Le test provoque l'échec et vérifie la ligne."""
def test_checking_needs_no_open_session():
    """On coche une liste chez soi aussi (§ 15) — c'est le websocket
    `list/check` qui le permet, pas le scan."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/test_shopping.py tests/test_websocket_session.py -q --timeout=60`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/shopping.py tests/
git commit -m "feat: the scan checks the list, and putting an item back unchecks it"
```

---

## Task 12: Le coût du panier — estimé, constaté, hors liste

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/sensor.py`
- Test: `tests/storage/test_repositories_shopping.py`, `tests/test_entities.py`

**Interfaces:**
- `repo.session_totals(conn, session_id)` gagne `estimated`, `observed`, `unpriced_lines`, `off_list_lines`, `checked_items`, `list_items`.
- `summary()` gagne `cart_estimated`, `cart_observed`, `cart_unpriced_lines`, `cart_off_list_lines`, `cart_list_progress`.
- `CartTotalSensor.extra_state_attributes` gagne `estimated`, `observed`, `unpriced_lines`, `off_list_lines`, `store`.

**Trois catégories, jamais une moyenne.**

| Catégorie | Ce que c'est | `price_source` |
|---|---|---|
| Constaté | Prix tapé ou corrigé par un humain devant l'étiquette, ou lu sur le ticket | `manual`, `receipt` |
| Estimé | Suggestion acceptée sans y toucher | `open_prices`, `last_known`, `store` |
| Inconnu | Aucun prix. Compté **zéro dans le total**, et **signalé** | `NULL` |

Le panier affiche `47,20 € — dont 12,30 € estimés, 2 lignes sans prix`. Une ligne, trois faits. C'est le chiffre qu'on compare mentalement au ticket ; un écart inexpliqué détruit la confiance dans tout le reste.

**Aucun capteur nouveau pour le panier** : le lot 0 a posé qu'une synthèse s'enrichit d'attributs plutôt que de se dupliquer.

**Le coût par nutriment est gratuit.** Le lot 2 a figé les neuf nutriments sur *tout* mouvement, achats compris, en annonçant que ça « rendrait le lot 4 gratuit ». C'est vérifié : le panier connaît les kilocalories qu'il rapporte sans une colonne de plus, et le panneau l'affiche en **second rang**, comme une curiosité et non comme une décision.

- [x] **Step 1: Écrire les tests**

```python
def test_the_total_splits_into_observed_and_estimated():
    """Somme inchangée, répartie. `observed + estimated == total`, exactement."""

def test_a_line_without_a_price_counts_zero_and_is_counted():
    """`COALESCE` la comptait déjà zéro en silence ; désormais elle est DITE."""

def test_a_store_sourced_price_counts_as_estimated():
    """`store` = le dernier prix relevé dans ce magasin, proposé et accepté
    sans y toucher : c'est une suggestion, pas l'étiquette d'aujourd'hui."""

def test_the_off_list_counter_counts_lines_not_units():
    """« n hors liste » sert à UNE chose : savoir, à la caisse, combien
    d'articles se sont invités."""

def test_the_progress_counts_checked_over_open():
    """« 12 / 17 de la liste »."""

def test_a_session_with_no_line_publishes_zeroes_not_nulls():
    """Un capteur `unknown` en plein magasin est un capteur inutile."""

async def test_cart_total_publishes_the_five_attributes(hass):
async def test_no_new_sensor_was_created_for_the_cart(hass):
    """Garde-fou : le nombre d'entités `sensor` du composant augmente de
    exactement trois sur tout le lot — shopping_list, list_estimate,
    receipts_pending — et d'aucune de plus."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/storage/test_repositories_shopping.py tests/test_entities.py -q`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: the cart says how much of its total is a guess"
```

---

## Task 13: `domain/route.py` — l'ordre appris, pur

**Files:**
- Create: `custom_components/home_stock/domain/route.py`
- Test: `tests/domain/test_route.py`

**Interfaces:**
- `session_ranks(aisle_sequence: Sequence[int]) -> dict[int, float]` — rang moyen normalisé sur `[0,1]` de chaque rayon dans **une** session.
- `learn_route(sessions: Sequence[Sequence[int]], *, default_positions: Mapping[int, int], pinned: Mapping[int, int] | None = None) -> list[RouteEntry]` — `RouteEntry(aisle_id, position, mean_rank, observed_sessions, source)`.
- `is_reliable(session_count: int) -> bool` — `session_count >= ROUTE_MIN_SESSIONS`.

**Ce qu'on apprend, et de quoi.** La donnée existe déjà et personne ne la lisait : `shopping_line.scanned_at`. **L'ordre des scans est l'ordre du parcours**, à ceci près qu'on scanne parfois trois articles du même rayon d'affilée et qu'on revient parfois sur ses pas.

**Pourquoi une moyenne de rangs et pas un tri topologique.** Le tri topologique sur les précédences observées est la solution élégante, et elle meurt sur le premier **cycle**. Or les cycles sont la norme : on retourne à la boulangerie en fin de course, on revient chercher le lait oublié. Un algorithme qui doit alors « casser une arête » choisit arbitrairement laquelle, donc produit un ordre différent pour deux jeux de données presque identiques. La moyenne de rangs n'a **pas de cas dégénéré**, se recalcule en temps linéaire, s'explique en une phrase au propriétaire (« tu prends le pain vers la fin ») et se corrige à la main sans surprise.

**Normaliser est indispensable** : une session de 8 lignes et une de 40 doivent peser pareil.

- [x] **Step 1: Écrire les tests**

```python
def test_a_clean_walk_gives_back_its_own_order():
def test_repeated_scans_of_one_aisle_average_out():
    """Trois yaourts d'affilée ne déplacent pas la crémerie de trois rangs."""
def test_a_backtrack_pulls_the_aisle_towards_the_middle():
    """On revient chercher le lait oublié : la crémerie glisse, elle ne saute
    pas à la fin."""
def test_a_full_cycle_produces_a_stable_order():
    """LE cas qui tue un tri topologique : A→B→C→A. Ici, un ordre, et le
    même ordre à chaque appel."""
def test_two_sessions_of_very_different_sizes_weigh_the_same():
    """8 lignes contre 40 : sans normalisation, la grande écraserait la
    petite et le magasin apprendrait un seul voyage."""
def test_an_aisle_seen_in_only_one_session_keeps_its_default_place():
    """L'animalerie visitée une fois ne doit pas s'installer entre la
    crémerie et les fromages (ROUTE_MIN_AISLE_SESSIONS = 2)."""
def test_an_unobserved_aisle_keeps_aisle_position():
def test_a_tie_is_broken_by_the_default_position():
    """Déterminisme : deux moyennes égales ne doivent pas dépendre de
    l'ordre d'itération d'un dictionnaire."""
def test_a_pinned_aisle_is_never_moved_by_learning():
    """Règle `article.manual_fields` du lot 0, transposée. Le calcul continue
    de tourner et `mean_rank` reste visible — on VOIT donc que l'ordre appris
    contredit l'ordre épinglé — mais `position` ne bouge pas."""
def test_learning_stays_available_after_unpinning():
    """Le bouton « reprendre l'apprentissage » rend la ligne à l'automatisme."""
def test_fewer_than_three_sessions_is_not_reliable():
    """Avec une observation, un détour exceptionnel devient la loi ; avec
    deux, rien ne distingue une habitude d'une coïncidence ; à trois, une
    valeur aberrante est minoritaire. Le foyer fait une grande course par
    semaine : trois semaines."""
def test_only_the_last_ten_sessions_are_kept():
    """Un magasin réaménage ses rayons, et une moyenne sur toute l'histoire
    mettrait des mois à s'en apercevoir. Le tronquage est fait par
    l'appelant ; ce test épingle que `learn_route` n'en tronque PAS un
    deuxième, ce qui diviserait la fenêtre par deux en silence."""
def test_learn_route_is_deterministic():
    """Deux appels, même sortie, y compris sur des égalités parfaites."""
def test_an_empty_history_returns_the_default_order_untouched():
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/domain/test_route.py -q`
Expected: FAIL puis PASS.

- [x] **Step 5: Vérifier que les tests ont des dents (mutation)**

Retirer la normalisation (`rang moyen` au lieu de `rang moyen / n`) : `test_two_sessions_of_very_different_sizes_weigh_the_same` doit tomber. Puis laisser l'apprentissage écraser une ligne `manual` : `test_a_pinned_aisle_is_never_moved_by_learning` doit tomber. Remettre.

- [x] **Step 6: Commit**

```bash
git add custom_components/home_stock/domain/route.py tests/domain/test_route.py
git commit -m "feat: the walking order of a shop, learned from mean scan ranks"
```

---

## Task 14: `store_aisle` — apprendre à la clôture, trier, épingler

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/shopping.py`
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_shopping.py`, `tests/storage/test_repositories_shopping.py`

**Interfaces:**
- `repo.store_route(conn, store_id) -> list[dict]` — `store_aisle` joint à `aisle`, avec `mean_rank` et `observed_sessions`.
- `repo.recent_session_aisle_sequences(conn, store_id, limit=ROUTE_SESSION_WINDOW) -> list[list[int]]` — les lignes des dernières sessions **closes**, triées par `scanned_at`, ramenées au rayon de leur produit.
- `repo.save_store_route(conn, store_id, entries, *, updated_at)` — n'écrase **jamais** une ligne `source = 'manual'`.
- `repo.pin_store_aisles(conn, store_id, aisle_ids)` / `repo.unpin_store_aisle(conn, store_id, aisle_id)`
- `StockManager.learn_store_route(store_id) -> dict` et `_learn_store_route_within(conn, store_id, *, moment)`.
- `repo.list_lines` : `ORDER BY aisle_position` devient `ORDER BY COALESCE(sa.position, ai.position, 999), …`, jointure gauche sur `store_aisle` filtrée par le `store_id` de la session.

**Le recalcul a lieu à la clôture d'une session, pas à chaque scan** : on n'apprend pas d'un parcours en cours. Il vit **dans la transaction de clôture** (`ShoppingService.close`), via `_learn_store_route_within` — un second `db.write()` figerait le processus.

**En dessous de trois sessions**, `store_aisle` est rempli et visible dans les réglages, mais **l'affichage utilise `aisle.position`**. Les réglages le disent en toutes lettres (« 2 sessions sur 3 »).

**L'écran de rangement ne trie pas par rayon** — il groupe par emplacement **dans la maison**. C'est rappelé ici parce que c'est le genre de cohérence qu'on applique par réflexe là où elle n'a pas de sens.

- [x] **Step 1: Écrire les tests**

```python
def test_closing_a_session_recalculates_the_route():
def test_scanning_does_not_recalculate_anything():
def test_the_cart_is_sorted_by_the_store_route_once_it_is_reliable():
def test_the_cart_keeps_the_default_order_below_three_sessions():
    """`store_aisle` est REMPLI et visible ; seul l'affichage attend."""
def test_a_pinned_aisle_survives_the_next_close():
def test_unpinning_gives_the_line_back_to_learning():
def test_learning_reads_at_most_the_last_ten_closed_sessions():
def test_an_open_session_is_never_part_of_the_history():
def test_the_put_away_screen_is_not_sorted_by_aisle():
    """Garde-fou explicite : `rangement` groupe par emplacement dans la
    maison. Un test l'épingle pour que personne ne « corrige » ça."""
def test_learning_runs_inside_the_close_transaction():
    """Avec `--timeout=60` : un `db.write()` imbriqué figerait la clôture
    d'une session en plein magasin, sans exception et sans trace."""
def test_a_session_with_no_store_learns_nothing_and_raises_nothing():
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/test_shopping.py tests/storage -q --timeout=60`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: a shop learns its aisle order at checkout, and stays pinned where told"
```

---

## Task 15: `receipt/parse.py` et les fixtures de tickets

**Files:**
- Create: `custom_components/home_stock/receipt/__init__.py`, `custom_components/home_stock/receipt/parse.py`
- Create: `tests/fixtures/receipts/*.json`
- Test: `tests/receipt/test_parse.py` *(nouveau paquet)*

**Interfaces:**
- `RECEIPT_STRUCTURE: dict` — le schéma de sortie passé à `ai_task` (magasin, date, total, devise, lignes `{libellé, quantité, prix unitaire, prix total}`).
- `@dataclass(frozen=True) class ParsedLine: position; label; quantity; unit_price; total_price`
- `@dataclass(frozen=True) class ParsedReceipt: store; purchased_on; total; currency; lines; dropped; total_gap; warnings`
- `parse(payload: Any, *, session_started_on: str, today: str) -> ParsedReceipt` — **ne lève jamais**.

**La réponse structurée est validée quand même**, champ par champ, avec les helpers du composant (`bounded_text`, `finite_float`, `non_negative_float`, `bounded_int`, `iso_date`). Un schéma contraint la **forme**, pas la **vraisemblance** : rien n'empêche un modèle de rendre 4 000 € ou une date en 1970.

| Contrôle | Seuil |
|---|---|
| Prix unitaire et total d'une ligne | `0 ≤ v ≤ 1 000` € |
| Total du ticket | `0 ≤ v ≤ 3 000` € |
| Quantité d'une ligne | `0 < v ≤ 500` |
| Nombre de lignes | `≤ 200` |
| Date d'achat | dans `[session.started_at − 2 j ; aujourd'hui]` |
| Somme des lignes contre le total lu | écart signalé au-delà de 2 %, **jamais bloquant** |

**Une ligne fautive est écartée SEULE**, contrairement à la nutrition OFF du lot 1 où un dépassement refuse toute la fiche. La différence est assumée : une fiche OFF est un **tout cohérent** dont une valeur aberrante trahit la table entière ; un ticket est une **suite de lignes indépendantes**, et perdre les dix-neuf bonnes parce que la vingtième est illisible n'aide personne. L'écart au total rend l'omission visible.

- [x] **Step 1: Écrire les fixtures et les tests**

Fixtures versionnées dans `tests/fixtures/receipts/` : `propre.json`, `promotions_et_fidelite.json`, `ligne_a_4000_euros.json`, `quantite_nulle.json`, `date_en_1970.json`, `total_qui_ne_tombe_pas_juste.json`, `vide.json`, `tronquee.json`.

```python
def test_a_clean_receipt_reads_every_line():
def test_loyalty_points_and_promotions_are_ignored():
    """Elles ne sont ni des lignes écartées ni des lignes gardées : elles
    n'entrent pas. L'invite le dit, le parseur le vérifie."""
def test_a_four_thousand_euro_line_is_dropped_alone():
    """Les dix-neuf autres survivent, et `dropped` la nomme."""
def test_a_zero_quantity_line_is_dropped():
    """`0 < v` strict : une ligne de zéro article n'a pas été achetée."""
def test_a_1970_date_is_refused_and_the_receipt_survives():
    """Une date hors fenêtre ne rend pas le ticket illisible : elle rend
    `purchased_on is None`, et le panneau demande."""
def test_the_purchase_date_window_boundaries():
    """`started_at − 2 j` accepté, `started_at − 3 j` refusé, aujourd'hui
    accepté, demain refusé. Les quatre bornes."""
def test_a_total_that_does_not_add_up_is_flagged_never_blocking():
    """Au-delà de 2 % : `total_gap` porte l'écart, les lignes restent."""
def test_a_gap_just_under_two_percent_is_silent():
def test_an_empty_answer_yields_an_empty_receipt_without_raising():
def test_a_truncated_answer_yields_an_empty_receipt_without_raising():
def test_more_than_two_hundred_lines_are_cut_and_the_cut_is_reported():
def test_parse_never_raises_on_anything():
    """Boucle sur les huit fixtures plus None, "", [], 0, True, {"lines": 3}."""
def test_nothing_in_this_module_touches_the_network_or_hass():
    """Scan d'import : ni `homeassistant`, ni `aiohttp`, ni `sqlite3`."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/receipt -q`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/receipt/ tests/receipt/ tests/fixtures/receipts/
git commit -m "feat: a receipt is read line by line, and a bad line is dropped alone"
```

---

## Task 16: `receipt/task.py`, l'option `receipt_agent` et le flux d'options

**Files:**
- Create: `custom_components/home_stock/receipt/task.py`
- Modify: `custom_components/home_stock/config_flow.py`
- Modify: `custom_components/home_stock/translations/fr.json`, `en.json`
- Test: `tests/receipt/test_task.py`, `tests/test_config_flow.py`

**Interfaces:**
- `build_instructions(*, session_labels: Sequence[str]) -> str` — invite **en français**.
- `async read_receipt(hass, *, agent_entity_id: str | None, media_content_id: str, session_labels, session_started_on: str, today: str) -> ReceiptReadResult` — **ne lève jamais**.
- `@dataclass(frozen=True) class ReceiptReadResult: parsed; raw; error; agent_entity_id`
- `supports_attachments(hass, entity_id) -> bool` — lit `AITaskEntityFeature.SUPPORT_ATTACHMENTS` sur les `supported_features` de l'entité.
- Option `CONF_RECEIPT_AGENT`, sélecteur `EntitySelector(EntitySelectorConfig(domain="ai_task"))`, **vide par défaut**.

**Une entité `ai_task`, et pourquoi pas `conversation`.** La décision du lot 3 est reprise mot pour mot — aucune clé d'API dans le composant, la maison a déjà ses backends Gemini, le composant part sur HACS et ne code aucun fournisseur en dur. **C'est l'entité qui change, parce que l'entrée change : un ticket est une image, pas une phrase.** `conversation.process` prend un texte et rend un texte ; il n'a ni pièce jointe ni réponse structurée, et décrire la photo est précisément l'information qu'on cherche à extraire.

`ai_task.async_generate_data(hass, task_name=…, entity_id=…, instructions=…, structure=…, attachments=[…])` apporte trois choses que `conversation` n'a pas : **`attachments`** (des `media_content_id` résolus par `media_source`), **`structure`** (le modèle rend un objet conforme — la gymnastique du lot 3, « le premier bloc délimité par des accolades équilibrées », disparaît), et **le même fournisseur sans configuration en plus**.

**L'invite donne les libellés des articles de la session en cours** : un modèle qui sait qu'il cherche « LT DEMI ECR 1L » parmi vingt candidats connus se trompe beaucoup moins qu'un modèle qui lit dans le vide.

**L'option est validée quand elle est CHOISIE**, pas quand elle sert : une entité sans `SUPPORT_ATTACHMENTS` est refusée par le flux d'options, en français. Découvrir l'incompatibilité à 21 h sur un parking n'est pas un moment acceptable pour l'apprendre.

**Aucun test ne sort sur le réseau.** L'entité `ai_task` est un **double injecté**, exactement comme le transport OFF l'est déjà.

- [x] **Step 1: Écrire les tests**

```python
async def test_no_agent_configured_returns_a_result_that_says_so(hass):
    """Pas de bouton « Photographier » ; les réglages disent pourquoi.
    Un réglage, pas une panne."""

async def test_the_prompt_carries_the_labels_of_the_session(hass):
async def test_the_prompt_is_in_french_and_names_what_to_ignore(hass):
    """Promotions de fidélité, points, mode de paiement."""

async def test_a_successful_read_returns_parsed_lines_and_the_raw_answer(hass, faux_ai_task):
    """`raw` est conservée telle quelle, comme `article.off_raw`."""

async def test_an_agent_that_raises_yields_a_french_error_not_an_exception(hass):
async def test_a_quota_error_yields_a_french_error(hass):
async def test_a_timeout_yields_a_french_error(hass):
async def test_an_agent_that_disappeared_names_the_missing_entity(hass):
    """`receipt.state = 'failed'`, message NOMMANT l'entité manquante — pas
    « Unknown error »."""
async def test_an_answer_out_of_bounds_drops_the_bad_lines_only(hass):
async def test_an_empty_answer_is_a_failure_not_a_crash(hass):

async def test_the_options_flow_refuses_an_entity_without_attachments(hass):
    """En français, AU RÉGLAGE. Découvrir ça sur un parking à 21 h n'est pas
    un moment acceptable."""
async def test_the_options_flow_accepts_an_entity_with_attachments(hass):
async def test_an_empty_receipt_agent_is_a_valid_setting(hass):
    """Même forme que `recipe_agent` au lot 3 : `vol.Optional` plus
    `suggested_value`, jamais `default=""` — `EntitySelector` refuse la
    chaîne vide, et « pas d'agent » deviendrait irreprésentable."""
async def test_the_horizon_option_survives_a_round_trip(hass):

def test_no_api_key_is_read_anywhere_in_the_component():
    """Scan littéral de `custom_components/` : ni `GEMINI_KEY`, ni `.env`,
    ni `.mcp.json`, ni `api_key`. C'est une RÈGLE, pas une préférence : ce
    composant part sur HACS."""

async def test_no_test_in_this_file_reaches_the_network(hass):
    """Le double est injecté ; `aiohttp` n'est jamais importé ici."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/receipt tests/test_config_flow.py -q`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/receipt/task.py custom_components/home_stock/config_flow.py custom_components/home_stock/translations/ tests/
git commit -m "feat: the receipt is read by an ai_task entity of the house, attachments and all"
```

---

## Task 17: Les dépôts du ticket, le rapprochement, et `application.apply_receipt()`

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/domain/matching.py`
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/validators.py`
- Test: `tests/domain/test_matching.py`, `tests/storage/test_repositories_receipt.py` *(nouveau)*, `tests/test_application_receipt.py` *(nouveau)*

**Interfaces:**
- `repo.insert_receipt`, `get_receipt`, `list_receipts(conn, *, states=None)`, `set_receipt_state`, `replace_receipt_lines`, `set_receipt_line_match`, `mark_receipt_line_applied`, `pending_receipts(conn)`
- `matching.receipt_candidates(*, label, lines, unit_price) -> list[Candidate]` — similarité de chaîne (marque comprise, puis marque retirée) **plus** une prime de **proximité de prix**.
- `StockManager.apply_receipt(receipt_id) -> dict` → `{"applied", "skipped", "corrected_movements"}`
- `StockManager.preview_receipt(receipt_id) -> dict` — « 3 mouvements déjà écrits seront corrigés », ou rien.

**La prime de proximité de prix.** Deux lignes dont les prix unitaires coïncident à **1 %** près se rapprochent même quand les libellés divergent — cas normal des abréviations de caisse. Les seuils du lot 1 sont **inchangés** : `auto` au-delà de 0,75 avec 0,10 d'avance sur le second, `unmatched` sinon.

**Appliquer fait trois choses et jamais une quatrième :**

1. `shopping_line.unit_price` prend le prix du ticket **ramené à l'unité de base** par la règle du lot 1 (division par le poids net en `g`/`ml`, **aucun diviseur** en `piece`) ; `price_source` passe à `receipt`.
2. Une observation `price` par ligne corrigée, `source = 'receipt'`, `store_id` de la session, `observed_on` la date du ticket. C'est elle qui alimentera le **rang 1** de la cascade au voyage suivant.
3. Si la ligne est **déjà rangée**, la correction passe par `correct_price` (§ 12.4) — le lot existe, une partie a peut-être été consommée, et le journal est en ajout seul.

**Ce que l'application ne fait pas** : elle ne crée **aucune** ligne pour un article du ticket qu'aucune ligne de panier ne porte. Un article passé en caisse sans avoir été scanné n'a ni EAN, ni article, ni produit, ni emplacement ; en fabriquer un depuis un libellé abrégé produirait des doublons de catalogue à chaque voyage — exactement le ré-appariement par nom qui a créé **35 doublons dans Grocy en avril 2026**. Ces lignes restent `unmatched`, **visibles**, et le panneau propose de scanner l'article pour les rattacher. **Le ticket relit des prix ; ce n'est pas une seconde source d'entrée en stock.**

**Une seule transaction pour tout appliquer.** `apply_receipt` ouvre **un** `db.write()` et appelle `_correct_price_within` par ligne rangée. Aucun `db.write()` imbriqué — `Database._lock` n'est pas réentrant.

- [x] **Step 1: Écrire les tests**

```python
# tests/domain/test_matching.py
def test_a_till_abbreviation_matches_its_article():
    """« LT DEMI ECR 1L » contre « Lait demi-écrémé 1 L »."""
def test_the_brand_is_tried_both_ways():
def test_a_price_within_one_percent_earns_a_bonus():
def test_a_price_bonus_alone_does_not_reach_the_auto_threshold():
    """Garde-fou : la prime AIDE, elle ne décide pas. Deux articles à 1,99 €
    ne se confondent pas parce qu'ils coûtent pareil."""
def test_a_price_two_percent_away_earns_nothing():
def test_the_lot_one_thresholds_are_unchanged():
    """0,75 et 0,10 : un test les relit depuis `matching`, pour qu'un
    ajustement du lot 4 ne déplace pas l'appariement d'ingrédients du lot 3."""

# tests/test_application_receipt.py
def test_applying_sets_the_line_price_in_base_units():
    """Divisé par le poids net en `g`/`ml`, JAMAIS en `piece`."""
def test_applying_marks_the_line_price_source_receipt():
def test_applying_writes_one_price_observation_per_corrected_line():
    """Avec le `store_id` de la session et la date du TICKET, pas celle du
    jour : c'est ce qui a été payé, le jour où ça l'a été."""
def test_a_receipt_observation_reaches_rank_one_next_trip():
def test_an_already_stored_line_goes_through_correct_price():
    """Contrepassation puis réécriture, en une transaction (§ 12.4)."""
def test_a_line_stored_and_partly_eaten_corrects_every_movement():
def test_the_usual_case_corrects_nothing_at_all():
    """Un ticket lu le soir même : `corrected_movements == 0`."""
def test_an_unmatched_receipt_line_creates_nothing():
    """Ni article, ni produit, ni lot. Elle reste visible et `unmatched`."""
def test_applying_twice_is_a_no_op():
    """`receipt_line.applied_at` rend la seconde application sans effet."""
def test_applying_a_discarded_receipt_is_refused():
def test_matching_a_line_by_hand_overrides_the_automatic_match():
    """`confirmed` et `ignored` : le même vocabulaire qu'au lot 3, les mêmes
    quatre mots, la même signification."""
def test_apply_receipt_runs_in_one_transaction():
    """`--timeout=60`."""
def test_the_put_away_never_depends_on_the_receipt():
    """Deux fils PARALLÈLES à partir de la caisse : on vide les sacs pendant
    que le modèle lit, et on lit le lendemain matin si le réseau du parking
    était mauvais. Le test range une session dont le ticket est `failed`."""
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/domain/test_matching.py tests/storage/test_repositories_receipt.py tests/test_application_receipt.py -q --timeout=60`
Expected: FAIL puis PASS.

- [x] **Step 5: Suite complète**

Run: `./scripts/test.sh -q --timeout=120`
Expected: tout vert — l'appariement d'ingrédients du lot 3 compris, qui partage `matching.py`.

- [x] **Step 6: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: a receipt re-reads prices, and never feeds the catalogue"
```

---

## Task 18: `websocket_receipts.py` et les commandes du ticket

**Files:**
- Create: `custom_components/home_stock/websocket_receipts.py`
- Modify: `custom_components/home_stock/websocket_api.py`
- Modify: `custom_components/home_stock/sensor.py`
- Modify: `custom_components/home_stock/coordinator.py`
- Test: `tests/test_websocket_receipts.py` *(nouveau)*, `tests/test_offline_queue_contract.py`

**Interfaces:**
- `home_stock/receipt/submit` — `{media_content_id, session_id?, idempotency_key?}` → enregistre et **lance la lecture**
- `home_stock/receipt/get` — état, lignes lues, lignes de panier, écart au total
- `home_stock/receipt/retry`, `home_stock/receipt/discard`
- `home_stock/receipt/line/match` — `{line_id, shopping_line_id | null, state}`
- `home_stock/receipt/apply`
- `sensor.home_stock_receipts_pending` — tickets `pending` ou `failed` ; attribut : la **dernière erreur**, en français.

**Fichier séparé** parce que `websocket_api.py` fait déjà 1 251 lignes et que les lots 3 et 5 ont créé le précédent. L'import se fait **dans** `async_register_websocket`, pas au niveau module : `websocket_receipts` réutilise les helpers de `websocket_api`, donc un import de haut niveau dans un sens ou dans l'autre serait un cycle.

**Le `media_content_id` est validé comme un chemin de média** : `validators.media_path` refuse déjà l'absolu, le `..` et tout ce qui vit sous `www/`. Un ticket porte un numéro de carte tronqué, une heure, un magasin et des habitudes ; `www/` est servi sur `/local/` **sans authentification**.

**La photo n'est pas supprimée toute seule** : elle est la pièce justificative de tout ce que le modèle en a tiré. Le nettoyage est un geste du propriétaire ; les réglages affichent la **taille du dossier** pour qu'il ne l'oublie pas.

- [x] **Step 1: Écrire les tests**

```python
async def test_submitting_records_the_receipt_and_starts_the_read(hass):
async def test_submitting_the_same_key_twice_returns_the_first_receipt(hass):
async def test_a_media_id_under_www_is_refused(hass):
    """Tout ce qui vit dans `www/` est servi sur `/local/` SANS
    authentification."""
async def test_an_absolute_or_climbing_path_is_refused(hass):
async def test_get_returns_the_lines_face_to_face(hass):
    """Lignes lues d'un côté, lignes de panier de l'autre, et l'écart au
    total. C'est l'écran."""
async def test_retry_increments_attempts_and_keeps_the_photo(hass):
async def test_discard_leaves_the_photo_and_the_lines_in_place(hass):
    """Abandonner n'est pas effacer la preuve."""
async def test_matching_by_hand_accepts_null_to_ignore_a_line(hass):
async def test_apply_needs_a_read_receipt(hass):
async def test_every_write_command_accepts_an_idempotency_key(hass):
    """Le contrat de la file hors ligne. Le téléversement d'une photo et le
    cochage d'une ligne sont des ÉCRITURES comme les autres, et se font
    typiquement là où le réseau est le plus mauvais."""
async def test_a_command_refused_by_the_service_is_refused_here_too(hass):
async def test_the_pending_sensor_publishes_the_last_error_in_french(hass):
```

Dans `tests/test_offline_queue_contract.py`, ajouter les commandes nouvelles à `EXPECTED_QUEUED_COMMAND_TYPES` **en fin de liste**. Le test scanne le TypeScript réel : il tombera de lui-même quand les écrans des tâches 21–23 poseront leurs appels.

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/test_websocket_receipts.py tests/test_offline_queue_contract.py -q`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: the receipt commands, in their own module like recipes and batteries"
```

---

## Task 19: Les commandes websocket de la liste, du magasin et de la correction

**Files:**
- Modify: `custom_components/home_stock/websocket_api.py`
- Modify: `custom_components/home_stock/validators.py`
- Test: `tests/test_websocket_list.py` *(nouveau)*, `tests/test_websocket_session.py`, `tests/test_websocket_write.py`

**Interfaces:**

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
| `home_stock/movement/correct` | Contrepasse un mouvement (§ 12) |
| `home_stock/movement/correction_preview` | Ce que la correction fera, avant |
| `home_stock/meal/correct` | Contrepasse un repas validé (§ 12.5) |
| `home_stock/session/start` *(étendue)* | Accepte `store_id` en plus du nom |
| `home_stock/session/add_line` *(étendue)* | Accepte `price_source`, coche la liste |

Les fonctions s'ajoutent **en fin** de `websocket_api.py`, leurs noms **en fin** du tuple d'`async_register_websocket`.

- [x] **Step 1: Écrire les tests**

```python
async def test_list_items_is_sorted_for_the_given_store(hass):
async def test_list_items_falls_back_to_the_open_session_store(hass):
    """Puis au DERNIER magasin utilisé, puis à l'ordre par défaut. Les
    trois niveaux, dans cet ordre."""
async def test_adding_a_free_text_line_works_without_a_product(hass):
async def test_adding_a_line_that_names_nothing_is_refused_in_french(hass):
async def test_check_and_uncheck_are_symmetric(hass):
async def test_checking_without_an_open_session_is_allowed(hass):
    """On coche une liste chez soi aussi."""
async def test_remove_is_a_timestamp(hass):
async def test_refresh_returns_the_counts(hass):
async def test_recurring_save_bounds_every_days(hass):
    """0 refusé, 1 accepté, 365 accepté, 366 refusé. Les quatre bornes."""
async def test_stores_list_carries_id_and_observed_sessions(hass):
async def test_merging_during_an_open_session_is_refused_in_french(hass):
async def test_reorder_aisles_pins_and_says_it_pinned(hass):
async def test_store_aisles_reports_how_far_the_learning_got(hass):
    """« 2 sessions sur 3 » : les réglages le DISENT plutôt que d'afficher
    un ordre par défaut sans expliquer pourquoi."""
async def test_correcting_a_movement_returns_the_correction_row(hass):
async def test_correcting_twice_answers_a_french_refusal_not_unknown_error(hass):
async def test_correction_preview_says_what_it_will_do(hass):
async def test_correcting_a_meal_refuses_a_started_dish_in_french(hass):
async def test_session_start_accepts_a_store_id(hass):
async def test_add_line_accepts_a_price_source(hass):
async def test_every_new_write_command_accepts_an_idempotency_key(hass):
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run: `./scripts/test.sh tests/test_websocket_list.py tests/test_websocket_session.py tests/test_websocket_write.py -q --timeout=60`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: the list, the shop and the correction, on the websocket surface"
```

---

## Task 20: Les six services, et la parité des deux surfaces

**Files:**
- Modify: `custom_components/home_stock/services.py`, `services.yaml`
- Modify: `custom_components/home_stock/messages.py`
- Test: `tests/test_services_shopping_list.py` *(nouveau)*, `tests/test_services_correction.py` *(nouveau)*, `tests/test_surface_parity.py` *(nouveau)*

**Interfaces:**

| Service | Rôle |
|---|---|
| `home_stock.add_to_shopping_list` | Produit ou texte, quantité, note. **La porte du vocal** |
| `home_stock.refresh_shopping_list` | Réconciliation à la demande |
| `home_stock.query_shopping_list` | **`SupportsResponse.ONLY`**, comme `query_stock` : « qu'est-ce qu'il faut acheter ? » sans créer d'entité |
| `home_stock.read_receipt` | Relance la lecture d'un ticket, ou du **dernier en échec** |
| `home_stock.correct_movement` | La contrepassation, en service |
| `home_stock.correct_meal` | Le bloc entier d'un repas validé |

**Validation aux deux surfaces.** La règle du lot 1, répétée au lot 2, tient sans exception : *aucune des deux surfaces n'a le droit d'être la plus faible*. Ce que le websocket refuse, le service le refuse, et réciproquement. Les helpers de `validators.py` sont **partagés** ; les bornes nouvelles du lot 4 (quantité de liste, `every_days`, prix de ticket, identifiant de mouvement) y vivent **une fois** et sont utilisées des deux côtés.

- [x] **Step 1: Écrire le test de parité en premier**

`tests/test_surface_parity.py` — le test qui donne son sens à la règle. Sur la même liste de valeurs limites (quantité 0, quantité négative, quantité au-delà de la borne, texte de 300 caractères, `every_days = 0`, identifiant de mouvement inexistant, prix de ticket à 4 000 €), il envoie **la même charge** sur les deux surfaces et exige **le même verdict** : refusé des deux côtés, ou accepté des deux côtés. Jamais l'un sans l'autre.

Il est écrit **avant** les services, comme `test_offline_queue_contract.py` l'a été pour la file : c'est un contrat, pas une vérification a posteriori.

```python
CAS_LIMITES = [
    # (websocket, service, charge, attendu)
    ("home_stock/list/add", "add_to_shopping_list", {"quantity": 0}, "refusé"),
    ("home_stock/list/add", "add_to_shopping_list", {"quantity": -1}, "refusé"),
    ("home_stock/list/add", "add_to_shopping_list", {"free_text": "x" * 300}, "refusé"),
    ("home_stock/movement/correct", "correct_movement", {"movement_id": 0}, "refusé"),
    ("home_stock/meal/correct", "correct_meal", {"meal_id": -3}, "refusé"),
    ...
]

async def test_neither_surface_is_weaker_than_the_other(hass, cas):
    """Un refus d'un seul côté n'est pas une asymétrie mineure : c'est une
    porte dérobée dans la validation, et elle s'ouvre toujours du côté qu'on
    n'a pas testé."""
```

- [x] **Step 2: Écrire les tests des six services**

```python
async def test_add_to_shopping_list_accepts_a_product_or_a_text(hass):
async def test_add_to_shopping_list_is_the_voice_door(hass):
    """Une charge minimale — juste un texte — doit passer : « Bleuenn,
    ajoute du beurre à la liste »."""
async def test_refresh_shopping_list_returns_nothing_and_writes(hass):
async def test_query_shopping_list_answers_without_creating_an_entity(hass):
    """`SupportsResponse.ONLY`, comme `query_stock`."""
async def test_query_shopping_list_groups_by_aisle(hass):
async def test_read_receipt_retries_the_last_failed_one_when_given_nothing(hass):
async def test_read_receipt_on_an_unknown_id_says_so_in_french(hass):
async def test_correct_movement_service_matches_the_websocket(hass):
async def test_correct_meal_service_refuses_a_started_dish(hass):
async def test_services_yaml_documents_every_new_field(hass):
    """Un champ accepté par le schéma et absent de `services.yaml` est un
    champ que l'interface ne montrera jamais. Le test compare les deux."""
```

- [x] **Step 3 → 5: Rouge, code, vert**

Run: `./scripts/test.sh tests/test_services_shopping_list.py tests/test_services_correction.py tests/test_surface_parity.py -q --timeout=60`
Expected: FAIL puis PASS.

- [x] **Step 6: Suite Python complète**

Run: `./scripts/test.sh -q --timeout=120`
Expected: tout vert. **C'est le dernier point de contrôle avant le front** : à partir d'ici, plus aucune tâche ne touche à Python sauf la documentation.

- [x] **Step 7: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: six services, and a contract test that neither surface is the weaker one"
```

---

## Task 21: L'écran « Liste »

**Files:**
- Create: `frontend/src/ecrans/liste.ts`, `frontend/tests/liste.test.ts`
- Modify: `frontend/src/panneau.ts`
- Test: `frontend/tests/panneau.test.ts`

**Interfaces:**
- `<home-stock-liste>` — propriétés `donnees`, `connexion`, `file`, `enAttente`.
- `Ecran` gagne `'liste'` ; la barre de navigation expose **« Liste »**.
- Écritures par la file hors ligne : `home_stock/list/check`, `uncheck`, `add`, `remove`.

**Ce qu'on y fait.** Les lignes ouvertes, **groupées par rayon dans l'ordre du magasin**, avec quantité et origine. Cocher en **un** appui. Ajouter un produit (recherche catalogue) ou un texte libre. Les cochées **se replient en bas**. Un bandeau « *n* lignes, ≈ 62 € ».

**Contraintes de rendu, inchangées depuis le lot 1** : 412 × 915 et 1280 × 800, cibles tactiles **≥ 48 px**, contraste **≥ 4,5:1**, aucun débordement horizontal, **aucun geste**, tout au bouton.

**Cocher est un appui, pas deux.** Le double appui du lot 2 protège les gestes **destructifs** (cocher une tâche de maintenance, supprimer). Cocher une ligne de courses se défait en un appui — c'est un bit, réversible sur place.

- [x] **Step 1: Écrire les tests**

```ts
it('groupe les lignes par rayon, dans l’ordre du magasin', ...)
it('affiche l’origine de chaque ligne en clair', ...)     // « sous le seuil · dîner de jeudi »
it('affiche « ce qu’il faut » quand aucune quantité n’est connue', ...)
it('coche une ligne en un seul appui', ...)
it('replie les lignes cochées en bas et les garde décochables', ...)
it('ajoute un produit du catalogue', ...)
it('ajoute un texte libre quand aucun produit ne dépasse le seuil', ...)
it('retire une ligne sans la supprimer', ...)
it('affiche le bandeau « n lignes, ≈ 62 € » et dit que c’est une estimation', ...)
it('n’affiche jamais deux fois la même donnée sur le même écran', ...)
it('passe toutes ses écritures par la file hors ligne, avec une clé', ...)
it('reste utilisable hors ligne : une ligne cochée le reste à l’écran', ...)
it('affiche une liste vide sans erreur et dit quoi faire', ...)
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test -- liste`
Expected: FAIL

- [x] **Step 3: Écrire l'écran et le brancher**

`liste.ts` en français (identifiants et commentaires), sur le modèle de `panier.ts` : `ecrire(type, charge)` qui délègue à `FileAttente`. Dans `panneau.ts` : import, `'liste'` **en fin** de l'union `Ecran`, bouton de navigation **en fin** de la barre.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test`
Expected: PASS — 405 tests + les nouveaux.

- [x] **Step 5: Commit**

```bash
git add frontend/src/ecrans/liste.ts frontend/src/panneau.ts frontend/tests/
git commit -m "feat: the list screen, in the order of the shop one is standing in"
```

---

## Task 22: L'écran « Ticket »

**Files:**
- Create: `frontend/src/ecrans/ticket.ts`, `frontend/tests/ticket.test.ts`
- Modify: `frontend/src/panneau.ts`

**Interfaces:**
- `<home-stock-ticket>` — photographier ou choisir une image, l'état de lecture, les lignes lues **face aux** lignes de panier, l'écart au total, « Appliquer » **en deux appuis** avec le nombre de contrepassations annoncé.
- Le téléversement va sur `/api/media_source/local_source/upload` avec `media_content_id = media-source://media_source/local/home_stock/receipts`, puis le `media_content_id` rendu part dans `home_stock/receipt/submit` **par la file hors ligne**.

**« Ticket » ne s'atteint pas par un bouton nu.** On y entre depuis la session ou depuis un **bandeau de ticket en attente** — comme `recette` et `validation` au lot 3, on y entre par un contexte. Le garde-fou du lot 1 sur le rangement en attente s'applique à cette cible comme aux autres.

**Le téléversement exige un compte administrateur** : le foyer n'en a qu'un, et un **403 s'affiche en français** au lieu de laisser tourner un rond. La vue de Home Assistant plafonne à 20 Mo et refuse tout ce qui n'est pas `image/*` — un refus de sa part est affiché tel quel, traduit.

- [x] **Step 1: Écrire les tests**

```ts
it('affiche « aucune entité de lecture configurée » plutôt qu’un bouton mort', ...)
it('téléverse la photo puis envoie le media_content_id', ...)
it('affiche un 403 en français et conserve la photo dans la file', ...)
it('affiche l’état de lecture : en attente, lu, échoué', ...)
it('affiche l’erreur du modèle en français, telle qu’elle est stockée', ...)
it('met les lignes lues face aux lignes de panier', ...)
it('rapproche une ligne en un appui, et l’ignore en un appui', ...)
it('affiche l’écart au total quand il dépasse 2 %', ...)
it('n’affiche aucun écart quand la somme tombe juste', ...)
it('demande deux appuis pour appliquer', ...)
it('annonce le nombre de contrepassations avant d’appliquer', ...)
it('dit « aucun mouvement déjà écrit » quand il n’y en a pas', ...)
it('laisse les lignes non rapprochées visibles et propose de scanner', ...)
it('ne propose jamais de créer un article depuis un libellé de caisse', ...)
it('permet de réessayer une lecture échouée', ...)
it('n’ajoute pas de hauteur : un bandeau REMPLACE un bloc, il ne s’ajoute pas', ...)
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run (depuis `frontend/`) : `npm test -- ticket` puis `npm test`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/ecrans/ticket.ts frontend/src/panneau.ts frontend/tests/ticket.test.ts
git commit -m "feat: the receipt screen, from the photo to the applied prices"
```

---

## Task 23: Les quatre écrans modifiés

**Files:**
- Modify: `frontend/src/ecrans/panier.ts`, `session.ts`, `journal.ts`, `reglages.ts`
- Test: `frontend/tests/panier.test.ts`, `session.test.ts`, `journal.test.ts`, `reglages.test.ts`

**Ce qui change, écran par écran.**

| Écran | Ce qui change |
|---|---|
| **Panier** | Total « dont estimé », compteur « *n* hors liste » (un appui les isole), progression « 12 / 17 de la liste », kilocalories du panier **en second rang** |
| **Courses** | Magasin en pastilles **réelles** (`store.id`, plus une `list[str]`), « emporter la liste », et à la clôture « photographier le ticket » |
| **Journal** | Détail d'une ligne, « Corriger » en **deux appuis**, contrepassation affichée **sous la ligne barrée** |
| **Réglages** | Ordre des rayons **par magasin**, fusion de magasins, lignes récurrentes, entité `ai_task`, taille du dossier des tickets |

**Le journal ne cache jamais une erreur.** Une ligne corrigée reste **visible**, barrée, sa contrepassation juste en dessous. C'est ce qui permet de comprendre, six mois plus tard, pourquoi une journée porte une valeur négative.

**Le détail dit ce que la correction va faire, en clair, AVANT** : « Annule 200 g de Pâtes — 310 kcal, 0,42 € — et remet 200 g dans le lot du 2026-08-14 ». Une opération irréversible qui ne s'annonce pas est une opération qu'on déclenche par erreur.

- [x] **Step 1: Écrire les tests**

```ts
// panier.test.ts
it('dit combien du total est estimé', ...)
it('signale les lignes sans prix sans les compter dans le total', ...)
it('compte les lignes hors liste et permet de les isoler en un appui', ...)
it('affiche la progression sur la liste', ...)
it('affiche les kilocalories du panier au second rang, jamais au premier', ...)

// session.test.ts
it('affiche les magasins comme des pastilles portant un identifiant', ...)
it('propose « emporter la liste » quand la liste n’est pas vide', ...)
it('propose « photographier le ticket » à la clôture', ...)
it('accepte encore un magasin saisi à la main', ...)   // non-régression lot 1

// journal.test.ts
it('ouvre le détail d’une ligne en un appui', ...)
it('annonce exactement ce que la correction va faire', ...)
it('demande deux appuis pour corriger', ...)
it('laisse la ligne corrigée visible et barrée', ...)
it('affiche la contrepassation juste en dessous', ...)
it('refuse de proposer « Corriger » sur une ligne déjà corrigée', ...)
it('refuse de proposer « Corriger » sur un transfert ou une conversion', ...)
it('propose « corriger le repas » sur un mouvement cuisiné', ...)

// reglages.test.ts
it('réordonne les rayons magasin par magasin', ...)
it('dit combien de sessions manquent avant que l’ordre soit fiable', ...)
it('montre qu’un rayon épinglé contredit l’ordre appris', ...)
it('propose « reprendre l’apprentissage » sur un rayon épinglé', ...)
it('fusionne deux magasins en deux appuis', ...)
it('refuse la fusion pendant une session ouverte, en français', ...)
it('gère les lignes récurrentes', ...)
it('affiche l’entité ai_task, ou dit qu’il n’y en a pas', ...)
it('affiche la taille du dossier des tickets', ...)
```

- [x] **Step 2 → 4: Rouge, code, vert**

Run (depuis `frontend/`) : `npm test`
Expected: FAIL puis PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/ecrans/ frontend/tests/
git commit -m "feat: the cart tells its guesses, and the journal can be corrected"
```

---

## Task 24: Vérification de rendu (39 → 41), documentation, et construction du bundle

**Files:**
- Modify: `frontend/outils/verifier-rendu.mjs`
- Modify: `docs/exploitation.md`
- Modify: `custom_components/home_stock/panel/home-stock-panel.js` *(artefact de build)*

**C'est la seule tâche autorisée à lancer `npm run build`.** `custom_components/home_stock/` est bind-monté dans le conteneur Home Assistant : le bundle construit est servi **tel quel**. Un vérificateur ne déploie pas ; un build, si.

- [x] **Step 1: Ajouter les deux scénarios**

**En fin** de `SCENARIOS`, aux deux formats (412 × 915 et 1280 × 800) :

```js
{
  nom: 'Liste (quatre rayons, deux origines, trois cochées repliées)',
  fixture: …,                       // une liste chargée : ruptures, planning, manuel, récurrent
  actions: [{ type: 'dispatch-evenement', nom: 'ouvrir-liste', detail: {} }],
  ecranAttendu: 'home-stock-liste',
},
{
  nom: 'Ticket (lu, deux lignes non rapprochées, écart au total, application armée)',
  fixture: …,                       // un ticket `read`, un panier de dix lignes
  actions: [
    { type: 'dispatch-evenement', nom: 'ouvrir-ticket', detail: { receipt_id: 1 } },
    { type: 'clic', selecteur: '.appliquer' },        // premier appui : arme
  ],
  ecranAttendu: 'home-stock-ticket',
},
```

`ecranAttendu` est **obligatoire** sur les deux : c'est ce qui fait échouer le scénario quand l'écran n'est jamais atteint, au lieu de mesurer un écran par défaut et de le déclarer vert.

- [x] **Step 2: Lancer le vérificateur, sur les sources**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs`
Expected: **41 scénarios**, tous verts. Le bundle est construit **en mémoire** depuis `src/` : ce script ne déploie rien.

Ce qu'il vérifie et qu'aucun test unitaire ne voit : débordement horizontal, cible tactile < 48 px, contraste < 4,5:1, texte tronqué, écran jamais atteint.

- [x] **Step 3: Écrire la documentation d'exploitation**

Dans `docs/exploitation.md`, **en fin**, quatre sections :

1. **Liste de courses.** Elle appartient au composant. Une ligne posée à la main est respectée ; une ligne de rupture disparaît quand la rupture disparaît. **Cocher veut dire « je l'ai », jamais « c'est en stock »** : une ligne cochée sans achat réel **revient** à la synchronisation suivante, une fois la session close — même contrat que `todo.maintenance`. L'entrée en stock reste le scan et le rangement.
2. **Ticket de caisse.** Choisir une entité `ai_task` dans les options ; une entité sans pièces jointes est refusée au réglage. Le dossier `media/home_stock/receipts` doit exister. Le téléversement **exige un compte administrateur**. **Jamais sous `www/`.** **La photo n'est pas supprimée toute seule** : c'est la pièce justificative de tout ce que le modèle en a tiré. Le nettoyage est un geste du propriétaire ; les réglages affichent la taille du dossier.
3. **Corriger une ligne du journal.** Depuis l'écran Journal, deux appuis. Une correction s'impute au **jour de la correction**, pas au jour de l'erreur : la barre d'hier ne bouge pas, celle d'aujourd'hui porte une entrée négative nommée « Correction ». Un mouvement ne s'annule qu'**une** fois. Un repas validé se corrige **en bloc**, et pas si le plat est entamé.
4. **Statistiques à supprimer, une fois.** `sensor.home_stock_kcal_total`, `cost_total` et `cost_waste_total` passent en `state_class: TOTAL`. Home Assistant ouvre un `repair` « la classe d'état a changé » : le résoudre en **supprimant les statistiques de ces trois entités** (Outils de développement → Statistiques). **Le composant ne supprime jamais de statistiques tout seul.** Le journal SQLite contient toute l'histoire et les graphes du panneau se recalculent depuis lui ; seules les statistiques natives repartent. Le lot 2 l'a déjà payé sur les deux premiers : c'est la **seconde et dernière** fois.

- [x] **Step 4: Construire le bundle**

Run (depuis `frontend/`) : `npm run build`

Puis vérifier que l'écriture est bien celle attendue :

```bash
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain custom_components/home_stock/panel/
```

Un seul fichier doit avoir changé : `home-stock-panel.js`.

- [x] **Step 5: Vérifier le bundle réellement en place**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs --deploye`
Expected: les mêmes 41 scénarios verts, cette fois sur le bundle construit.

- [x] **Step 6: Lancer les trois suites une dernière fois**

```bash
./scripts/test.sh -q --timeout=120
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert — Python, front, et 41 scénarios.

- [x] **Step 7: Commit**

```bash
git add frontend/outils/verifier-rendu.mjs docs/exploitation.md custom_components/home_stock/panel/home-stock-panel.js
git commit -m "chore: render checks for the two new screens, docs, and the built panel"
```

---

## Ce que ce plan ne fait pas

Rappel, pour qu'aucune tâche n'aille les chercher :

- **Corriger un `cooked` ou une `conversion` à l'unité.** Ces motifs viennent par blocs transactionnels ; `correct_meal` couvre le seul bloc qui arrive vraiment. Une conversion d'unité fautive se refait par une conversion inverse.
- **Corriger un repas dont le plat est entamé.** Reconstituer un lot partiellement mangé suppose de savoir qui a mangé quoi. Refusé **explicitement**, avec le message qui dit quoi faire.
- **Créer un article depuis une ligne de ticket.** Un libellé de caisse abrégé est exactement la matière qui a produit 35 doublons dans Grocy. Le ticket **relit des prix** ; il n'alimente pas le catalogue.
- **Purger automatiquement les photos de tickets.** La photo est la pièce justificative de tout ce qui en a été tiré. Effacer la preuve automatiquement est le contraire de ce qu'un journal en ajout seul cherche à garantir.
- **Supprimer les statistiques des trois capteurs.** Le composant ne le fait jamais. C'est un geste du propriétaire, écrit dans `docs/exploitation.md`.
- **Une liste par magasin**, et **plusieurs personnes qui font les courses ensemble**. Une seule session ouverte à la fois, invariant tenu par index depuis le lot 1 ; le foyer suit une personne et fait une course par semaine.
- **Le budget mensuel et son alerte de dépassement.** `cost_today` et les statistiques existent ; un objectif est une décision du foyer, pas une donnée du garde-manger. Groupé avec les objectifs nutritionnels différés au lot 2.
- **Une vue HTTP maison pour les images.** Prévue au lot 0, jamais écrite, et le lot 4 confirme qu'elle ne le sera pas ici : le téléversement passe par la vue de Home Assistant. La question des images d'articles et de recettes se posera une seule fois, au lot 7.
- **Contribuer des prix vers Open Prices.** Demande un compte, ne sert pas la maison. Décision du lot 1, inchangée.
- **Les tablettes murales, la vue dense PC et le vocal Bleuenn** — lot 6. `todo.home_stock_shopping` et `home_stock.query_shopping_list` sont déjà les deux surfaces dont le vocal aura besoin.
- **La reprise du stock, de l'historique et des recettes Grocy**, et l'arrêt du conteneur — lot 7. `corrects_id` et la contrepassation donnent enfin le moyen de réparer une reprise qui se serait trompée, sans repartir d'une base vide.
- **Écrire vers Grocy.** Jamais. L'import est à sens unique, décision du lot 0.
- **Déployer.** Redémarrer Home Assistant, recharger l'intégration, appliquer `m006` sur la vraie base et résoudre le `repair` des statistiques restent les gestes du **propriétaire**. Ce plan ne touche pas l'instance vivante.
