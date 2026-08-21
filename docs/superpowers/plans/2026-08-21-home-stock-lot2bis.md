# home_stock — Lot 2bis : objectifs nutritionnels, portion manuelle et tri des déchets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Poser un plafond journalier sur ce qu'on mange et le voir céder ; corriger à la main la portion d'un produit que la médiane apprise devine mal ; lire le bac de tri d'un emballage au moment exact où on le jette.

**Architecture:** Trois sujets ramassés, aucun mécanisme nouveau. Les objectifs vivent dans les **options de l'entrée**, sont comparés par un module de domaine pur (`domain/goals.py`) aux totaux déjà calculés par `application.summary()`, et se lisent sur **un** `binary_sensor` dont l'attribut porte la liste. La portion manuelle est **une colonne** sur `product`, en tête de l'ordre de priorité que `websocket_api.product_get` est le seul endroit du dépôt à décider. Le matériau d'emballage se lit **à la volée** dans `article.off_raw` — après avoir réparé `off/client.FIELDS`, qui ne l'a jamais demandé.

**Tech Stack:** Python 3.13 / Home Assistant 2026.8.2 / SQLite (WAL, écrivain unique) / `pytest-homeassistant-custom-component` — TypeScript / `lit` / rollup / vitest / playwright-core.

**Spec:** `docs/superpowers/specs/2026-08-21-home-stock-lot2bis-design.md`

## Global Constraints

Ces règles lient **toutes** les tâches.

- **Nommage.** Code, schéma et identifiants Python **en anglais** ; textes affichés **en français**. Le front garde ses identifiants et ses commentaires **en français**, comme aux lots 0 à 5.
- **Plafonds seulement, jamais de plancher.** Un objectif est un maximum. C'est ce qui rend impossible **par construction** l'alerte de 4 h 01 sur une journée vide : la journée vaut zéro partout, donc rien n'est dépassé, donc le capteur est `off`. Aucune garde « la journée n'est pas vide » ne doit être écrite — elle prouverait qu'on a laissé passer un plancher.
- **Un objectif atteint exactement n'est pas dépassé** : `>`, jamais `>=`.
- **Le calcul lit `coordinator.data["today"]`, jamais une entité.** Cinq des neuf capteurs quotidiens sont créés éteints ; un objectif posé sur l'un d'eux doit fonctionner sans qu'on l'allume. Ni `domain/goals.py`, ni `binary_sensor.py`, ni le blueprint ne référencent un capteur par nutriment.
- **La fenêtre longue est la moyenne des sept journées CLOSES** (J-7 … J-1), la journée courante **exclue**, divisée par **sept journées** — pas par 168 heures. L'inclure ferait clignoter le capteur chaque matin.
- **La frontière de journée est 4 h** (`FOOD_DAY_START_HOUR = 4`), via `domain/foodday.py` (`food_day_bounds`, `bounds_of_food_day`, `food_day_of`) et le rendez-vous existant `_schedule_food_day_rollover`. **Aucun calcul de date locale** dans le code de ce lot.
- **Bornes de portion manuelle**, reprises à l'identique du lot 2 : `]0 ; 5000]` (`MAX_SERVING`), jamais supérieure au poids net connu (le **plus grand** `net_quantity` parmi les articles du produit), et **uniquement** pour un produit suivi en `g` ou en `ml`.
- **Aucune des deux surfaces n'a le droit d'être la plus faible.** Le validateur vit dans `validators.py`, jamais dans `websocket_api.py` : un futur service `home_stock.*` n'aura rien à réécrire. Le front duplique la borne pour refuser avant l'aller-retour, **jamais** comme seul contrôle.
- **`Database._lock` n'est pas réentrant.** Deux `db.write()` imbriqués **figent le processus sans lever**. Réutiliser `_consume_within` / `_add_stock_within` de `application.py`, n'en créer aucune variante, et mettre `--timeout=60` sur tout test qui touche à une écriture.
- **Jamais de `SELECT b.*`** dans `custom_components/` : un test épingle le motif **littéralement**, sans distinguer les tables. N'aliaser **aucune** table en `b`.
- **Rien ne touche l'instance vivante.** Pas de `docker compose`, pas de redémarrage, pas de rechargement de l'intégration, pas de lecture du jeton dans `.mcp.json`, aucune écriture dans `/opt/nivuus/HomeAssistant/config/`.
- **Aucun test ne sort sur le réseau.** Open Food Facts n'est joint que par un transport injecté et des fixtures ; ce lot ne capture aucune fiche en ligne.
- **`npm run build` est interdit** avant la dernière tâche. `custom_components/home_stock/` est bind-monté dans le conteneur Home Assistant : le bundle construit est servi tel quel. Une seule construction, à la toute fin.
- **Commandes de test.** Python : `./scripts/test.sh` depuis la racine du dépôt (image Docker alignée sur HA 2026.8.2). Front : `npm test` puis `node outils/verifier-rendu.mjs`, **depuis `frontend/`**. État de départ : **1390** tests Python, **405** tests front, **39** scénarios de rendu, tout vert.

---

## Migration : ce lot prend `m007`, et le trou est assumé

Tranché, et à ne pas rediscuter tâche par tâche :

- L'état réel de `storage/migrations/` est `m001_initial` … `m005_equipment`. **Le lot 4, écrit en parallèle, prend `m006_shopping`.** Ce lot prend donc **`m007_portion.py`, `VERSION = 7`**, et ne bouge pas.
- Dans ce worktree, `m006` n'existe pas : la suite est `[1, 2, 3, 4, 5, 7]`. `apply_migrations()` n'applique que les versions strictement supérieures à `MAX(version)` : **un trou est sans conséquence**, seul un **dépassement** en aurait (une base passée en 6 par ce lot ne verrait jamais le `m006` du lot 4, sautée définitivement et en silence). Prendre 7 est donc le choix sûr.
- `tests/storage/test_migrations.py::test_migration_versions_are_contiguous_from_one` est **assoupli** en Task 3, exactement d'un cran : versions **uniques**, **strictement croissantes**, commençant à 1, et **le seul numéro manquant toléré est 6**. Tout autre trou, tout doublon, toute régression restent refusés. Le test porte un commentaire `# À RESSERRER AU MERGE DU LOT 4`.
- `test_migration_modules_are_named_after_their_version` reste **strict** : `m007_portion.VERSION == 7`.

**Consigne de merge (bloquante, à exécuter au merge du lot 4, pas avant) :**

1. Relire `storage/migrations/__init__.py` après fusion. Si `m006_shopping` est présent, la suite est `[1…7]` : **remettre le test de contiguïté dans sa forme stricte** (`versions == list(range(1, len(versions) + 1))`) et supprimer le commentaire.
2. Si le lot 4 n'a **pas** été fusionné, ou a pris un autre numéro : renommer `m007_portion.py` en `m00N_portion.py` **et** sa constante `VERSION` **ensemble**, dans le même commit, puis remettre le test strict. Un module renuméroté à moitié est exactement l'erreur que le test de nommage existe pour attraper.
3. Ce lot est le **plus indépendant** des migrations en attente : sa migration n'a **aucun hook `apply()`** et ne dépend d'aucune colonne des lots 3, 4 ou 5. C'est donc lui qui cède le numéro si l'ordre de merge change, jamais l'inverse.

## Fichiers à fort risque de conflit avec le lot 4

Dans **tous** ces fichiers : **ajouter en fin de liste / en fin de dict / en fin de tableau, ne jamais réordonner** ce qui existe, ne jamais reformater une ligne voisine. Un conflit de fusion sur un ajout en queue se résout en gardant les deux ; un conflit sur un réordonnancement se résout à la main, mal.

`storage/migrations/__init__.py` · `const.py` · `sensor.py` · `binary_sensor.py` · `coordinator.py` · `application.py` · `websocket_api.py` · `services.py` et `services.yaml` · `validators.py` · `config_flow.py` · `translations/fr.json` et `translations/en.json` · `frontend/src/panneau.ts` · `frontend/outils/verifier-rendu.mjs` · `docs/exploitation.md`

---

## Structure des fichiers

**Python — créés**

| Fichier | Responsabilité |
|---|---|
| `custom_components/home_stock/domain/goals.py` | Pur : compare des totaux à des plafonds, rend les dépassements triés. |
| `custom_components/home_stock/off/packaging.py` | Pur : lit `packagings` / `packaging_tags` dans un `off_raw`, rend des bacs. |
| `custom_components/home_stock/storage/migrations/m007_portion.py` | Une colonne : `product.manual_portion`. Aucun `apply()`. |
| `blueprints/automation/home_stock/objectifs_bleuenn.yaml` | Blueprint livré, jamais installé par le composant. |

**Python — modifiés**

| Fichier | Ce qui change |
|---|---|
| `off/client.py` | `FIELDS` gagne `packagings,packaging_tags` |
| `const.py` | `CONF_GOALS`, `GOAL_NUTRIENTS`, `MAX_GOAL`, `GOAL_WINDOW_DAYS`, `RECYCLING_BINS` |
| `validators.py` | `goal_quantity()`, `check_manual_portion()` |
| `storage/migrations/__init__.py` | `m007_portion` dans `MIGRATIONS` |
| `storage/repositories.py` | `manual_portion` dans `PRODUCT_FIELDS`, `article_off_raw()` |
| `application.py` | `summary()` publie `week_mean` |
| `coordinator.py` | Publie `data["goals"]` depuis les options |
| `binary_sensor.py` | `NutritionGoalsBinarySensor` |
| `config_flow.py` | Neuf champs d'options facultatifs |
| `websocket_api.py` | `product/get` étendu, `manual_portion` dans `PRODUCT_EDITABLE`, `goals` dans `journal/day` |
| `translations/fr.json`, `translations/en.json` | Le capteur, les neuf libellés d'objectif |
| `docs/exploitation.md` | Section « Lot 2bis » |

**Front — créés**

| Fichier | Responsabilité |
|---|---|
| `frontend/src/tri.ts` | Libellés français des bacs. Pur, comme `dlc.ts`. |

**Front — modifiés**

| Fichier | Ce qui change |
|---|---|
| `frontend/src/portion.ts` | « Ma portion » quand la source est `manual` |
| `frontend/src/ecrans/consommation.ts` | La consigne de tri, aux deux conditions |
| `frontend/src/ecrans/catalogue.ts` | Le champ « Ma portion » |
| `frontend/src/ecrans/journal.ts` | Une ligne par objectif réglé |
| `frontend/outils/verifier-rendu.mjs` | Deux scénarios de plus |

---

## Task 1: Demander l'emballage à Open Food Facts

**Pourquoi en premier.** Sans ce champ, toute la partie emballage est mort-née. La note du lot 1 (« matériau d'emballage conservé gratuitement dans `off_raw` ») est **fausse** : `off/ingest.py` écrit `off_raw = json.dumps(product)` où `product` est la réponse **déjà filtrée** par le paramètre `fields=` de la requête, et `off/client.FIELDS` (ligne 28) ne demande ni `packagings` ni `packaging_tags`. Vérifié : `grep -c packaging tests/fixtures/off/*.json` rend **0** sur les trois fichiers. **Aucun rattrapage rétroactif n'est possible** — seuls les articles rescannés ou resynchronisés après cette version porteront l'information, et un `apply()` qui relirait `off_raw` ne trouverait rien, sur aucun article, jamais. Ce lot le dit, et le teste comme tel.

**Files:**
- Modify: `custom_components/home_stock/off/client.py`
- Modify: `tests/fixtures/off/catalogue.json` (deux fiches, pas plus)
- Test: `tests/off/test_client.py`

**Interfaces:**
- Produit : `off.client.FIELDS` contient `packagings` et `packaging_tags`. Rien d'autre ne change : zéro requête de plus, quelques centaines d'octets par fiche, très loin du plafond `MAX_OFF_RAW_BYTES` de 256 kB.

- [ ] **Step 1: Écrire les tests**

Dans `tests/off/test_client.py`, étendre la boucle de `test_the_requested_fields_are_the_ones_the_mapping_reads` avec `"packagings"` et `"packaging_tags"` (**ajouter en fin de tuple**, ne pas réordonner), puis ajouter à la fin du fichier :

```python
def test_the_packaging_fields_are_asked_for_by_name():
    """La donnée d'emballage n'est PAS gratuite : `off_raw` ne contient que ce
    que `fields=` a demandé. Retirer ces deux champs un jour viderait
    silencieusement la consigne de tri de tout le catalogue — sans erreur,
    sans log, sans que rien d'autre ne tombe. D'où ce test nommé."""
    from custom_components.home_stock.off.client import FIELDS

    assert "packagings" in FIELDS
    assert "packaging_tags" in FIELDS
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/off/test_client.py -q`
Expected: FAIL — `assert 'packagings' in FIELDS`

- [ ] **Step 3: Ajouter les deux champs**

Dans `custom_components/home_stock/off/client.py`, **à la fin** de la chaîne `FIELDS`, en gardant la virgule de continuation :

```python
    "image_nutrition_url,image_ingredients_url,obsolete,completeness,last_modified_t,"
    # Lot 2bis : le matériau d'emballage. Absent jusqu'ici, donc absent de tous
    # les `off_raw` déjà stockés — la consigne de tri n'apparaîtra que sur les
    # articles scannés ou resynchronisés après cette version (spec § 9.1).
    "packagings,packaging_tags"
```

- [ ] **Step 4: Enrichir deux fixtures**

Dans `tests/fixtures/off/catalogue.json`, ajouter les deux clés à **exactement deux** fiches, choisies pour couvrir les deux formes du § 9.2 :

- une fiche avec `packagings` structuré, plusieurs composants dont un pot et un étui :
  `"packagings": [{"material": "en:pp-polypropylene", "shape": "en:pot", "number_of_units": 4}, {"material": "en:cardboard", "shape": "en:sleeve"}]`
- une fiche **sans** `packagings` mais avec `"packaging_tags": ["en:glass", "fr:bocal", "en:metal-lid"]`, pour exercer le repli.

Les autres fiches restent **sans** emballage : c'est le cas majoritaire en base, et il doit rester couvert.

- [ ] **Step 5: Écrire le test qui interdit le rattrapage**

Dans `tests/off/test_client.py`, à la fin :

```python
def test_the_existing_fixtures_carry_no_packaging_which_is_the_point():
    """Les fiches déjà capturées n'ont pas d'emballage, et n'en auront jamais :
    il n'a pas été demandé au moment de la capture. Ce test fige la
    conséquence — aucune migration, aucun `apply()`, aucun backfill ne peut
    inventer cette donnée (spec § 4, amendement A1)."""
    import json
    from pathlib import Path

    fiches = json.loads(
        (Path(__file__).parent.parent / "fixtures/off/soeurs.json").read_text())
    for code, fiche in fiches.items():
        assert "packagings" not in fiche, code
        assert "packaging_tags" not in fiche, code
```

- [ ] **Step 6: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/off/ -q`
Expected: PASS. Puis `./scripts/test.sh -q` : les 1390 restent verts — un champ de plus dans `fields=` ne change aucune réponse de fixture existante.

- [ ] **Step 7: Commit**

```bash
git add custom_components/home_stock/off/client.py tests/off/test_client.py tests/fixtures/off/catalogue.json
git commit -m "fix: ask Open Food Facts for the packaging fields it was never asked for"
```

---

## Task 2: Lire un bac dans une fiche brute

**Files:**
- Create: `custom_components/home_stock/off/packaging.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/off/test_packaging.py`

**Interfaces:**
- Produit :
  - `const.RECYCLING_BINS: tuple[str, ...] = ("yellow", "glass", "household", "dropoff")`
  - `off.packaging.bins_from_raw(raw: str | None) -> dict[str, list[str]] | None` — `{"bins": ["yellow"], "materials": ["en:pp-polypropylene", "en:cardboard"]}`, ou `None`.
- Le serveur rend **les clés** et les matériaux bruts ; les phrases françaises sont l'affaire de `frontend/src/tri.ts` (Task 10).

**Discipline.** Ce module applique la défense de `serving_from_raw` : `off_raw` absent, tronqué, non-objet, ou liste contenant autre chose que des dictionnaires → `None` **sans lever**. C'est un confort d'affichage, jamais une donnée dont dépend le stock. `packagings` d'abord, repli sur `packaging_tags` **seulement** s'il est absent ou vide. **Rien de connu → rien d'affiché** : jamais de bac deviné, une consigne inventée envoie du verre dans le bac jaune avec l'assurance de l'écran.

- [ ] **Step 1: Écrire les tests**

Créer `tests/off/test_packaging.py` :

```python
"""Le matériau d'emballage, lu à la volée dans `article.off_raw`.

Aucune colonne : la donnée est lue une fois par ouverture de l'écran
« manger », sur un seul article, et n'est jamais agrégée, triée, filtrée ni
jointe (spec § 9.4).
"""
import json

from custom_components.home_stock.off.packaging import bins_from_raw


def _raw(**payload) -> str:
    return json.dumps({"product_name": "Yaourt", **payload})


def test_a_structured_packaging_yields_its_bins():
    raw = _raw(packagings=[
        {"material": "en:pp-polypropylene", "shape": "en:pot"},
        {"material": "en:cardboard", "shape": "en:sleeve"},
    ])
    assert bins_from_raw(raw) == {
        "bins": ["yellow"],
        "materials": ["en:pp-polypropylene", "en:cardboard"],
    }


def test_two_components_in_two_bins_give_two_bins():
    raw = _raw(packagings=[{"material": "en:glass"}, {"material": "en:cardboard"}])
    assert bins_from_raw(raw)["bins"] == ["glass", "yellow"]


def test_bins_are_deduplicated_by_bin_not_by_material():
    """Le pot et son étui vont dans le même bac : ce qu'on doit faire, c'est
    ouvrir UN couvercle, pas lire un inventaire."""
    raw = _raw(packagings=[{"material": "en:plastic"}, {"material": "en:cardboard"},
                           {"material": "en:pp-polypropylene"}])
    assert bins_from_raw(raw)["bins"] == ["yellow"]


def test_packaging_tags_are_the_fallback_only():
    assert bins_from_raw(_raw(packaging_tags=["en:glass", "fr:bocal"]))["bins"] == ["glass"]
    # `packagings` présent : les tags ne sont même pas regardés.
    both = _raw(packagings=[{"material": "en:glass"}], packaging_tags=["en:plastic"])
    assert bins_from_raw(both)["bins"] == ["glass"]


def test_an_empty_packagings_list_falls_back_to_the_tags():
    raw = _raw(packagings=[], packaging_tags=["en:cardboard"])
    assert bins_from_raw(raw)["bins"] == ["yellow"]


def test_an_unknown_material_is_ignored_and_the_others_survive():
    raw = _raw(packagings=[{"material": "en:unobtainium"}, {"material": "en:glass"}])
    assert bins_from_raw(raw) == {"bins": ["glass"], "materials": ["en:glass"]}


def test_nothing_known_yields_nothing_at_all():
    for raw in (_raw(packagings=[{"material": "en:unobtainium"}]),
                _raw(packaging_tags=["fr:bocal"]),        # une forme, pas un matériau
                _raw()):
        assert bins_from_raw(raw) is None


def test_anything_unusable_yields_none_without_raising():
    for raw in (None, "", "{tronqu", "[1, 2]", '"une chaine"', "{}",
                _raw(packagings="du plastique"),
                _raw(packagings=[1, 2, 3]),
                _raw(packagings=[{"shape": "en:pot"}]),   # composant sans matériau
                _raw(packaging_tags="en:glass"),
                _raw(packaging_tags=[None, 42])):
        assert bins_from_raw(raw) is None


def test_the_bins_returned_are_all_declared_in_the_constant():
    from custom_components.home_stock.const import RECYCLING_BINS

    raw = _raw(packagings=[{"material": "en:glass"}, {"material": "en:cardboard"},
                           {"material": "en:plastic-film"}])
    assert set(bins_from_raw(raw)["bins"]) <= set(RECYCLING_BINS)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/off/test_packaging.py -q`
Expected: FAIL — `ModuleNotFoundError: custom_components.home_stock.off.packaging`

- [ ] **Step 3: Écrire la constante et le module**

Dans `const.py`, **en fin de fichier** (conflit lot 4 : ajouter, ne pas réordonner) :

```python
# Les quatre destinations d'un emballage en France depuis l'extension des
# consignes de tri (2023). Le serveur rend ces clés ; les phrases françaises
# sont l'affaire du panneau (frontend/src/tri.ts).
RECYCLING_BINS: Final = ("yellow", "glass", "household", "dropoff")
```

Créer `custom_components/home_stock/off/packaging.py`. Une table `_MATERIAL_BINS: dict[str, str]` associe un préfixe de matériau normalisé à un bac : `plastic`, `pp`, `pet`, `pe`, `hdpe`, `cardboard`, `paper`, `carton`, `brick`, `metal`, `aluminium`, `steel`, `can` → `yellow` ; `glass` → `glass` ; `wood`, `ceramic` → `household` ; `battery`, `light-bulb` → `dropoff`. La résolution retire le préfixe de langue (`en:`, `fr:`) puis cherche le **premier** mot-clé de la table contenu dans le matériau — `en:pp-polypropylene` donne `yellow` sans avoir à énumérer les polymères.

L'ordre de sortie de `bins` suit **`RECYCLING_BINS`**, pas l'ordre de lecture : deux fiches décrivant le même emballage doivent rendre la même liste, sinon la ligne de l'écran « manger » change de mot d'un article à l'autre. `materials` garde en revanche l'ordre de la fiche, dédupliqué, **et ne contient que les matériaux reconnus** — un matériau ignoré ne doit pas ressortir dans une clé que le panneau pourrait afficher.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/off/test_packaging.py -q`
Expected: PASS

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Remplacer le repli `if not packagings:` par `if "packagings" not in payload:`. `test_an_empty_packagings_list_falls_back_to_the_tags` doit tomber — une liste vide est le cas réel d'une fiche Open Food Facts à moitié remplie. Remettre le code correct.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/off/packaging.py custom_components/home_stock/const.py tests/off/test_packaging.py
git commit -m "feat: read recycling bins out of a stored Open Food Facts record"
```

---

## Task 3: La colonne `manual_portion`, et deux lectures ciblées

**Files:**
- Create: `custom_components/home_stock/storage/migrations/m007_portion.py`
- Modify: `custom_components/home_stock/storage/migrations/__init__.py`
- Modify: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/storage/test_migrations.py`, `tests/storage/test_repositories.py`

**Interfaces:**
- Produit :
  - Colonne `product.manual_portion REAL` (nullable, `NULL` = « déduis-la »).
  - `repo.PRODUCT_FIELDS` gagne `"manual_portion"` — **en fin de tuple**.
  - `repo.article_off_raw(conn, article_id: int) -> str | None`
  - `repo.max_net_quantity(conn, product_id: int) -> float | None` — le **plus grand** `net_quantity` connu parmi les articles du produit, `None` si aucun.
- Aucun hook `apply()` : cette migration est purement schéma, et c'est ce qui la rend renumérotable sans risque (voir « Migration » en tête de plan).

- [ ] **Step 1: Écrire les tests de la migration**

Dans `tests/storage/test_migrations.py`, à la fin du fichier, en réutilisant les helpers déjà présents (`_migrated`, `_migrated_to`) :

```python
def test_m007_adds_the_manual_portion_column(tmp_path):
    conn = _migrated(tmp_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(product)")}
    assert "manual_portion" in columns


def test_m007_leaves_every_existing_product_undecided(tmp_path):
    """NULL n'est pas 0.0 : c'est « déduis-la ». Le jour de la migration, c'est
    100 % du catalogue — et la médiane apprise du lot 2 continue de décider."""
    conn = _migrated_to(tmp_path, version=CURRENT_VERSION - 1)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Riz', 'g')")
    conn.commit()
    apply_migrations(conn)
    assert conn.execute("SELECT manual_portion FROM product").fetchone()[0] is None


def test_m007_is_replayable(tmp_path):
    conn = _migrated(tmp_path)
    assert apply_migrations(conn) == CURRENT_VERSION
```

`_migrated_to(tmp_path, version=CURRENT_VERSION - 1)` applique tout ce qui précède `m007` sans écrire `5` en dur — le helper existant saute déjà les migrations dont la `VERSION` dépasse la borne, et le nombre reste juste le jour où `m006` arrive avec le lot 4.

Puis **assouplir d'un cran** `test_migration_versions_are_contiguous_from_one`, en remplaçant son corps :

```python
def test_migration_versions_are_contiguous_from_one():
    """Un dépassement de version saute une migration DÉFINITIVEMENT et sans
    bruit : `apply_migrations` ne redescend jamais.

    # À RESSERRER AU MERGE DU LOT 4.
    Le lot 4 (`m006_shopping`) et le lot 2bis (`m007_portion`) sont écrits en
    parallèle ; tant que le premier n'est pas fusionné, la suite locale est
    [1, 2, 3, 4, 5, 7]. Le SEUL trou toléré est le 6 : tout autre trou, tout
    doublon, toute version non croissante reste refusé. Au merge du lot 4,
    remettre `versions == list(range(1, len(versions) + 1))` et supprimer ce
    paragraphe (consigne de merge, plan du lot 2bis)."""
    versions = [module.VERSION for module in migrations.MIGRATIONS]
    assert versions[0] == 1
    assert len(set(versions)) == len(versions)
    assert versions == sorted(versions)
    assert set(range(1, versions[-1] + 1)) - set(versions) <= {6}
    assert migrations.CURRENT_VERSION == versions[-1]
```

`test_migration_modules_are_named_after_their_version` **ne bouge pas** : il reste la garde qui attrape un module renuméroté à moitié.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q --timeout=60`
Expected: FAIL — `assert 'manual_portion' in columns`

- [ ] **Step 3: Écrire la migration**

Créer `custom_components/home_stock/storage/migrations/m007_portion.py` :

```python
"""Lot 2bis: the portion this household decided on, for one product.

Schema-only, no `apply()`: there is nothing to backfill. `article.serving_quantity`
is the manufacturer's portion, `repo.learned_portion` is the median of the last
three meals — and neither is what someone typed. NULL means "work it out",
which on migration day is the whole catalogue.

Numbering: lot 4 claims m006 (shopping). If this module is renumbered, its
file name AND its VERSION move together, in the same commit.
"""
from __future__ import annotations

VERSION = 7

SQL = """
-- La portion que le foyer a fixée à la main, dans l'unité de base du produit.
-- Prime sur la médiane apprise et sur la portion d'Open Food Facts.
ALTER TABLE product ADD COLUMN manual_portion REAL;
"""
```

Dans `storage/migrations/__init__.py`, ajouter `m007_portion` **en fin** de l'import groupé **et** en fin du tuple `MIGRATIONS`. Ne rien réordonner (fichier à fort risque de conflit).

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q --timeout=60`
Expected: PASS

- [ ] **Step 5: Écrire les tests des deux lectures**

Dans `tests/storage/test_repositories.py`, à la fin :

```python
def test_manual_portion_is_writable_through_update_product(db):
    ...  # create_product puis update_fields(conn, "product", id, {"manual_portion": 45.0})
    # relire : 45.0 ; puis écrire None : la colonne redevient NULL (l'effacement).


def test_article_off_raw_returns_the_stored_record_or_none(db):
    # un article avec off_raw -> la chaîne exacte ; un article sans -> None ;
    # un article_id inconnu -> None, sans lever.


def test_max_net_quantity_is_the_largest_pack_known_for_the_product(db):
    """Un même riz existe en 500 g et en 1 kg : 800 g reste une portion
    (indigeste), pas une faute de saisie. C'est le PLUS GRAND paquet connu
    qui borne, jamais le premier trouvé ni le lot FIFO."""
    # deux articles 500 et 1000 -> 1000.0 ; aucun net_quantity connu -> None ;
    # produit sans article -> None.
```

Écrire ces trois tests en entier en reprenant les helpers de fixture du fichier (`db`, création de produit/article) plutôt qu'en inventant d'autres.

- [ ] **Step 6: Écrire les deux lectures**

Dans `repositories.py` : ajouter `"manual_portion"` **en fin** de `PRODUCT_FIELDS`, puis deux fonctions à la suite des lectures d'article existantes.

`article_off_raw` : `SELECT off_raw FROM article WHERE id = ?`, `None` si aucune ligne.
`max_net_quantity` : `SELECT MAX(net_quantity) AS m FROM article WHERE product_id = ?`, `None` si la ligne rend `NULL`.

**Piège du dépôt :** ne **jamais** aliaser une table en `b` (un test épingle littéralement le motif `SELECT b.*` dans tout `custom_components/`). Ces deux requêtes n'ont besoin d'aucun alias.

- [ ] **Step 7: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage/ -q --timeout=60`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add custom_components/home_stock/storage/ tests/storage/
git commit -m "feat: a product can carry the portion its household decided on"
```

---

## Task 4: Les deux validateurs, également forts aux deux surfaces

**Files:**
- Modify: `custom_components/home_stock/validators.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/test_validators.py`

**Interfaces:**
- Produit :
  - `const.CONF_GOALS: str = "nutrition_goals"`
  - `const.GOAL_NUTRIENTS: tuple[str, ...] = ("kcal", *MACRO_COLUMNS)` — les neuf que le lot 2 gèle dans le journal.
  - `const.MAX_GOAL: float = 20_000.0` — au-delà, c'est une faute de frappe.
  - `const.GOAL_WINDOW_DAYS: int = 7`
  - `validators.goal_quantity(value: Any) -> float` — `]0 ; MAX_GOAL]`, fini, jamais booléen. Lève `vol.Invalid`.
  - `validators.check_manual_portion(value: Any, *, base_unit: str, max_net_quantity: float | None) -> float | None` — rend la valeur normalisée, ou `None` pour l'effacement. Lève `vol.Invalid` en **français**.

**Pourquoi ici et pas dans `websocket_api.py`.** `product/update` est aujourd'hui la seule surface qui édite un produit, mais la règle du lot 1 tient : aucune des deux surfaces n'a le droit d'être la plus faible. Le validateur est écrit dans `validators.py` **précisément pour qu'un futur service n'ait rien à réécrire**. Les trois refus sont ceux de `off/mapping.plausible_serving()`, dans le même ordre — mais celui-ci **lève un message français** au lieu de rendre `None`, parce qu'ici quelqu'un a tapé quelque chose et attend qu'on lui dise pourquoi c'est refusé.

- [ ] **Step 1: Écrire les tests**

Dans `tests/test_validators.py`, à la fin :

```python
def test_a_manual_portion_is_a_number_in_the_lot_two_bounds():
    assert check_manual_portion(45, base_unit="g", max_net_quantity=500) == 45.0
    assert check_manual_portion("45,5", base_unit="ml", max_net_quantity=1000) == 45.5
    assert check_manual_portion(5000, base_unit="g", max_net_quantity=None) == 5000.0


def test_clearing_a_manual_portion_is_allowed():
    """`null` est l'effacement, pas une erreur : le produit repasse à la
    médiane apprise au rechargement suivant."""
    assert check_manual_portion(None, base_unit="g", max_net_quantity=500) is None


def test_a_manual_portion_is_refused_on_a_piece_product():
    with pytest.raises(vol.Invalid, match="pièce"):
        check_manual_portion(45, base_unit="piece", max_net_quantity=None)


def test_a_manual_portion_out_of_bounds_says_the_bound():
    for value in (0, -5, 5000.1):
        with pytest.raises(vol.Invalid, match="5000"):
            check_manual_portion(value, base_unit="g", max_net_quantity=None)


def test_a_manual_portion_bigger_than_the_biggest_pack_is_refused():
    with pytest.raises(vol.Invalid, match="1000"):
        check_manual_portion(1200, base_unit="g", max_net_quantity=1000)
    # Exactement le paquet reste plausible : une conserve individuelle.
    assert check_manual_portion(1000, base_unit="g", max_net_quantity=1000) == 1000.0


def test_a_manual_portion_is_accepted_when_no_pack_weight_is_known():
    assert check_manual_portion(80, base_unit="g", max_net_quantity=None) == 80.0


def test_a_manual_portion_refuses_what_is_not_a_number():
    for value in ("", "trente", True, [45]):
        with pytest.raises(vol.Invalid):
            check_manual_portion(value, base_unit="g", max_net_quantity=None)


def test_a_goal_is_a_positive_finite_number_under_the_cap():
    assert goal_quantity(6) == 6.0
    assert goal_quantity("6,5") == 6.5
    assert goal_quantity(MAX_GOAL) == float(MAX_GOAL)
    for value in (0, -1, MAX_GOAL + 1, True, float("inf"), "beaucoup"):
        with pytest.raises(vol.Invalid):
            goal_quantity(value)


def test_the_nine_goal_nutrients_are_the_nine_journal_columns():
    """Un objectif sur un nutriment que le journal ne fige pas ne pourrait
    jamais être comparé à quoi que ce soit."""
    assert GOAL_NUTRIENTS == ("kcal", *MACRO_COLUMNS)
    assert len(GOAL_NUTRIENTS) == 9
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_validators.py -q`
Expected: FAIL — `ImportError: cannot import name 'check_manual_portion'`

- [ ] **Step 3: Écrire les constantes et les validateurs**

Dans `const.py`, **en fin de fichier** : `CONF_GOALS`, `GOAL_NUTRIENTS`, `MAX_GOAL`, `GOAL_WINDOW_DAYS`, avec le commentaire disant que `GOAL_NUTRIENTS` est dérivé de `MACRO_COLUMNS` et non recopié.

Dans `validators.py`, réutiliser `finite_float` et `preview` déjà présents ; importer `MAX_GOAL` et `MAX_SERVING` depuis `.const`. `check_manual_portion` refuse dans l'ordre : unité (`base_unit not in ("g", "ml")`), puis lecture du nombre, puis `]0 ; MAX_SERVING]`, puis `> max_net_quantity`. Chaque message est en français et **nomme la borne** — « au plus 5000 », « au plus 1000 g, le plus gros paquet connu ».

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_validators.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/validators.py custom_components/home_stock/const.py tests/test_validators.py
git commit -m "feat: validate a manual portion and a daily goal, once, for every surface"
```

---

## Task 5: `domain/goals.py`, avant tout capteur

**Files:**
- Create: `custom_components/home_stock/domain/goals.py`
- Test: `tests/domain/test_goals.py`

**Interfaces:**
- Produit :
  - `exceeded(today: Mapping[str, Any], week_mean: Mapping[str, Any], goals: Mapping[str, Any]) -> list[dict[str, Any]]`
  - Chaque entrée : `{"nutrient": "salt", "scope": "day", "value": 8.4, "goal": 6.0, "ratio": 1.4}`, triée par `ratio` **décroissant**.
- Consomme : `const.GOAL_NUTRIENTS`. **Rien d'autre** — pas de `hass`, pas de SQLite, pas d'horloge, pas de fuseau, aucune date locale.

**Ce que ce module ne fait pas, et pourquoi.** Il ne lit **aucune entité** : cinq des neuf capteurs quotidiens sont créés éteints, et un objectif posé sur l'un d'eux doit fonctionner sans qu'on l'allume. Il n'a **aucune notion de plancher** : c'est ce qui rend impossible par construction l'alerte de 4 h 01 sur une journée vide. Et il ne calcule **aucune borne de journée** — elles arrivent déjà calculées par `domain/foodday.py`.

- [ ] **Step 1: Écrire les tests**

Créer `tests/domain/test_goals.py` :

```python
"""Comparer des totaux à des plafonds. Rien d'autre.

Un objectif est un MAXIMUM (spec § 7.5) : sur une journée vide, tout vaut
zéro, rien n'est dépassé, et il n'y a donc rien à protéger contre une alerte
à 4 h 01. Aucune garde « la journée n'est pas vide » ne doit apparaître ici —
elle prouverait qu'un plancher s'est glissé dans le lot.
"""
import pytest

from custom_components.home_stock.domain.goals import exceeded

TODAY = {"kcal": 2400.0, "salt": 8.4, "proteins": 70.0, "fiber": None}
WEEK = {"kcal": 2100.0, "salt": 5.0, "proteins": 68.0, "fiber": None}


def test_no_goal_set_means_nothing_to_report():
    assert exceeded(TODAY, WEEK, {}) == []


def test_a_day_over_its_cap_is_reported():
    assert exceeded(TODAY, WEEK, {"salt": 6.0}) == [
        {"nutrient": "salt", "scope": "day", "value": 8.4, "goal": 6.0, "ratio": 1.4}]


def test_a_goal_reached_exactly_is_not_exceeded():
    """`>`, jamais `>=` : manger exactement son objectif, c'est le tenir."""
    assert exceeded({"salt": 6.0}, {"salt": 6.0}, {"salt": 6.0}) == []


def test_the_week_mean_has_its_own_line_with_the_same_cap():
    result = exceeded({"salt": 2.0}, {"salt": 7.0}, {"salt": 6.0})
    assert [e["scope"] for e in result] == ["week"]


def test_both_windows_can_fire_at_once():
    result = exceeded({"salt": 8.4}, {"salt": 7.2}, {"salt": 6.0})
    assert [e["scope"] for e in result] == ["day", "week"]


def test_entries_are_sorted_by_ratio_descending():
    result = exceeded({"salt": 12.0, "kcal": 2400.0}, {"salt": 1.0, "kcal": 1.0},
                      {"salt": 6.0, "kcal": 2300.0})
    assert [e["nutrient"] for e in result] == ["salt", "kcal"]
    assert result[0]["ratio"] > result[1]["ratio"]


def test_an_empty_day_exceeds_nothing():
    zeros = dict.fromkeys(("kcal", "salt", "proteins"), 0.0)
    assert exceeded(zeros, zeros, {"kcal": 2000.0, "salt": 6.0}) == []


def test_a_missing_or_null_total_is_not_a_breach():
    """Un nutriment que le journal ne sait pas chiffrer n'est pas un
    dépassement : NULL n'est pas 0.0, et ce n'est pas non plus l'infini."""
    assert exceeded({"fiber": None}, {"fiber": None}, {"fiber": 30.0}) == []
    assert exceeded({}, {}, {"fiber": 30.0}) == []


def test_a_goal_set_to_none_is_no_goal_at_all():
    assert exceeded(TODAY, WEEK, {"salt": None}) == []


def test_a_goal_on_an_unknown_nutrient_is_ignored():
    """Le formulaire est fermé sur GOAL_NUTRIENTS, mais des options écrites à
    la main dans `.storage` ne doivent pas faire tomber un coordinateur."""
    assert exceeded(TODAY, WEEK, {"vitamine_x": 1.0}) == []


def test_no_entity_is_ever_read():
    """Garde-fou de lecture : ce module n'importe rien de Home Assistant."""
    import custom_components.home_stock.domain.goals as module
    source = open(module.__file__).read()
    for forbidden in ("homeassistant", "hass", "sensor.", "datetime", "ZoneInfo"):
        assert forbidden not in source
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_goals.py -q`
Expected: FAIL — `ModuleNotFoundError: custom_components.home_stock.domain.goals`

- [ ] **Step 3: Écrire le module**

Créer `custom_components/home_stock/domain/goals.py` : pour chaque nutriment de `GOAL_NUTRIENTS`, si l'objectif est un nombre strictement positif et que le total de la fenêtre est un nombre, comparer avec `>`. Deux fenêtres, `"day"` puis `"week"`. Tri final par `ratio` décroissant, puis par nom de nutriment pour que deux ratios égaux sortent dans un ordre stable. `ratio` arrondi à trois décimales, `value` et `goal` rendus tels quels.

Le seul import autorisé est `from ..const import GOAL_NUTRIENTS`.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/domain/test_goals.py -q`
Expected: PASS

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Remplacer `>` par `>=`. `test_a_goal_reached_exactly_is_not_exceeded` doit tomber. Remettre le code correct.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/domain/goals.py tests/domain/test_goals.py
git commit -m "feat: compare a day and a weekly mean against nutrition caps"
```

---

## Task 6: `week_mean` dans `summary()`

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_application_journal.py`

**Interfaces:**
- Produit : `summary()` rend une clé `week_mean` de plus, de la **même forme que `today`** moins `food_day` et `start` : `kcal`, les huit macros, `cost`, `waste_cost`, `unvalued`.
- Consomme : `domain.foodday.food_day_of`, `bounds_of_food_day`, déjà importés dans ce fichier ; `const.GOAL_WINDOW_DAYS`.

**La règle décisive.** La fenêtre couvre `[début de J-7 ; début de la journée courante[` et divise par **`GOAL_WINDOW_DAYS` journées**, pas par 168 heures. Une journée est une journée, même quand elle en dure 23 ou 25. La **journée courante est exclue** : l'inclure ferait chuter la moyenne toute la matinée puis remonter au dîner, et le capteur clignoterait chaque matin sur une grandeur censée décrire une tendance. Une dérive se lit sur des journées finies.

Coût : **une** requête agrégée de plus par rafraîchissement, sur la **même connexion** et dans le **même travail d'exécuteur** que le reste de `summary()` — pas de second `db.read()`, pas de second `async_add_executor_job`.

- [ ] **Step 1: Écrire les tests**

Dans `tests/test_application_journal.py`, à la fin. Points à couvrir :

- La moyenne exclut la journée courante : deux repas hier, un énorme aujourd'hui → `week_mean["kcal"]` ne bouge pas quand on ajoute le repas du jour.
- Sept journées, dont **une de 23 h (28 mars 2026) et une de 25 h (24 octobre 2026)** : le diviseur reste **7**, jamais une durée.
- Base sans historique → `week_mean` à zéro partout (et non `None`), le capteur pourra donc être `off`.
- La borne basse est bien `bounds_of_food_day(food_day_of(now) - 7 jours)` : un mouvement à `J-8 23:00` n'entre pas, un mouvement à `J-7 04:00` entre.
- `week_mean` porte les mêmes clés que `today` moins `food_day` et `start` (test de forme, pour qu'un capteur puisse lire l'un ou l'autre sans se demander lequel).

Réutiliser les helpers d'écriture du fichier (`_consume_within` via `manager.consume`, jamais un `db.write()` maison — `Database._lock` n'est pas réentrant).

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_application_journal.py -q --timeout=120`
Expected: FAIL — `KeyError: 'week_mean'`

- [ ] **Step 3: Écrire le calcul**

Dans `summary()`, juste après `today_totals`, sur la **même** `conn` :

```python
        # Les sept journées CLOSES qui précèdent : J-7 … J-1, la journée
        # courante exclue (spec § 7.3). Divisée par sept JOURNÉES, pas par
        # 168 heures : une journée est une journée, même quand elle en dure
        # 23 ou 25. Une dérive se lit sur des journées finies.
        week_start, _ = bounds_of_food_day(
            food_day_of(now or datetime.now(UTC), tz) - timedelta(days=GOAL_WINDOW_DAYS), tz)
        week_totals = repo.totals_between(conn, week_start, day_start)
```

et la clé `"week_mean"` dans le dictionnaire rendu, **après `today`** (ajouter en fin, ne pas réordonner — fichier à fort risque de conflit avec le lot 4), avec les mêmes arrondis que `today` : `kcal` à 1 décimale, les macros à 3, les euros à 2, `unvalued` en entier — chacun **divisé par `GOAL_WINDOW_DAYS` avant arrondi**.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_application_journal.py tests/test_application.py -q --timeout=120`
Expected: PASS

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Remplacer la borne haute `day_start` par `day_end` (donc inclure la journée courante). Le test d'exclusion doit tomber. Puis remplacer le diviseur `GOAL_WINDOW_DAYS` par `(fin - début).days` : le test des journées de 23 h / 25 h doit tomber. Remettre le code correct.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/application.py tests/test_application_journal.py
git commit -m "feat: the summary carries the mean of the seven closed food days"
```

---

## Task 7: Le capteur d'objectifs, et le blueprint qui l'annonce

**Files:**
- Modify: `custom_components/home_stock/coordinator.py`
- Modify: `custom_components/home_stock/binary_sensor.py`
- Modify: `custom_components/home_stock/translations/fr.json`, `translations/en.json`
- Create: `blueprints/automation/home_stock/objectifs_bleuenn.yaml`
- Test: `tests/test_entities.py`, `tests/test_coordinator_foodday.py`

**Interfaces:**
- `coordinator.data["goals"]` : `{"exceeded": [...], "count": n, "day_count": n, "week_count": n, "food_day": "2026-08-21"}`.
- `binary_sensor.home_stock_nutrition_goals`, « Objectifs nutritionnels » / « Nutrition goals », clé de traduction `nutrition_goals`.
- Le coordinateur appelle `domain.goals.exceeded()` avec `self.config_entry.options.get(CONF_GOALS, {})`. **Les options ne descendent jamais dans `application.py`** : c'est le coordinateur qui les connaît, et lui seul.

**Ni un attribut sur `kcal_today`** (illisible sur un capteur éteint), **ni une entité par nutriment** (neuf fois la même phrase dans le registre), **ni une entité `event`** : un dépassement est un **état** qui dure jusqu'à 4 h, pas un franchissement daté ; un `event` obligerait à retenir en base ce qui a été annoncé, donc une table, donc la migration que ce lot refuse.

- [ ] **Step 1: Écrire les tests**

Dans `tests/test_entities.py`, à la fin :

- Aucun objectif réglé → l'entité existe et vaut `off`, `count == 0`.
- Un objectif de 6 g de sel, 8,4 g mangés → `on`, attribut `exceeded` d'une entrée, `day_count == 1`, `week_count == 0`, `food_day` égal à celui de `data["today"]`.
- **Un objectif sur `fiber`, dont le capteur est créé éteint** : `binary_sensor.home_stock_nutrition_goals` passe quand même à `on`. Le test **désactive explicitement** `sensor.home_stock_fiber_today` dans le registre d'entités avant de rafraîchir, et vérifie que le résultat est identique — c'est la preuve de l'invariant, pas une redite.
- Un garde-fou de lecture : `binary_sensor.py` ne contient **aucune** occurrence de `sensor.` ni de `hass.states`.

Dans `tests/test_coordinator_foodday.py`, à la fin :

- 03:59 et 04:01 tombent dans deux journées différentes, donc dans deux valeurs différentes de `goals["food_day"]`.
- Après le rendez-vous de 4 h (`_schedule_food_day_rollover` / `_on_food_day_rollover`), un dépassement de la veille est **retombé à `off`** — sans ce rendez-vous, il resterait `on` toute la matinée.
- `coordinator.py` ne calcule aucune date locale de son côté : le test relit `data["goals"]["food_day"]` et le compare à `data["today"]["food_day"]`, qui vient de `food_day_bounds()`.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_entities.py tests/test_coordinator_foodday.py -q --timeout=120`
Expected: FAIL — `KeyError: 'goals'`

- [ ] **Step 3: Publier `goals` et créer le capteur**

Dans `coordinator._async_update_data`, après le `_read()` en exécuteur (le calcul est pur, il n'a rien à faire dans l'exécuteur) :

```python
        # Les options vivent ici, jamais dans application.py : le gestionnaire
        # ne connaît pas l'entrée de configuration, et n'a pas à la connaître.
        breaches = goals_domain.exceeded(
            data["today"], data["week_mean"],
            self.config_entry.options.get(CONF_GOALS, {}) or {})
        data["goals"] = {
            "exceeded": breaches,
            "count": len(breaches),
            "day_count": sum(1 for b in breaches if b["scope"] == "day"),
            "week_count": sum(1 for b in breaches if b["scope"] == "week"),
            "food_day": data["today"]["food_day"],
        }
```

Dans `binary_sensor.py`, une troisième classe sur le modèle exact des deux existantes (`__init__` avec la clé `"nutrition_goals"` et `ENTITY_ID_FORMAT`, `is_on` sur `count`, `extra_state_attributes` rendant `data["goals"]` privé de `count`), et l'ajouter **en fin** de la liste passée à `async_add_entities`. Compléter la docstring du module — elle annonce « Deux alertes », il y en a trois.

Dans `translations/fr.json` et `en.json`, ajouter `entity.binary_sensor.nutrition_goals.name` **en fin** de l'objet `binary_sensor`.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_entities.py tests/test_coordinator_foodday.py -q --timeout=120`
Expected: PASS

- [ ] **Step 5: Écrire le blueprint**

Créer `blueprints/automation/home_stock/objectifs_bleuenn.yaml`, calqué sur `dlc_bleuenn.yaml` — **livré dans le dépôt, jamais installé par le composant** : `home_stock` part sur HACS et n'a pas à coder l'assistant vocal d'un foyer en dur.

- Entrées : `heure` (défaut **`"21:30:00"`** — après le dîner, dernier moment où la journée est encore corrigeable), `agent` (défaut `conversation.personas_studio_home_manager`), `capteur` (défaut `binary_sensor.home_stock_nutrition_goals`).
- Déclencheur **`trigger: time`**, jamais un déclencheur d'état : un passage à `on` s'annoncerait au rafraîchissement du coordinateur, donc à n'importe quel quart d'heure, y compris à table.
- Condition : `state` du capteur à `"on"`.
- Action : `conversation.process`, phrase construite depuis l'attribut `exceeded`, **en distinguant les deux fenêtres** (« aujourd'hui » pour `day`, « en moyenne sur la semaine » pour `week`).
- **Aucune référence à un capteur par nutriment** : `state('sensor.home_stock_fiber_today')` rendrait `unavailable` sur une entité éteinte, et une automation qui ne se déclenche jamais est le pire des états.

- [ ] **Step 6: Vérifier le blueprint sans toucher à l'instance**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('blueprints/automation/home_stock/objectifs_bleuenn.yaml')); print(sorted(d['blueprint']['input'])); assert d['triggers'][0]['trigger']=='time'"`
Expected: `['agent', 'capteur', 'heure']`, aucune assertion tombée. **Ne pas** copier ce fichier dans `/opt/nivuus/HomeAssistant/config/`, ne pas recharger quoi que ce soit : l'import est le geste du propriétaire.

- [ ] **Step 7: Commit**

```bash
git add custom_components/home_stock/coordinator.py custom_components/home_stock/binary_sensor.py custom_components/home_stock/translations/ blueprints/automation/home_stock/objectifs_bleuenn.yaml tests/
git commit -m "feat: one binary sensor for nutrition goals, and a blueprint nobody installs for you"
```

---

## Task 8: Neuf champs dans le flux d'options

**Files:**
- Modify: `custom_components/home_stock/config_flow.py`
- Modify: `custom_components/home_stock/translations/fr.json`, `translations/en.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Neuf clés de formulaire `goal_kcal`, `goal_proteins`, `goal_carbohydrates`, `goal_sugars`, `goal_added_sugars`, `goal_fat`, `goal_saturated_fat`, `goal_fiber`, `goal_salt`, toutes `vol.Optional`, toutes validées par `goal_quantity`.
- Elles sont **repliées** en un seul dict `options[CONF_GOALS]` à l'enregistrement, et **dépliées** en valeurs suggérées à l'affichage. Le reste du composant ne voit jamais les neuf clés plates.

**Un champ vidé omet la clé, il n'écrit pas `0`.** Même mécanique que `CONF_RECIPE_AGENT` au lot 3, pour la même raison : « pas d'objectif » doit rester exprimable, et `0` voudrait dire « tout est un dépassement ». Les valeurs existantes sont passées en `description={"suggested_value": …}`, jamais en `default=` — un `default` réintroduirait la valeur dans un formulaire qu'on vient de vider.

- [ ] **Step 1: Écrire les tests**

Dans `tests/test_config_flow.py`, à la fin :

- Le formulaire d'options offre les neuf champs, tous facultatifs ; le soumettre **vide** n'écrit **aucun** objectif (`options.get(CONF_GOALS, {}) == {}`), et ne casse pas les options existantes (`expiration_alert_days`, `recipe_agent`, `recipe_source_key` survivent).
- Régler `goal_salt: 6` puis relire : `options[CONF_GOALS] == {"salt": 6.0}`.
- Rouvrir le formulaire : la valeur 6 est **suggérée**, pas imposée ; la vider et enregistrer **retire** la clé `salt` du dict.
- Une valeur hors bornes (`0`, `-1`, `MAX_GOAL + 1`, `"beaucoup"`) fait **échouer** le formulaire : l'entrée n'est pas enregistrée, et les options d'avant sont intactes.
- Un objectif sur un nutriment inconnu est **impossible** : le schéma est fermé sur `GOAL_NUTRIENTS` (test de forme sur les clés du schéma).

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_config_flow.py -q`
Expected: FAIL — les neuf champs sont absents du schéma

- [ ] **Step 3: Écrire le flux**

Dans `HomeStockOptionsFlow.async_step_init`, **ajouter** au schéma existant les neuf `vol.Optional(f"goal_{nutrient}")` construits par compréhension sur `GOAL_NUTRIENTS` (ne rien réordonner : fichier à fort risque de conflit). À l'entrée, replier les clés `goal_*` non vides en `user_input[CONF_GOALS]` et les retirer du dict plat avant `async_create_entry`.

Dans les deux fichiers de traduction, ajouter les neuf libellés sous `options.step.init.data.goal_*`, **en fin** de l'objet `data` : « Objectif maximal de sel par jour (g) », « Objectif maximal d'énergie par jour (kcal) », etc. — l'unité doit être dans le libellé, sinon personne ne sait s'il faut taper 6 ou 6000.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_config_flow.py -q`
Expected: PASS

- [ ] **Step 5: Vérifier que les deux traductions sont alignées**

Run: `python3 -c "
import json
fr=json.load(open('custom_components/home_stock/translations/fr.json'))
en=json.load(open('custom_components/home_stock/translations/en.json'))
a=set(fr['options']['step']['init']['data']); b=set(en['options']['step']['init']['data'])
assert a==b, a^b
print(sorted(k for k in a if k.startswith('goal_')))"`
Expected: les neuf clés, et aucune différence entre les deux langues.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/config_flow.py custom_components/home_stock/translations/ tests/test_config_flow.py
git commit -m "feat: nine optional daily caps in the options flow"
```

---

## Task 9: Les trois commandes websocket étendues

**Files:**
- Modify: `custom_components/home_stock/websocket_api.py`
- Test: `tests/test_websocket_consume.py`, `tests/test_websocket_write.py`, `tests/test_websocket.py`

**Interfaces:**

| Commande | Ce qu'elle gagne |
|---|---|
| `home_stock/product/get` | `manual_portion` (valeur brute), `portion_source` peut valoir `"manual"`, et `packaging` : `{"bins": [...], "materials": [...]}` ou `null` |
| `home_stock/product/update` | `manual_portion` dans `PRODUCT_EDITABLE` |
| `home_stock/journal/day` | `goals` : les plafonds réglés, pour que le panneau dessine la ligne d'objectif |

**Aucune commande nouvelle. Aucun service nouveau ni modifié.**

**La priorité, en un seul endroit.** `product_get` reste le **seul** endroit du dépôt qui décide d'une portion. L'ordre du lot 2 (`learned` → `serving` → `None`) devient :

```python
    suggested, source = (
        (manual,  "manual")  if manual  is not None else
        (learned, "learned") if learned is not None else
        (serving, "serving") if serving is not None else (None, None))
```

Une valeur **saisie par une personne** l'emporte toujours sur une valeur **déduite**, sinon la saisie n'a servi à rien — même règle que `article.manual_fields`, qui protège d'une resynchronisation Open Food Facts tout champ corrigé à la main.

- [ ] **Step 1: Écrire les tests**

Dans `tests/test_websocket_consume.py`, à la fin :

- Les trois existent (manuelle 45, apprise 80, `serving` 200) → `suggested_portion == 45.0`, `portion_source == "manual"`.
- `manual_portion` absente → le comportement du lot 2 est **inchangé** : 80 g appris contre 200 g déclarés → 80, `portion_source == "learned"`. (Reprendre le test existant tel quel : il ne doit pas bouger.)
- `manual_portion: null` envoyé par `product/update` → au `product/get` suivant, `portion_source` repasse à `"learned"`.
- `packaging` est rendu depuis l'`off_raw` de l'article du **lot FIFO** — celui dont `list_batches_for_product` donne déjà l'`article_id`, dans le **même travail d'exécuteur** que le reste de `product_get`.
- Aucun lot ouvert, ou `off_raw` sans emballage → `"packaging": None`, **aucune erreur**.

Dans `tests/test_websocket_write.py`, à la fin :

- `product/update` avec `manual_portion: 45` écrit la colonne ; avec `null`, l'efface.
- Sur un produit suivi à la pièce → erreur, message **français** contenant « pièce », **rien n'est écrit**.
- `manual_portion: 6000` → refusée, message nommant la borne. `manual_portion` supérieure au plus grand `net_quantity` connu → refusée. Aucun `net_quantity` connu → acceptée.
- La validation passe bien par `validators.check_manual_portion` : un test le vérifie en le monkeypatchant et en constatant qu'il est appelé — c'est ce qui interdit qu'une deuxième copie de la règle apparaisse dans `websocket_api.py`.

Dans `tests/test_websocket.py`, à la fin : `journal/day` rend `goals` = les plafonds réglés (`{}` si aucun), lus depuis les options de l'entrée, **sans** que `application.journal_day` en entende parler.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_websocket_consume.py tests/test_websocket_write.py tests/test_websocket.py -q --timeout=120`
Expected: FAIL — `KeyError: 'packaging'`

- [ ] **Step 3: Écrire les trois extensions**

1. `PRODUCT_EDITABLE` gagne `"manual_portion"` **en fin de dict** (conflit lot 4). Sa valeur est un validateur qui accepte `None` et délègue le reste ; les deux arguments contextuels (`base_unit`, `max_net_quantity`) n'étant pas disponibles dans un schéma `voluptuous`, la vérification complète se fait dans `product_update` **juste après** `_validate_fields`, en appelant `check_manual_portion` avec le `base_unit` du produit relu et `repo.max_net_quantity(conn, product_id)`. L'erreur `vol.Invalid` est renvoyée en `connection.send_error(..., "invalid_format", str(err))`, comme les autres refus de ce fichier.
2. `product_get` : lire `manual_portion` depuis le produit déjà chargé, appliquer la cascade ci-dessus, et ajouter `manual_portion` et `packaging` au résultat. `packaging` vient de `off.packaging.bins_from_raw(repo.article_off_raw(conn, article_id))`, l'`article_id` étant celui du lot FIFO déjà calculé — **une** lecture de plus, dans le même `_read`.
3. `journal_day` : ajouter un helper `_options(hass)` (`hass.config_entries.async_loaded_entries(DOMAIN)[0].options`, `{}` si aucune entrée) et enrichir le résultat de `result["goals"] = options.get(CONF_GOALS, {}) or {}` **après** l'appel au gestionnaire.

**Piège :** ne pas ouvrir de `db.write()` dans ces chemins — `product_update` utilise déjà l'écriture existante, et `Database._lock` n'est pas réentrant : deux `db.write()` imbriqués figent le processus **sans exception**. D'où le `--timeout` sur ces suites.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh -q --timeout=120`
Expected: PASS, et le compte total est monté depuis 1390 sans qu'aucun test existant n'ait été modifié — sauf les deux assouplis/étendus explicitement (contiguïté des migrations, champs demandés à Open Food Facts).

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/websocket_api.py tests/
git commit -m "feat: a manual portion wins, and the panel learns which bin the packet goes in"
```

---

## Task 10: Le tri, et le bouton « Ma portion »

**Files:**
- Create: `frontend/src/tri.ts`
- Modify: `frontend/src/portion.ts`
- Modify: `frontend/src/ecrans/consommation.ts`
- Test: `frontend/tests/tri.test.ts` (créé), `frontend/tests/portion.test.ts`, `frontend/tests/consommation.test.ts`

**Interfaces:**
- `tri.ts` : `export type Bac = 'yellow' | 'glass' | 'household' | 'dropoff'` ; `export function consigneDeTri(bacs: Bac[]): string | null` — « Bac jaune », « Bac à verre », « Ordures ménagères », « Déchèterie », et « Bac jaune et bac à verre » pour deux. `null` si la liste est vide ou ne contient aucun bac connu. Pur, comme `dlc.ts`.
- `portion.ts` : `raccourcisQuantite(restant, unite, portion, source?)` — le quatrième argument est **facultatif** et vaut `null` par défaut, pour que les appels existants restent valides.

**Deux règles d'affichage.**
- Le bouton dit « **Ma portion** (45 g) » quand `portion_source === 'manual'`, « 1 portion (45 g) » sinon : on doit voir d'où vient le chiffre proposé.
- La consigne s'affiche **sur l'écran « manger » et nulle part ailleurs**, dans **deux cas et deux seulement** : le motif choisi est `waste` (« Jeté ») ou `expired` (« Périmé ») ; **ou** la quantité choisie **vide le lot visé** (« Tout le reste », ou une saisie ≥ au reste) — le cas réel, le pot de yaourt qu'on finit. Au rangement, l'emballage est plein et part dans un placard : personne ne trie alors.
- **Une ligne, jamais une carte** : la hauteur de l'écran ne doit pas bouger selon qu'un emballage est connu ou non. **Rien de connu → rien d'affiché**, et pas de bac deviné.

- [ ] **Step 1: Écrire les tests**

`frontend/tests/tri.test.ts` : une phrase par bac ; deux bacs joints par « et » ; liste vide → `null` ; bac inconnu ignoré ; deux bacs identiques ne se répètent pas.

`frontend/tests/portion.test.ts`, à la fin : « Ma portion (45 g) » quand la source est `'manual'` ; « 1 portion (45 g) » pour `'learned'`, `'serving'`, `null` et quand l'argument est omis ; à la pièce le libellé ne change pas (une portion y vaut une pièce).

`frontend/tests/consommation.test.ts`, à la fin : consigne présente sur `Jeté`, sur `Périmé`, et sur « Tout le reste » en `Mangé` ; **absente** sur une sortie partielle en `Mangé` ; absente quand `packaging` vaut `null` ; absente quand `packaging.bins` est vide ; une saisie manuelle ≥ au reste la fait apparaître.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test`
Expected: FAIL — `Cannot find module '../src/tri'`

- [ ] **Step 3: Écrire les trois changements**

`tri.ts` : une table `LIBELLE_BAC` et la mise en phrase. Aucun import de `lit`.

`portion.ts` : ajouter le paramètre `source` et n'en faire qu'une chose — choisir entre `'Ma portion'` et `'1 portion'`. Le module **reçoit** une portion et une source, il ne se demande pas d'où elles viennent : aucune autre logique n'entre ici.

`consommation.ts` : mémoriser `packaging` et `portion_source` à la réponse de `product/get` (à côté de `this.portion`, ligne 88), passer la source à `raccourcisQuantite` (ligne 234), et rendre **une ligne** sous les boutons de quantité, aux deux conditions ci-dessus.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test`
Expected: PASS

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Remplacer la condition « la quantité vide le lot » par « la quantité égale exactement le restant » (`===` au lieu de `>=`). Le test de la saisie manuelle supérieure au reste doit tomber. Remettre le code correct.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/tri.ts frontend/src/portion.ts frontend/src/ecrans/consommation.ts frontend/tests/
git commit -m "feat: say which bin the packet goes in, at the moment it is thrown out"
```

---

## Task 11: « Ma portion » au catalogue, les objectifs au journal

**Files:**
- Modify: `frontend/src/ecrans/catalogue.ts`
- Modify: `frontend/src/ecrans/journal.ts`
- Test: `frontend/tests/catalogue.test.ts`, `frontend/tests/journal.test.ts`

**Interfaces:**
- `catalogue.ts` : `manual_portion` rejoint le type `Produit`, `CHAMPS_CATALOGUE_MODIFIABLES` (**en fin de tableau**), `Brouillon`, `brouillonDepuis` et `LIBELLE_CHAMP_NUMERIQUE` (« Ma portion »). Il passe donc par `appliquerChampNumerique`, donc par `analyserNombre`, donc par la file hors-ligne, exactement comme `min_quantity`.
- `journal.ts` : `JourJournal` gagne `goals: Record<string, number>` ; le rendu ajoute une ligne par objectif réglé.

**La saisie se fait dans le Catalogue, et seulement là.** Un raccourci « en faire ma portion » depuis l'écran « manger » serait plus proche du moment où l'on constate que la médiane se trompe, mais c'est un **second chemin d'écriture** — file hors-ligne, clé d'idempotence et tests compris — pour un geste posé une fois par produit. Hors lot.

**Convention déjà en place, à ne pas réinventer :** une saisie vide vaut `null` (`analyserNombre` + `champsModifies`). Vider « Ma portion » rend le produit à la déduction automatique. La virgule décimale est acceptée, comme partout.

Le champ est **masqué** pour un produit suivi à la pièce — la borne est aussi vérifiée côté serveur (Task 9), le front ne fait que refuser avant l'aller-retour, **jamais** comme seul contrôle. Mention sous le champ : « vide = déduite automatiquement ».

Au Journal, sous les totaux du jour : une ligne par objectif réglé — « Sel 8,4 / 6 g » — et **la même en gris** pour la moyenne des sept journées closes **quand elle dépasse**. Aucun objectif réglé → **aucune ligne**, écran identique au lot 2.

- [ ] **Step 1: Écrire les tests**

`frontend/tests/catalogue.test.ts`, à la fin : le champ est absent pour un produit `base_unit: 'piece'` ; une saisie vide produit `{manual_portion: null}` ; « 45,5 » produit `45.5` ; une saisie illisible fait échouer l'édition **entière** (`{ok: false}`), sans envoyer les autres champs ; une valeur inchangée n'est **pas** renvoyée dans `fields` ; `CHAMPS_CATALOGUE_MODIFIABLES` contient bien `manual_portion` (le filet statique du fichier).

`frontend/tests/journal.test.ts`, à la fin : trois objectifs réglés → trois lignes ; aucun objectif → aucune ligne et un rendu **identique** à celui du lot 2 ; un objectif dépassé sur la seule moyenne rend la ligne grise ; la virgule décimale est utilisée à l'affichage (`formaterNombre`).

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test`
Expected: FAIL

- [ ] **Step 3: Écrire les deux écrans**

Suivre à la lettre les mécanismes existants : `appliquerChampNumerique` pour le catalogue (rien de nouveau à écrire, juste une entrée de plus dans `LIBELLE_CHAMP_NUMERIQUE` et un appel de plus dans `champsModifies`), `formaterNombre` pour le journal.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test`
Expected: PASS — 405 tests de départ, plus les nouveaux, aucun tombé.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/ecrans/catalogue.ts frontend/src/ecrans/journal.ts frontend/tests/
git commit -m "feat: set your own portion in the catalogue, see your caps in the journal"
```

---

## Task 12: Vérification de rendu, documentation, et construction du bundle

**Files:**
- Modify: `frontend/outils/verifier-rendu.mjs`
- Modify: `docs/exploitation.md`
- Modify: `custom_components/home_stock/panel/home-stock-panel.js` (artefact de build, **dernière tâche uniquement**)

- [ ] **Step 1: Ajouter deux scénarios**

Dans `frontend/outils/verifier-rendu.mjs`, **en fin** du tableau `SCENARIOS` (fichier à fort risque de conflit avec le lot 4 : ajouter, ne jamais réordonner), et dans `SCENARIOS_MINIFIES` si les scénarios voisins y figurent :

1. **« Manger (consigne de tri) »** — fixture `home_stock/product/get` rendant `packaging: {bins: ['yellow', 'glass'], materials: [...]}`, action : choisir le motif « Jeté ». La consigne doit être visible **et la hauteur du cadre inchangée** par rapport au scénario « manger » existant : c'est une ligne, pas une carte.
2. **« Journal (trois objectifs) »** — fixture `home_stock/journal/day` rendant `goals: {kcal: 2000, salt: 6, sugars: 50}` et des totaux qui en dépassent deux. Les trois lignes doivent tenir sans débordement.

Les deux formats obligatoires restent **412 × 915** et **1280 × 800**, avec les règles automatiques du script : pas de débordement, cible tactile ≥ 62 px, contraste ≥ 5:1, aucun texte tronqué.

- [ ] **Step 2: Lancer la vérification de rendu (bundle en mémoire, aucun déploiement)**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs`
Expected: **41 scénarios**, tous verts (39 au départ + 2).

- [ ] **Step 3: Écrire la section « Lot 2bis » de `docs/exploitation.md`**

**En fin de fichier**, après « Lot 5 », trois paragraphes et pas davantage :

1. **Les objectifs se règlent dans Paramètres → Appareils et services → Garde-manger → Configurer.** Un champ vide = pas d'objectif. Ce sont des **plafonds**, jamais des planchers. Il est **inutile d'allumer les cinq capteurs éteints** : le calcul ne lit aucune entité. Le dépassement se lit sur `binary_sensor.home_stock_nutrition_goals`, jour **et** moyenne des sept journées closes.
2. **Rien n'est annoncé sans importer le blueprint** `blueprints/automation/home_stock/objectifs_bleuenn.yaml`, exactement comme pour les dates limites au lot 2. Déclencheur horaire (défaut 21:30), agent par défaut `conversation.personas_studio_home_manager`.
3. **La consigne de tri n'apparaît que sur les articles scannés ou resynchronisés après cette version** : le champ d'emballage n'avait jamais été demandé à Open Food Facts, **aucun rattrapage rétroactif n'est possible**. Une passe `home_stock.resync_off` (une quarantaine de minutes) la ramène pour tout le catalogue. Mentionner aussi le champ « Ma portion » du Catalogue et le fait qu'un champ vidé rend la main à la médiane apprise.

- [ ] **Step 4: Construire le bundle — une seule fois, ici**

Run (depuis `frontend/`) : `npm run build`

Puis vérifier ce qui a été écrit :

```bash
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain custom_components/home_stock/panel/
```

Un seul fichier doit avoir changé. **Ne rien copier dans `/opt/nivuus/HomeAssistant/config/`, ne redémarrer ni recharger quoi que ce soit** : le déploiement reste le geste du propriétaire.

- [ ] **Step 5: Vérifier le bundle réellement en place**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs --deploye`
Expected: les 41 scénarios verts, cette fois sur le bundle construit.

- [ ] **Step 6: Lancer les deux suites une dernière fois**

```bash
./scripts/test.sh -q --timeout=120
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert.

- [ ] **Step 7: Commit**

```bash
git add frontend/outils/verifier-rendu.mjs docs/exploitation.md custom_components/home_stock/panel/home-stock-panel.js
git commit -m "chore: render checks for the goal lines and the sorting hint, docs, and the built panel"
```

---

## Ce que ce plan ne fait pas

Rappel, pour qu'aucune tâche n'aille les chercher :

- **Les objectifs minimaux** (« au moins 80 g de protéines »). Un plancher n'a de sens qu'à la **clôture** de la journée : heure de clôture réglable, mémoire des annonces, donc une table, donc une migration de plus. Un mécanisme, pas un champ. Et c'est ce refus qui rend l'alerte de 4 h 01 impossible par construction.
- **Éditer les objectifs depuis le panneau.** Écrire dans les options depuis le websocket demanderait une commande, un validateur en double et un rechargement d'entrée, pour un geste annuel. Le panneau les **lit**, il ne les écrit pas.
- **Un objectif de dépense en euros.** L'argent est le sujet du lot 4 ; la mécanique de `domain/goals.py` s'y branchera telle quelle, `cost` étant déjà dans `today`.
- **« En faire ma portion » depuis l'écran « manger ».** Second chemin d'écriture, file hors-ligne et clé d'idempotence comprises, pour un geste posé une fois par produit.
- **Une portion manuelle à la pièce.** Une portion y vaut une pièce, et le raccourci « 1 » est déjà armé pour 239 des 299 produits.
- **Rattraper l'emballage des articles déjà en base.** Impossible : le champ n'a jamais été demandé, `off_raw` ne le contient pas, et aucun `apply()` ne peut l'inventer. Seule une resynchronisation le ramène.
- **Compter les emballages sortis par bac.** Demanderait de figer le bac **sur le mouvement**, comme les neuf nutriments — pas une colonne sur l'article.
- **Des consignes de tri locales.** Aucune source ouverte fiable ; l'extension des consignes couvre la France depuis 2023, la table nationale suffit.
- **Des objectifs par personne.** Le foyer ne suit qu'une personne, comme les parts du lot 2 le disent déjà.
- **Renuméroter la migration.** `m007` reste `m007` jusqu'au merge du lot 4 ; la consigne de merge en tête de plan dit quoi faire, et quand.
- **Déployer.** Redémarrer Home Assistant, importer le blueprint et lancer la resynchronisation Open Food Facts restent le geste du propriétaire.
