# home_stock — Lot 7 : migration & extinction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reprendre ce qui reste chez Grocy — le stock, les recettes, les images, le planning, la liste de courses —, le prouver par onze contrôles chiffrés dont aucun ne peut passer à vide, puis **livrer au propriétaire la procédure d'extinction du conteneur**. Le lot livre la séquence ; il ne l'exécute pas.

**Architecture:** Trois imports rejouables, tous en simulation par défaut, tous lisant une **copie** de `grocy.db` posée dans `config/`. Chacun prend **une seule** transaction et appelle des fonctions `_within(conn, …)` en dessous. La partie qui casse — le découpage du HTML des recettes, la conversion des unités, le nommage des images — est extraite dans un paquet `grocy/` **pur** : pas de `hass`, pas de réseau, pas de SQLite, testable en `pytest` nu sur les 102 descriptions réelles. Les images vont sous `media/` et se résolvent par `media_source` : le composant n'écrit **aucune** vue HTTP. Les contrôles sont un module à part, `migration_check.py`, dont chaque contrôle porte un **plancher** qui le fait échouer s'il n'a rien mesuré.

**Tech Stack:** Python 3.13 / Home Assistant 2026.8.2 / SQLite (WAL, écrivain unique) / `pytest-homeassistant-custom-component` — TypeScript / `lit` / rollup / vitest / playwright-core.

**Spec:** `docs/superpowers/specs/2026-08-21-home-stock-lot7-design.md`

**État de départ, vérifié :** `master`, **1914 tests Python**, **536 tests front**, **70 exécutions** de `node outils/verifier-rendu.mjs`, tout vert. Lots 0 à 6 et 2bis fusionnés. Migrations `m001` … `m007`.

---

## Global Constraints

Ces règles lient **toutes** les tâches. Elles sont recopiées depuis la spec et des lots précédents, et aucune n'est assouplie.

### Ce que le lot n'a pas le droit de faire

- **Le composant n'arrête JAMAIS Grocy, et ce plan ne l'arrête jamais non plus.** Arrêter un conteneur de la maison est un geste humain. Le lot **livre** la séquence d'extinction (§ 18 de la spec, tâche 20 de ce plan) sous forme d'une liste de gestes numérotés destinée au propriétaire, et **aucune tâche n'en exécute un seul** — ni `docker stop`, ni `docker compose stop`, ni le retrait d'une route Pomerium, ni une modification de crontab. Même discipline que le raccord `maintenance.jinja` du lot 5, livré dans `docs/raccord/` et jamais appliqué ; même discipline que les blueprints du lot 2, livrés et jamais importés. L'intégration livre, elle n'installe pas.
- **Le raccord du lot 5 n'est toujours pas posé, et le poser est un préalable à toute extinction.** Vérifié au 2026-08-21 : `config/custom_templates/maintenance.jinja` fait encore ses **142 lignes** avec son **bloc 3 « Piles »**, et `config/automations.yaml` **lignes 4304-4321** lit encore `todo.grocy_batteries`. Le plan le **rappelle** dans la procédure (tâche 20, geste 8) et le contrôle **C11** le mesure ; **aucune tâche ne l'applique**. Un import d'équipements non fait avant le raccord ferait *disparaître* 14 tâches de pile au lieu de les déplacer — c'est la seule dépendance d'ordre du lot 5 vers le lot 7.
- **Rien ne touche l'instance vivante.** Pas de `docker compose` (ni `up`, ni `restart`, ni `stop`, **surtout pas sur Grocy**), pas de rechargement de l'intégration, pas de lecture du jeton dans `.mcp.json`, aucune écriture dans `/opt/nivuus/HomeAssistant/config/` — ni `home_stock.db`, ni `media/`, ni `www/`, ni un `.yaml`. La vérification s'arrête à ce qui s'observe sans déranger la maison. Règle posée au lot 1 après un redémarrage non demandé du Home Assistant du foyer.
- **Grocy est en lecture seule, et seule une copie de sa base est lue.** Toute lecture de volumétrie ou d'extraction de fixture se fait sur une copie posée dans le scratchpad, ouverte en `file:…?mode=ro`. Jamais sur `/opt/nivuus/Grocy/config/data/grocy.db`. **Écriture vers Grocy : jamais** (décision du lot 0).
- **Aucun test ne sort sur le réseau.** Ni Open Food Facts, ni Unsplash, ni `grocy.allanic.me`. Les 112 références Unsplash sont laissées telles quelles dans le HTML et **jamais téléchargées**, par personne, à aucun moment.
- **`npm run build` est interdit avant la dernière tâche.** `custom_components/home_stock/` est bind-monté dans le conteneur Home Assistant : le bundle construit est servi tel quel. Une seule construction, à la toute fin, quand tout le reste est vert.

### Nommage et modèle

- **Nommage.** Code, schéma et identifiants Python **en anglais** ; textes affichés **en français**. Le front garde ses identifiants et ses commentaires **en français**, comme aux lots 0 à 6. Les libellés d'anomalies des rapports d'import sont **en français** : ils sont lus par le propriétaire pendant la bascule.
- **`m008`, `VERSION = 8`, une colonne et un index.** `batch.external_ref` (TEXT) plus `idx_batch_external_ref`, unique **partiel** sur `external_ref IS NOT NULL`. Pas d'`apply()` : il n'y a rien à rétro-remplir. Le test **strict** de contiguïté `test_migration_versions_are_contiguous_from_one` impose `[1..8]` et **ne doit pas être affaibli** : le fichier `m008_migration.py`, sa `VERSION`, son entrée dans `MIGRATIONS` et `CURRENT_VERSION` bougent dans **le même commit**.
- **`NULL` reste distinct de `0.0`.** Un prix aberrant devient `NULL` (« inconnu »), jamais `0.0` (« mesuré à zéro »). Une quantité d'ingrédient non convertible devient `NULL`, jamais une devinette.
- **`variable_amount` n'est jamais réimporté comme quantité.** Provenance seulement, dans `raw_text`. Règle du lot 3, § 18 : « il ne revient pas par la porte de derrière ». Aucune tâche n'écrit d'analyseur de « 1 cs ».
- **Aucun arrondi au stockage.** 0,08 concombre et 12,875 œufs entrent tels quels. L'arrondi est un geste d'affichage.
- **Les images vont sous `media/`, jamais sous `www/`, et le composant n'écrit AUCUNE vue HTTP.** Le `http.py` envisagé au lot 0 est **abandonné**. `recipe.image_url`, `recipe_step.image_url` et `article.image` portent un identifiant `media-source://media_source/local/…`, résolu par la commande **native** `media_source/resolve_media`.
- **Validation également forte aux deux surfaces.** Ce que le websocket refuse, le service le refuse, et réciproquement. Les bornes vivent **une seule fois** dans `validators.py` ; `test_surface_parity.py` tient le contrat.
- **Un contrôle qui ne mesure rien échoue.** Chaque contrôle porte un **plancher** : zéro lot, zéro recette, zéro image lue = **rouge**, jamais « écart : 0 ». C'est la leçon du lot 6, et c'est le cœur de ce lot.

### Pièges du dépôt

- **`Database._lock` n'est PAS réentrant.** Deux `db.write()` imbriqués **figent le processus sans lever d'exception** — pas d'échec, pas de trace, un test qui ne rend jamais la main. Les imports du lot 7 prennent **une seule** transaction chacun et appellent des fonctions `_within(conn, …)` en dessous, comme `application.py` le fait déjà. **Réutiliser `_consume_within` / `_add_stock_within` / `_correct_movement_within` existants ; n'en créer aucune variante.** Tout test qui traverse un import complet porte **`--timeout=60`**.
- **`SELECT b.*` est interdit dans tout `custom_components/`** par `tests/storage/test_repositories.py`, qui scanne le **littéral** : le test ne distingue pas les tables, donc **n'aliaser aucune table en `b`** — ni `batch`, ni `barcode`, ni une table Grocy. Les requêtes SQL de ce lot aliasent `s`, `prod`, `rec`, `pos`, `plan`, `sl`.
- **Un seul conteneur de test à la fois.** Avant chaque lancement : `docker ps --filter ancestor=home-stock-test`, et `docker kill` les surnuméraires. Plusieurs exécutions concurrentes se disputent le processeur et font passer une suite de 9 minutes à 50.
- **`movement` est en ajout seul**, avec deux triggers qui refusent `UPDATE` et `DELETE`. Un import appliqué ne s'annule pas : il se corrige par contrepassation (lot 4). D'où la simulation par défaut, partout.
- **`idempotency_key` est `UNIQUE` sur `movement`.** La rejouabilité se joue **avant** l'insertion, sur `batch.external_ref`, jamais en rattrapant une `IntegrityError`.

### Commandes de test

- **Python** : `./scripts/test.sh` depuis la **racine du dépôt** (image Docker alignée sur HA 2026.8.2 — le Python de l'hôte ne peut pas charger le plugin). Ciblé : `./scripts/test.sh tests/grocy/test_html.py -q`.
- **Front** : `npm test` puis `node outils/verifier-rendu.mjs`, **depuis `frontend/`**.
- Suites de référence à ne pas faire baisser : **1914** Python, **536** front, **70** exécutions de rendu.

---

## La cible mobile — comment ce plan la traite

Grocy est **encore utilisé** : le produit #350 « Sorbet Fraise » y a été créé le 2026-08-21 à 18 h 54, trois heures avant l'écriture de la spec. Le catalogue de `home_stock` compte 299 produits, Grocy 300 actifs. La reprise vise donc une cible qui bouge, et le plan y répond par **trois mécanismes, aucun magique** :

1. **Le rejeu du catalogue est un geste de la séquence, pas une supposition.** `import_grocy_catalog` (lot 0, **inchangé**) est rejoué en tête de bascule (geste 6) et rattrape tout produit, code-barres ou catégorie créé depuis le 19 août. Il est rejouable par construction : la tâche 1 en réépingle la propriété avec `batch.external_ref` en tête.
2. **Le gel de Grocy est acquitté, pas espéré.** Le contrôle **C0** compare le `MAX(row_created_timestamp)` de `stock`, `stock_log`, `products` et `meal_plan` à la date de la copie, et **bloque** si Grocy a écrit après. Une écriture après la copie invalide les dix autres contrôles : C0 le dit avant qu'ils mentent.
3. **Aucun chiffre de la spec n'est écrit en dur dans le code.** 108 lots, 102 recettes, 510 ingrédients, 116 minuteurs, 42 repas, 9 lignes de courses : ce sont des **attentes de tests sur fixtures figées**, jamais des constantes de production. Le code compte ce qu'il trouve ; les contrôles comparent les deux bases entre elles. Un lot de plus créé demain ne fait pas échouer le code — il fait échouer C0, ce qui est le comportement voulu.

---

## Structure des fichiers

**Python — créés**

| Fichier | Responsabilité |
|---|---|
| `custom_components/home_stock/storage/migrations/m008_migration.py` | `batch.external_ref` + son index unique partiel. Rien d'autre. |
| `custom_components/home_stock/grocy/__init__.py` | Le paquet pur. Aucun import de `hass`. |
| `custom_components/home_stock/grocy/units.py` | Table de correspondance des unités, **réimportée** par `import_grocy.py` — pas copiée. |
| `custom_components/home_stock/grocy/html.py` | Découpe du HTML des recettes : pages, méta, titres, puces, minuteurs. Pur. |
| `custom_components/home_stock/grocy/pictures.py` | Nommage, décodage des data-URI, réécriture des URL, réconciliation fichiers ↔ références. Pur sauf l'écriture de fichier, isolée. |
| `custom_components/home_stock/import_grocy_stock.py` | Lots, mouvements d'entrée, `packaging`, lignes de courses ouvertes. |
| `custom_components/home_stock/import_grocy_recipes.py` | Recettes, étapes, instructions, ingrédients, images, planning. |
| `custom_components/home_stock/migration_check.py` | Les onze contrôles, leurs planchers, les acquittements nominatifs, l'archive JSON. |

**Python — modifiés**

| Fichier | Ce qui change |
|---|---|
| `storage/migrations/__init__.py` | `m008` dans `MIGRATIONS` ; `CURRENT_VERSION` passe à 8 |
| `import_grocy.py` | Réimporte les tables d'unités depuis `grocy/units.py`. **Aucun autre changement.** |
| `const.py` | `GROCY_*` (préfixes d'`external_ref`, sentinelle de DLC, seuil de prix aberrant), `MIGRATION_CHECKS` |
| `validators.py` | `grocy_database_path`, `picture_dir`, `acknowledgement_list` |
| `services.py` | Trois services : `import_grocy_stock`, `import_grocy_recipes`, `check_grocy_migration` |
| `services.yaml` | Leurs trois descriptions, en français |
| `websocket_api.py` | `home_stock/migration/check`, même schéma et même réponse que le service |
| `translations/fr.json`, `translations/en.json` | Libellés des trois services |
| `docs/exploitation.md` | Journal qui démarre le jour de la bascule, images sous `media/`, statistiques à supprimer, chemin de repli des 6 corvées |

**Front — modifiés**

| Fichier | Ce qui change |
|---|---|
| `frontend/src/ecrans/reglages.ts` | Un bloc « Bascule » : bouton « Contrôler », onze lignes, bloquantes en rouge. **Aucun bouton d'import, aucun bouton d'extinction.** |
| `frontend/outils/verifier-rendu.mjs` | Un scénario de plus, aux deux formats → 70 exécutions deviennent 72 |
| `frontend/src/panneau.ts` | Rien de nouveau : pas d'écran de plus (§ 15.3) |

**Front — créés**

| Fichier | Responsabilité |
|---|---|
| `frontend/tests/reglages-bascule.test.ts` | Le bloc Bascule : onze lignes, rouge sur bloquant, aucun bouton d'import ni d'extinction |

**Documents livrés**

| Fichier | Ce que c'est |
|---|---|
| `docs/extinction/README.md` | **La procédure d'extinction**, 18 gestes numérotés pour le propriétaire. Livrée, jamais exécutée. |
| `docs/extinction/inventaire-grocy.md` | Ce qui casse, ce qui devient inerte, ce qui était déjà mort — avec le geste en face de chacun |
| `docs/extinction/retour-arriere.md` | Ce qu'on garde et combien de temps ; les trois situations d'après-coup ; ce qui ne revient pas |
| `config/home_stock_grocy_archive_<AAAA-MM-JJ>.json` | **Produit à l'exécution** par `check_grocy_migration`, pas versionné : 1 123 lignes de `stock_log`, 25 notes de lots, 39 pointages de corvées, 66 entrées de planning passées |
| `docs/superpowers/specs/2026-08-21-home-stock-lot7-design.md` | Amendé en tâche 20 §22 si un chiffre mesuré diffère |

---

## Task 1: `m008` — `batch.external_ref`, et la rejouabilité du stock

**Files:**
- Create: `custom_components/home_stock/storage/migrations/m008_migration.py`
- Modify: `custom_components/home_stock/storage/migrations/__init__.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/storage/test_migrations.py`

**Interfaces:**
- Produit : la colonne `batch.external_ref TEXT` et l'index `idx_batch_external_ref`, unique **partiel** (`WHERE external_ref IS NOT NULL`).
- Produit : `const.GROCY_STOCK_REF_PREFIX = "grocy:stock:"`, `const.GROCY_NEVER_EXPIRES = "2999-12-31"`, `const.GROCY_MAX_BATCH_VALUE = 20.0`.
- `migrations.CURRENT_VERSION` passe de 7 à **8**.

**Pourquoi cette colonne.** `batch` est la **seule** table du schéma sans `external_ref` : `product`, `article`, `recipe`, `recipe_ingredient`, `meal`, `battery` et `equipment` en ont un, tous pour la même raison écrite au lot 0 — « id Grocy, pour un import rejouable ». Un import de stock non rejouable serait le seul de la chaîne, et le plus dangereux : c'est celui qu'on relance après avoir corrigé un prix.

**Ce qui a été envisagé et refusé, à ne pas réintroduire :** `batch.note` (les 25 notes vivent dans le rapport d'import et dans l'archive ; une colonne que rien ne lit finit par être crue) ; une table `archive_movement` (écrite une fois, lue jamais — l'archive est un fichier) ; `recipe_step.external_ref` (une étape est découpée d'un HTML, sa clé naturelle est `(recipe_id, position)`, déjà UNIQUE).

- [ ] **Step 1: Écrire les tests**

Dans `tests/storage/test_migrations.py`, à la suite des tests de `m007` :

```python
def test_m008_adds_external_ref_to_batch(tmp_path):
    conn = _migrated(tmp_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(batch)")}
    assert "external_ref" in columns


def test_m008_index_is_unique_but_partial(tmp_path):
    """Deux lots créés au scan n'ont pas de référence externe, et cent lots
    sans référence ne doivent pas se gêner — c'est exactement pourquoi
    l'index est partiel, comme idx_recipe_source."""
    conn = _migrated(tmp_path)
    article, location = _one_article(conn)
    for _ in range(3):
        repo.insert_batch(conn, article_id=article, location_id=location,
                          quantity=1.0, entered_at="2026-08-21T10:00:00")
    # Trois lots sans référence : aucun conflit.
    assert conn.execute("SELECT COUNT(*) AS n FROM batch").fetchone()["n"] == 3

    first = repo.insert_batch(conn, article_id=article, location_id=location,
                              quantity=1.0, entered_at="2026-08-21T10:00:00")
    conn.execute("UPDATE batch SET external_ref = 'grocy:stock:419' WHERE id = ?",
                 (first,))
    second = repo.insert_batch(conn, article_id=article, location_id=location,
                               quantity=1.0, entered_at="2026-08-21T10:00:00")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE batch SET external_ref = 'grocy:stock:419' WHERE id = ?",
                     (second,))


def test_m008_is_replayable(tmp_path):
    """Deux passages d'apply_migrations ne doivent ni lever ni dupliquer."""
    conn = _migrated(tmp_path)
    assert migrations.apply_migrations(conn) == 8
    assert migrations.apply_migrations(conn) == 8


def test_current_version_is_eight():
    assert migrations.CURRENT_VERSION == 8
```

Et **ne pas toucher** `test_migration_versions_are_contiguous_from_one` : il passe de `[1..7]` à `[1..8]` **tout seul**, parce qu'il compare la liste à `range(1, len+1)`. Si une tâche est tentée de l'assouplir, c'est le signe que la `VERSION` et le nom du fichier ont divergé.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

```bash
docker ps --filter ancestor=home-stock-test        # doit être vide
./scripts/test.sh tests/storage/test_migrations.py -q
```
Expected: FAIL — `no such column: external_ref`, et `CURRENT_VERSION == 7`.

- [ ] **Step 3: Écrire la migration**

Créer `custom_components/home_stock/storage/migrations/m008_migration.py` :

```python
"""Lot 7: the Grocy id of a batch, so the stock import is replayable.

`batch` is the only table in the schema without an external_ref. product,
article, recipe, recipe_ingredient, meal, battery and equipment all have one,
all for the reason written in lot 0: "Grocy id, for a replayable import". A
stock import that could not be replayed would be the only one in the chain,
and the most dangerous — it is the one you re-run after fixing a price.

Schema-only, no apply(): there is nothing to backfill. The single batch in
production is the 19 August trial, which does not come from Grocy.

Numbering: the file name and VERSION move together, in the same commit. A
strict contiguity test requires [1..8].
"""
from __future__ import annotations

VERSION = 8

SQL = """
-- L'id Grocy du lot. Même rôle exactement que product.external_ref au lot 0 :
-- c'est ce qui rend l'import du stock rejouable, donc ce qui permet de le
-- lancer en simulation, de corriger la source, et de le relancer.
ALTER TABLE batch ADD COLUMN external_ref TEXT;

-- Partiel, comme idx_recipe_source : un lot créé au scan n'a pas de référence
-- externe, et cent lots sans référence ne doivent pas se gêner.
CREATE UNIQUE INDEX idx_batch_external_ref
  ON batch(external_ref) WHERE external_ref IS NOT NULL;
"""
```

Puis, dans `storage/migrations/__init__.py`, ajouter `m008_migration` à l'import **et** au tuple `MIGRATIONS`, dans cet ordre. Et dans `const.py` :

```python
# --- lot 7 : la bascule ------------------------------------------------------
GROCY_STOCK_REF_PREFIX: Final = "grocy:stock:"
GROCY_RECIPE_REF_PREFIX: Final = "grocy:recipe:"
GROCY_MEAL_UID_TEMPLATE: Final = "grocy-meal-{id}@home_stock"
# La sentinelle « ne périme jamais » de Grocy. La recopier donnerait dix lots
# qui périment dans neuf cent soixante-treize ans, en tête de tous les tris
# décroissants. NULL est la façon dont home_stock dit « pas de DLC ».
GROCY_NEVER_EXPIRES: Final = "2999-12-31"
# Au-delà, `amount x price` n'est pas un prix maladroit mais une ligne de
# ticket accrochée au mauvais produit (spec §8.4). Le lot le plus cher retenu
# vaut 13,80 EUR, le premier écarté en vaut 47 : la frontière est un fossé.
GROCY_MAX_BATCH_VALUE: Final = 20.0
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage/ -q`
Expected: PASS, contiguïté `[1..8]` comprise.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Retirer `WHERE external_ref IS NOT NULL` de l'index : `test_m008_index_is_unique_but_partial` doit tomber sur les **trois premiers** lots (deux `NULL` en conflit), pas seulement sur le doublon. Si seul le doublon tombe, le test ne prouve pas la partialité. Remettre.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/storage/migrations/m008_migration.py \
        custom_components/home_stock/storage/migrations/__init__.py \
        custom_components/home_stock/const.py tests/storage/test_migrations.py
git commit -m "feat: batch.external_ref makes the stock import replayable (m008)"
```

---

## Task 2: `grocy/units.py` — une seule table de correspondance, pas trois

**Files:**
- Create: `custom_components/home_stock/grocy/__init__.py`
- Create: `custom_components/home_stock/grocy/units.py`
- Modify: `custom_components/home_stock/import_grocy.py`
- Test: `tests/grocy/__init__.py`, `tests/grocy/test_units.py`, `tests/test_import_grocy.py`

**Interfaces:**
- Produit : `MASS_UNITS`, `VOLUME_UNITS`, `CONTAINER_UNITS`, `DOSAGE_UNITS`, `base_unit(unit_name) -> tuple[str, float] | None`.
- `import_grocy.py` **réimporte** ces noms et supprime ses définitions locales. Ses `MASS_UNITS`, `_base_unit`, etc. restent accessibles sous leurs anciens noms (`from .grocy.units import MASS_UNITS, …` puis `_base_unit = base_unit`) pour ne casser aucun test existant.

**Pourquoi.** Trois imports qui convertiraient les unités chacun à sa façon finiraient par diverger — et une divergence de conversion d'unité, c'est **une bouteille et demie d'huile d'olive par burger**. Le test qui suit compare l'**identité** des objets, pas leurs valeurs : une copie qui « dit la même chose » aujourd'hui est exactement ce qu'on interdit.

- [ ] **Step 1: Écrire les tests**

Créer `tests/grocy/__init__.py` (vide) et `tests/grocy/test_units.py` :

```python
"""Une seule table de correspondance des unités, partagée, jamais copiée."""
from custom_components.home_stock import import_grocy
from custom_components.home_stock.grocy import units


def test_import_grocy_reuses_the_very_same_objects():
    """L'IDENTITÉ, pas l'égalité. Une copie qui dit la même chose aujourd'hui
    est précisément ce que ce test existe pour interdire : elle dira autre
    chose le jour où quelqu'un ajoutera « Flacon » d'un seul côté."""
    assert import_grocy.MASS_UNITS is units.MASS_UNITS
    assert import_grocy.VOLUME_UNITS is units.VOLUME_UNITS
    assert import_grocy.CONTAINER_UNITS is units.CONTAINER_UNITS
    assert import_grocy.DOSAGE_UNITS is units.DOSAGE_UNITS


def test_the_three_families_and_the_refusal():
    assert units.base_unit("kg") == ("g", 1000.0)
    assert units.base_unit("cl") == ("ml", 10.0)
    assert units.base_unit("Bouteille") == ("piece", 1.0)
    assert units.base_unit("Lot") == ("piece", 1.0)
    assert units.base_unit("Pot") == ("piece", 1.0)
    assert units.base_unit("cs") is None      # dosage, pas stockage
    assert units.base_unit("parsec") is None


def test_a_dosage_unit_is_never_a_stock_unit():
    """« cs » et « cc » doivent rester hors des trois familles : un produit
    stocké « à la cuillère » est une erreur de saisie, pas une unité."""
    for name in units.DOSAGE_UNITS:
        assert units.base_unit(name) is None


def test_no_unit_name_belongs_to_two_families():
    familles = [set(units.MASS_UNITS), set(units.VOLUME_UNITS),
                units.CONTAINER_UNITS, units.DOSAGE_UNITS]
    for i, une in enumerate(familles):
        for autre in familles[i + 1:]:
            assert not (une & autre)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/grocy/test_units.py -q`
Expected: FAIL — `ModuleNotFoundError: custom_components.home_stock.grocy`

- [ ] **Step 3: Écrire le module et rebrancher `import_grocy.py`**

`grocy/__init__.py` porte une seule docstring : « Pure helpers over Grocy's own shapes. No hass, no network, no SQLite here. »

`grocy/units.py` reçoit les quatre tables **déplacées** depuis `import_grocy.py` (couper-coller, pas copier) et `base_unit()`, qui est l'ancien `_base_unit` renommé. Dans `import_grocy.py`, remplacer les définitions par :

```python
from .grocy.units import (
    CONTAINER_UNITS, DOSAGE_UNITS, MASS_UNITS, VOLUME_UNITS, base_unit,
)

# Ancien nom, conservé : le lot 7 partage la table, il ne renomme rien de ce
# que le lot 0 a testé.
_base_unit = base_unit
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/grocy/ tests/test_import_grocy.py -q`
Expected: PASS. Les tests du lot 0 sont **inchangés** — c'est la preuve que le déplacement n'a rien changé au comportement.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Dans `import_grocy.py`, remplacer l'import par une copie littérale de `MASS_UNITS` (`MASS_UNITS = {"g": 1.0, "kg": 1000.0}`). `test_import_grocy_reuses_the_very_same_objects` doit tomber alors que **tous les autres tests restent verts** — c'est exactement la divergence silencieuse qu'on veut voir. Remettre.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/grocy/ custom_components/home_stock/import_grocy.py tests/grocy/
git commit -m "refactor: one unit table for every Grocy import, shared not copied"
```

---

## Task 3: Les fixtures — 102 descriptions réelles, figées

**Files:**
- Create: `tests/fixtures/grocy/extraire.py` (outil, pas un test)
- Create: `tests/fixtures/grocy/recipes.json` (les 102 recettes : id, type, nom, `base_servings`, `row_created_timestamp`, description)
- Create: `tests/fixtures/grocy/recipes_pos.json` (les 510 lignes + leurs 200 orphelines, pour prouver qu'on les écarte)
- Create: `tests/fixtures/grocy/stock.json`, `tests/fixtures/grocy/meal_plan.json`, `tests/fixtures/grocy/shopping_list.json`, `tests/fixtures/grocy/quantity_unit_conversions.json`
- Create: `tests/fixtures/grocy/inline_images.json` (longueur d'origine et SHA-256 de chaque data-URI remplacée)
- Create: `tests/conftest.py` — fixtures `grocy_reel`, `grocy_reel_db`
- Test: `tests/grocy/test_fixtures.py`

**Interfaces:**
- `tests/conftest.py` gagne :
  - `grocy_reel` — le dict des tables Grocy chargées depuis les JSON ;
  - `grocy_reel_db(tmp_path)` — une base SQLite **reconstruite** depuis ces JSON, avec le schéma minimal que les imports lisent, ouverte en lecture seule. C'est elle que les tâches 6 à 14 utilisent.

**La décision de fixture, tranchée ici.** Les 102 descriptions pèsent **3,80 Mo**, dont **3,48 Mo de base64** dans 62 data-URI. Versionner 3,8 Mo de blobs binaires en git pour tester un découpeur de HTML est un mauvais échange. Décision :

- **Chaque payload `data:image/...;base64,<…>` est remplacé** par un stub déterministe de 64 octets qui décode en un **vrai JPEG 1×1** valide, et `inline_images.json` conserve, pour chacun, sa longueur d'origine et son SHA-256.
- **Exception : la recette 41 garde ses data-URI intacts**, comme unique cas qui prouve que le décodeur écrit un fichier JPEG réel et non un stub.
- **Tout le reste du HTML est intouché**, octet pour octet : les 323 `<div class="page-recipes">`, les 234 `<h3 style="…">`, les 229 `<img>`, les 116 minuteurs et les **443 `#`** dont 327 sont des couleurs CSS. Aucun test structurel ne dépend des pixels ; tous dépendent de ces chiffres-là.
- Poids obtenu : **≈ 340 Ko**, versionnable sans remords.

`extraire.py` **n'est jamais lancé par la suite de tests**. Il documente d'où viennent les JSON et permet de les regénérer si la spec est amendée. Il ouvre `file:<copie>?mode=ro` et **refuse de démarrer** si le chemin qu'on lui donne est `/opt/nivuus/Grocy/config/data/grocy.db`.

- [ ] **Step 1: Écrire les tests des fixtures**

Créer `tests/grocy/test_fixtures.py` — ces tests **épinglent la volumétrie** et sont ce qui rend tous les tests suivants dignes de foi :

```python
"""Les fixtures sont la mesure. Si elles bougent, tout le lot 7 bouge.

Ces tests ne testent pas du code : ils testent que les données figées le
2026-08-21 sont toujours celles sur lesquelles la spec a été écrite. Un
chiffre qui change ici est un amendement de spec, jamais une correction de
test.
"""
import re


def test_the_hundred_and_two_recipes(grocy_reel):
    recettes = grocy_reel["recipes"]
    assert len(recettes) == 102
    types = {}
    for ligne in recettes:
        types[ligne["type"]] = types.get(ligne["type"], 0) + 1
    assert types == {"normal": 87, "1": 15}
    # Aucune copie fantôme : elles sont toutes à identifiant négatif.
    assert all(ligne["id"] > 0 for ligne in recettes)


def test_the_five_hundred_and_ten_ingredient_rows(grocy_reel):
    ids = {ligne["id"] for ligne in grocy_reel["recipes"]}
    lignes = grocy_reel["recipes_pos"]
    retenues = [l for l in lignes if l["recipe_id"] in ids]
    orphelines = [l for l in lignes if l["recipe_id"] not in ids]
    assert len(retenues) == 510
    assert len(orphelines) == 200      # résidus des recettes du jour/semaine


def test_the_structure_the_splitter_will_meet(grocy_reel):
    html = "".join(l["description"] or "" for l in grocy_reel["recipes"])
    assert html.count('<div class="page-recipes">') == 323
    assert html.count("<h3") == 234
    assert "<h3>" not in html          # AUCUN h3 nu : ils sont tous stylés
    assert html.count("<img") == 229


def test_three_quarters_of_the_hashes_are_css_colours(grocy_reel):
    """443 `#` dans la base, 327 sont des couleurs. Un motif de minuteur trop
    lâche transforme `color:#888;font-size:12px` en un minuteur « 888;font-size »
    de 12 secondes — c'est arrivé pendant l'analyse de la spec."""
    html = "".join(l["description"] or "" for l in grocy_reel["recipes"])
    assert html.count("#") == 443
    couleurs = len(re.findall(r"#[0-9a-fA-F]{3,6}\b(?=[;\"'])", html))
    assert couleurs == 327


def test_the_fifteen_type_one_recipes_have_no_pages(grocy_reel):
    """Leur description est un <ol><li> nu. C'est la forme que le découpeur
    doit rendre en UNE page, jamais en zéro."""
    for ligne in grocy_reel["recipes"]:
        if ligne["type"] == "1":
            assert '<div class="page-recipes">' not in (ligne["description"] or "")
            assert "<ol" in ligne["description"]


def test_the_hundred_and_eight_stock_rows(grocy_reel):
    lots = grocy_reel["stock"]
    assert len(lots) == 108
    assert len({l["product_id"] for l in lots}) == 87
    sentinelles = [l for l in lots if l["best_before_date"] == "2999-12-31"]
    assert len(sentinelles) == 10
    sans_emplacement = [l for l in lots if not l["location_id"] or l["location_id"] == 1]
    assert len(sans_emplacement) == 29


def test_the_forty_two_future_meal_plan_rows(grocy_reel):
    plan = grocy_reel["meal_plan"]
    assert len(plan) == 108
    assert len({l["section_id"] for l in plan}) == 4      # dont la ligne -1


def test_the_nine_open_shopping_rows(grocy_reel):
    lignes = grocy_reel["shopping_list"]
    assert len(lignes) == 25
    assert len([l for l in lignes if not l["done"]]) == 9


def test_the_thirty_conversions_are_fifteen_round_trips(grocy_reel):
    assert len(grocy_reel["quantity_unit_conversions"]) == 30


def test_recipe_forty_one_kept_its_real_data_uris(grocy_reel):
    """L'unique recette non stubbée : c'est elle qui prouve que le décodeur
    écrit un VRAI JPEG et non le stub de 64 octets des 101 autres."""
    r41 = next(l for l in grocy_reel["recipes"] if l["id"] == 41)
    assert "data:image/jpeg;base64," in r41["description"]
    assert len(r41["description"]) > 100_000
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/grocy/test_fixtures.py -q`
Expected: FAIL — `fixture 'grocy_reel' not found`

- [ ] **Step 3: Extraire les fixtures**

Écrire `tests/fixtures/grocy/extraire.py`, puis le lancer **sur une copie** :

```bash
S=/tmp/user/0/claude-0/-opt-nivuus-HomeAssistant-data-meal/*/scratchpad
cp /opt/nivuus/Grocy/config/data/grocy.db $S/grocy-lecture.db
python3 tests/fixtures/grocy/extraire.py $S/grocy-lecture.db tests/fixtures/grocy/
```

`extraire.py` :
- ouvre `file:<chemin>?mode=ro`, **`sys.exit(2)` si le chemin résolu est sous `/opt/nivuus/Grocy/`** ;
- écrit un JSON par table, indenté, trié par `id`, encodage UTF-8 sans échappement ASCII (pour que `git diff` reste lisible) ;
- remplace chaque data-URI par le stub, **sauf** dans la recette 41, et note longueur + SHA-256 dans `inline_images.json`.

Puis ajouter à `tests/conftest.py` :

```python
@pytest.fixture(scope="session")
def grocy_reel() -> dict[str, list[dict]]:
    """Les tables Grocy figées le 2026-08-21. Lecture seule, jamais réécrites."""
    base = Path(__file__).parent / "fixtures" / "grocy"
    return {nom: json.loads((base / f"{nom}.json").read_text("utf-8"))
            for nom in ("recipes", "recipes_pos", "stock", "products",
                        "meal_plan", "meal_plan_sections", "shopping_list",
                        "quantity_unit_conversions", "quantity_units",
                        "locations", "stock_log", "chores_log")}


@pytest.fixture
def grocy_reel_db(tmp_path, grocy_reel) -> str:
    """Une base SQLite reconstruite depuis les fixtures.

    Reconstruite, et pas copiée : le schéma minimal qu'on écrit ici est
    exactement ce que les imports lisent, donc une colonne lue et non
    déclarée devient une erreur de test au lieu d'un import qui « marche
    parce que la vraie base l'avait ».
    """
    ...
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/grocy/test_fixtures.py -q`
Expected: PASS, dix tests.

- [ ] **Step 5: Vérifier le poids et l'absence de réseau**

```bash
du -sh tests/fixtures/grocy/          # attendu : ~340 Ko, jamais > 1 Mo
grep -c 'images.unsplash.com' tests/fixtures/grocy/recipes.json   # 112, laissées telles quelles
grep -rn 'urlopen\|requests\.\|aiohttp' tests/fixtures/grocy/     # attendu : rien
```

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/grocy/ tests/conftest.py tests/grocy/test_fixtures.py
git commit -m "test: the 102 real Grocy descriptions, frozen as fixtures"
```

---

## Task 4: `grocy/html.py` — découper le HTML des recettes

**Files:**
- Create: `custom_components/home_stock/grocy/html.py`
- Test: `tests/grocy/test_html.py`

**Interfaces:**
- `Page(NamedTuple)` : `kind` (`"cover" | "ingredients" | "step" | "other"`), `title: str | None`, `images: list[str]`, `bullets: list[str]`, `html: str`
- `decouper(description: str) -> list[Page]`
- `meta(description: str) -> Meta` avec `Meta(total_minutes: int | None, utensils: str | None, summary: str | None)`
- `texte(fragment: str) -> str` — balises internes retirées, `html.unescape()` **une seule fois**

**Pur** : pas de `hass`, pas de réseau, pas de SQLite. C'est la partie qui casse, donc celle qui se teste en `pytest` nu sur les 102 descriptions réelles.

**Les trois pièges, vérifiés en direct par la spec — ne pas les redécouvrir :**
1. **Aucun `<h3>` nu.** Il y a 234 `<h3 style="color:#333;">` et **zéro** `<h3>`. Un motif `<h3>` littéral trouve zéro titre et rend 338 étapes sans nom, en silence.
2. **Une description sans `page-recipes` doit rendre UNE page, pas zéro.** C'est le cas des 15 recettes de type `1`, et c'est la forme exacte d'une perte silencieuse : un `findall` qui ne trouve rien, une boucle qui ne tourne pas, un import qui annonce « 0 anomalie ».
3. **`html.unescape()` une seule fois.** Grocy redécode `&#x27;` en `'` à l'enregistrement ; un second passage transformerait un `&amp;lt;` légitime en `<`.

**Ce qui est délibérément ignoré :** la page « Ingrédients » (elle est un *rendu* de `recipes_pos`, jamais une source — la réimporter serait la deuxième écriture d'une même quantité) et le `🔥 ~450 kcal` de la ligne méta (valeur calculée, datée ; on la recalcule à l'affichage).

- [ ] **Step 1: Écrire les tests**

Créer `tests/grocy/test_html.py` :

```python
"""Le découpeur, sur les 102 descriptions réelles.

Trois pièges mesurés sur la base et non négociables : aucun <h3> nu, une
description sans page rend UNE page, et l'échappement se défait une seule
fois. Chacun a son test, et chacun de ces tests doit tomber seul.
"""
import pytest

from custom_components.home_stock.grocy import html as gh


def _description(grocy_reel, recipe_id):
    return next(l["description"] for l in grocy_reel["recipes"] if l["id"] == recipe_id)


def test_the_three_hundred_and_twenty_three_pages(grocy_reel):
    """La somme exacte, sur les 87 recettes `normal`. Un découpeur qui rend
    322 ou 324 a mangé ou inventé une page, et c'est invisible autrement."""
    total = sum(len(gh.decouper(l["description"]))
                for l in grocy_reel["recipes"] if l["type"] == "normal")
    assert total == 323


def test_a_description_without_pages_yields_one_page_not_zero(grocy_reel):
    """LE test qui empêche la perte silencieuse des 15 recettes de type 1."""
    for ligne in grocy_reel["recipes"]:
        if ligne["type"] != "1":
            continue
        pages = gh.decouper(ligne["description"])
        assert len(pages) == 1, ligne["name"]
        assert pages[0].bullets, ligne["name"]      # le <ol> est bien dedans


def test_every_normal_recipe_has_exactly_one_ingredients_page(grocy_reel):
    for ligne in grocy_reel["recipes"]:
        if ligne["type"] != "normal":
            continue
        pages = gh.decouper(ligne["description"])
        assert len([p for p in pages if p.kind == "ingredients"]) == 1, ligne["name"]


def test_the_hundred_and_forty_seven_step_pages(grocy_reel):
    total = sum(len([p for p in gh.decouper(l["description"]) if p.kind == "step"])
                for l in grocy_reel["recipes"] if l["type"] == "normal")
    assert total == 147


def test_a_styled_h3_is_still_a_title():
    """Il n'existe AUCUN <h3> nu dans la base : 234 sur 234 portent un style.
    Un motif littéral `<h3>` trouve zéro titre et rend des étapes sans nom."""
    page = gh.decouper(
        '<div class="page-recipes">'
        '<h3 style="color:#333;">Étape 2 — Saisir le poulet</h3>'
        '<ol><li>Chauffer la poêle.</li></ol></div>')[0]
    assert page.kind == "step"
    assert page.title == "Saisir le poulet"


def test_the_step_number_orders_but_does_not_title():
    pages = gh.decouper(
        '<div class="page-recipes"><h3 style="color:#333;">Étape 10 — Dresser</h3>'
        '<ol><li>Servir.</li></ol></div>')
    assert pages[0].title == "Dresser"


def test_entities_are_unescaped_exactly_once():
    """Grocy redécode &#x27; en ' à l'enregistrement. Un second passage
    transformerait un &amp;lt; légitime en <."""
    assert gh.texte("<li>l&#x27;huile d&#x27;olive</li>") == "l'huile d'olive"
    assert gh.texte("<li>a &amp;lt; b</li>") == "a &lt; b"


def test_strong_is_stripped_but_its_words_stay():
    assert gh.texte("<li>saisir <strong>4 min par face</strong></li>") \
        == "saisir 4 min par face"


def test_the_four_hundred_and_sixty_eight_instruction_bullets(grocy_reel):
    total = sum(len(p.bullets)
                for l in grocy_reel["recipes"] if l["type"] == "normal"
                for p in gh.decouper(l["description"]) if p.kind == "step")
    assert total == 468


def test_the_ingredients_page_bullets_are_not_counted_as_instructions(grocy_reel):
    """415 <li> dans les <ul> d'ingrédients, pour 414 lignes de recipes_pos :
    la page est un miroir, et le découpeur ne doit surtout pas la confondre
    avec une étape."""
    total = sum(len(p.bullets)
                for l in grocy_reel["recipes"] if l["type"] == "normal"
                for p in gh.decouper(l["description"]) if p.kind == "ingredients")
    assert total == 415


def test_the_two_hundred_and_twenty_nine_images(grocy_reel):
    total = sum(len(p.images) for l in grocy_reel["recipes"]
                for p in gh.decouper(l["description"]))
    assert total == 229


def test_the_meta_line_gives_minutes_and_utensils(grocy_reel):
    m = gh.meta(_description(grocy_reel, 1))
    assert isinstance(m.total_minutes, int) and 1 <= m.total_minutes <= 600
    assert m.utensils
    assert m.summary


def test_every_normal_recipe_has_a_meta_line(grocy_reel):
    """87 lignes méta pour 87 recettes. Une seule absente et le compteur
    total_minutes serait NULL sans que personne s'en aperçoive."""
    avec = [l for l in grocy_reel["recipes"] if l["type"] == "normal"
            and gh.meta(l["description"]).total_minutes is not None]
    assert len(avec) == 87


def test_a_type_one_recipe_has_no_meta_and_that_is_not_an_error(grocy_reel):
    for ligne in grocy_reel["recipes"]:
        if ligne["type"] == "1":
            m = gh.meta(ligne["description"])
            assert m.total_minutes is None
            assert m.utensils is None


def test_the_kcal_of_the_meta_line_is_deliberately_not_returned(grocy_reel):
    """C'est une valeur CALCULÉE par recettes_miseenpage.py depuis le
    catalogue. La graver ici, c'est graver un chiffre daté."""
    assert not hasattr(gh.meta(_description(grocy_reel, 1)), "kcal")


def test_an_empty_description_yields_no_page():
    assert gh.decouper("") == []
    assert gh.decouper(None) == []


def test_nested_page_divs_do_not_produce_a_page(grocy_reel):
    """La découpe porte sur les <div class="page-recipes"> de PREMIER niveau.
    Un compte naïf de balises ouvrantes en trouverait davantage."""
    pages = gh.decouper(
        '<div class="page-recipes"><div class="page-recipes">'
        '<h3 style="color:#333;">Étape 1 — X</h3><ol><li>a</li></ol>'
        '</div></div>')
    assert len(pages) == 1
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/grocy/test_html.py -q`
Expected: FAIL — `ModuleNotFoundError: …grocy.html`

- [ ] **Step 3: Écrire le module**

`grocy/html.py`. Points d'implémentation obligatoires :

- La découpe des pages se fait par **balayage de profondeur** sur `<div … class="page-recipes"` / `</div>`, pas par `re.findall` non-greedy : les pages sont imbriquées et un `.*?` s'arrête au premier `</div>` intérieur.
- Le titre se lit sur `<h3[^>]*>(.*?)</h3>` — **`[^>]*` obligatoire**, jamais `<h3>`.
- `kind` : `ingredients` si le titre déséchappé est exactement `Ingrédients` ; `step` si le titre commence par `Étape` ; `cover` si la page porte la ligne méta ; `other` sinon.
- Une description sans aucun `page-recipes` rend **une** `Page(kind="other")` portant tout le fragment, avec ses `<li>` en `bullets`. C'est la branche qui sauve les 15 recettes de type `1` ; elle est écrite en premier et commentée comme telle.
- `texte()` : retirer les balises, **puis** `html.unescape()` **une fois**, puis normaliser les espaces. L'ordre compte : déséchapper d'abord ferait d'un `&lt;strong&gt;` littéral une balise à retirer.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/grocy/test_html.py -q`
Expected: PASS, dix-sept tests.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Trois mutations, chacune doit faire tomber **son** test et lui seul :

| Mutation | Test qui doit tomber |
|---|---|
| `re.findall(r"<h3>(.*?)</h3>")` au lieu de `<h3[^>]*>` | `test_a_styled_h3_is_still_a_title` (et les compteurs d'étapes) |
| `if not pages: return []` au lieu de la page unique | `test_a_description_without_pages_yields_one_page_not_zero` |
| `html.unescape(html.unescape(t))` | `test_entities_are_unescaped_exactly_once` |

Si la deuxième mutation laisse la suite verte, c'est que rien ne couvre les recettes de type `1` — arrêter et corriger le test avant de continuer.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/grocy/html.py tests/grocy/test_html.py
git commit -m "feat: split a Grocy recipe description into pages, on the real 102"
```

---

## Task 5: Les minuteurs — 116, dont 8 qui se dédoublent

**Files:**
- Modify: `custom_components/home_stock/grocy/html.py`
- Test: `tests/grocy/test_html.py` (nouveau bloc « minuteurs »)

**Interfaces:**
- `TIMER: re.Pattern` — `re.compile(r"#([^#:;<>]{1,40}?):(\d{1,5})\b")`
- `minuteurs(fragment: str) -> list[tuple[str, int]]`
- `instructions(bullet: str) -> list[Instruction]` avec `Instruction(text: str, timer_label: str | None, timer_seconds: int | None)` — **une puce peut rendre deux instructions**.

**Les deux pièges de forme, mesurés — ne pas les redécouvrir :**
1. **L'étiquette contient des espaces.** Le lot 3 et le README de `grocy-off` écrivent `#Nom:secondes` ; la réalité est `#Repos poulet:600`, `#Cabillaud face 1:180`, `#Airfryer légumes:1050`. Un motif `#(\S+):(\d+)` coupe au premier espace et perd la moitié du libellé.
2. **327 des 443 `#` de la base sont des couleurs CSS.** Un motif trop lâche fait de `style="color:#888;font-size:12px"` un minuteur « 888;font-size » de 12 secondes — c'est arrivé sur la première expression essayée pendant l'analyse de la spec. Le motif retenu **interdit `#`, `:`, `;`, `<` et `>` dans l'étiquette**.

**Le dédoublement des 8 puces.** `recipe_instruction` porte **au plus un** minuteur (`CHECK ((timer_label IS NULL) = (timer_seconds IS NULL))`) et les 8 puces à deux minuteurs sont des cuissons à deux faces. La puce est **scindée** : la première garde la phrase et son premier minuteur, la seconde porte le **libellé du second minuteur comme texte** (« Poulet face 2 ») et ce minuteur. Rien n'est inventé — ce texte existe déjà dans la source — et aucun minuteur n'est perdu. Les trois options écartées (garder le premier, ajouter `recipe_timer` en `m008`, fusionner en 480 s) le restent : la première perd 8 minuteurs, la deuxième change le contrat de la vue cuisine du lot 3 pour 8 puces sur 553, la troisième est fausse — on retourne le poulet entre les deux.

- [ ] **Step 1: Écrire les tests**

À la suite de `tests/grocy/test_html.py` :

```python
# --- minuteurs --------------------------------------------------------------

def test_a_label_with_spaces_survives():
    """#Repos poulet:600, pas #Repos. Un motif #(\\S+): coupe au premier
    espace et perd la moitié du libellé, sans rien signaler."""
    assert gh.minuteurs("Laisser reposer. #Repos poulet:600") == [("Repos poulet", 600)]
    assert gh.minuteurs("#Cabillaud face 1:180") == [("Cabillaud face 1", 180)]
    assert gh.minuteurs("#Airfryer légumes:1050") == [("Airfryer légumes", 1050)]


@pytest.mark.parametrize("fragment", [
    'style="color:#888;font-size:12px"',
    'style="color:#333;"',
    '<p style="color:#555;font-size:14px;">Une accroche.</p>',
    "#fff",
    "background:#1a1a1a;padding:12px",
])
def test_a_css_colour_is_never_a_timer(fragment):
    """327 des 443 # de la base sont des couleurs. C'est l'erreur qui a été
    commise pour de vrai sur la première expression essayée."""
    assert gh.minuteurs(fragment) == []


def test_the_hundred_and_sixteen_timers(grocy_reel):
    """116, pas 115. Un minuteur perdu, c'est une cuisson non minutée sur une
    tablette, et personne ne s'en aperçoit avant d'avoir brûlé le poisson."""
    total = 0
    for ligne in grocy_reel["recipes"]:
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                total += len(gh.minuteurs(puce))
    assert total == 116


def test_every_timer_lives_in_a_normal_recipe(grocy_reel):
    for ligne in grocy_reel["recipes"]:
        if ligne["type"] != "1":
            continue
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                assert gh.minuteurs(puce) == [], ligne["name"]


def test_durations_stay_inside_the_measured_range(grocy_reel):
    durees = [s for l in grocy_reel["recipes"]
              for p in gh.decouper(l["description"]) for b in p.bullets
              for _, s in gh.minuteurs(b)]
    assert min(durees) == 25
    assert max(durees) == 3600


def test_a_bullet_with_two_timers_becomes_two_instructions():
    puce = "Poêle à feu vif, saisir 4 min par face. #Poulet face 1:240 #Poulet face 2:240"
    resultat = gh.instructions(puce)
    assert len(resultat) == 2
    assert resultat[0].timer_label == "Poulet face 1" and resultat[0].timer_seconds == 240
    assert "saisir 4 min par face" in resultat[0].text
    # Le texte de la seconde est le libellé du second minuteur : une chaîne
    # qui existe DÉJÀ dans la source, jamais une phrase inventée.
    assert resultat[1].text == "Poulet face 2"
    assert resultat[1].timer_seconds == 240


def test_the_eight_double_bullets_and_no_more(grocy_reel):
    doubles = [b for l in grocy_reel["recipes"]
               for p in gh.decouper(l["description"]) for b in p.bullets
               if len(gh.minuteurs(b)) == 2]
    assert len(doubles) == 8


def test_no_bullet_carries_three_timers(grocy_reel):
    """Le dédoublement ne traite que la paire. Trois minuteurs sur une puce
    demanderaient une décision qui n'a pas été prise — mieux vaut le savoir
    par un test rouge que par une instruction avalée."""
    for ligne in grocy_reel["recipes"]:
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                assert len(gh.minuteurs(puce)) <= 2


def test_the_marker_never_stays_in_the_text():
    resultat = gh.instructions("Laisser reposer. #Repos poulet:600")
    assert "#" not in resultat[0].text
    assert resultat[0].text == "Laisser reposer."


def test_five_hundred_and_sixty_one_instructions_in_all(grocy_reel):
    """553 puces + les 8 dédoublements. C'est le chiffre que C8 contrôlera."""
    total = sum(len(gh.instructions(b)) for l in grocy_reel["recipes"]
                for p in gh.decouper(l["description"])
                if p.kind != "ingredients" for b in p.bullets)
    assert total == 561


def test_the_check_of_m004_can_never_be_violated(grocy_reel):
    """CHECK ((timer_label IS NULL) = (timer_seconds IS NULL)) : le motif
    exigeant les deux, une puce à libellé sans durée ne peut pas naître."""
    for ligne in grocy_reel["recipes"]:
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                for inst in gh.instructions(puce):
                    assert (inst.timer_label is None) == (inst.timer_seconds is None)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/grocy/test_html.py -q -k minuteur or timer`
Expected: FAIL — `module has no attribute 'minuteurs'`

- [ ] **Step 3: Écrire les minuteurs**

Ajouter à `grocy/html.py` le motif **exactement** tel que la spec le fixe, avec son commentaire :

```python
# L'étiquette contient des espaces (#Repos poulet:600) et 327 des 443 `#` de
# la base sont des couleurs CSS. Interdire #, :, ;, < et > dans l'étiquette
# est ce qui sépare les deux — un motif plus lâche fait de
# `style="color:#888;font-size:12px"` un minuteur de 12 secondes.
TIMER = re.compile(r"#([^#:;<>]{1,40}?):(\d{1,5})\b")
```

`instructions()` : retirer les marqueurs du texte, `texte()` dessus, puis rendre une `Instruction` par minuteur trouvé au-delà du premier — la seconde portant le **libellé** du second minuteur comme texte.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/grocy/test_html.py -q`
Expected: PASS, vingt-huit tests.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| `TIMER = re.compile(r"#(\S+?):(\d+)")` | `test_a_label_with_spaces_survives` **et** `test_a_css_colour_is_never_a_timer` **et** `test_the_hundred_and_sixteen_timers` |
| Garder seulement `minuteurs(b)[:1]` | `test_a_bullet_with_two_timers_becomes_two_instructions`, `test_five_hundred_and_sixty_one_instructions_in_all` |

La première mutation doit faire tomber **trois** tests. Si elle n'en fait tomber qu'un, la couverture des couleurs CSS est illusoire.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/grocy/html.py tests/grocy/test_html.py
git commit -m "feat: 116 timers, labels with spaces, and eight bullets that split in two"
```

---

## Task 6: La reprise du stock — le calcul, avant toute écriture

**Files:**
- Create: `custom_components/home_stock/import_grocy_stock.py` (partie pure : `plan_batches`)
- Test: `tests/test_import_grocy_stock.py`

**Interfaces:**
- `@dataclass PlannedBatch` : `grocy_stock_id`, `product_id`, `article_id`, `base_unit`, `quantity`, `best_before`, `price_per_base_unit`, `location_id`, `opened_at`, `entered_at`, `closed`, `external_ref`
- `plan_batches(grocy_rows, catalogue, locations, *, today) -> tuple[list[PlannedBatch], list[str]]` — rend les lots calculés et les anomalies, **sans toucher à la base de destination**.
- `StockImportError` — l'unique cas d'arrêt dur : un lot dont le `grocy_product_id` n'est pas au catalogue.

**La jointure, pas l'appariement.** Sur les 108 lots, **107 se résolvent par `external_ref`** vers un produit de `home_stock`, avec une unité de base identique à celle choisie à l'import du catalogue. Le 108ᵉ est le Sorbet Fraise créé le 21 août, que le rejeu du catalogue (geste 6) fait entrer. **L'appariement du lot 3, qui devine et qui score, n'est jamais sollicité** : chaque lot connaît son produit par son identifiant. C'est la promesse du lot 0 tenue et mesurée, et le plan ne doit surtout pas la contourner par un repli « par nom » — le repli par nom est ce qui a créé les 35 doublons d'avril 2026.

La requête Grocy est celle de la spec § 8.1, **sans aucun alias `b`** (le dépôt interdit le littéral `SELECT b.*` par un scan) : `s` pour `stock`, `prod` pour `products`.

- [ ] **Step 1: Écrire les tests**

Créer `tests/test_import_grocy_stock.py` :

```python
"""Le calcul des 108 lots, avant toute écriture.

Toute cette tâche est pure : elle reçoit des lignes et rend des lots. Ce qui
touche SQLite est la tâche suivante, et la séparation est ce qui permet de
tester les sept prix aberrants sans ouvrir une base.
"""
import pytest

from custom_components.home_stock.import_grocy_stock import (
    StockImportError, plan_batches,
)


def test_the_hundred_and_seven_batches_resolve(grocy_reel, catalogue_reel):
    lots, _ = plan_batches(grocy_reel["stock"], catalogue_reel,
                           locations_reelles(), today="2026-08-21")
    assert len(lots) == 107


def test_a_batch_without_a_product_stops_the_import(catalogue_reel):
    """LE seul arrêt dur du §8. Après le rejeu du catalogue ce cas ne doit
    plus exister ; s'il existe, quelqu'un a écrit dans Grocy pendant la
    bascule, et alors rien de ce qui suit n'a de valeur."""
    with pytest.raises(StockImportError) as err:
        plan_batches([_lot(product_id=99999)], catalogue_reel,
                     locations_reelles(), today="2026-08-21")
    assert "99999" in str(err.value)


def test_kilograms_become_grams(catalogue_reel):
    lots, _ = plan_batches([_lot(product_id=2, amount=1.5, unit="kg")],
                           catalogue_reel, locations_reelles(), today="2026-08-21")
    assert lots[0].quantity == 1500.0
    assert lots[0].base_unit == "g"


def test_no_unit_is_unknown_on_the_real_data(grocy_reel, catalogue_reel):
    """0 unité inconnue, 0 divergence entre l'unité du lot et l'unité de base
    du produit : c'est ce que la spec a mesuré, et c'est ce qui rend
    reference_kcal juste sans reconversion."""
    _, anomalies = plan_batches(grocy_reel["stock"], catalogue_reel,
                                locations_reelles(), today="2026-08-21")
    assert not [a for a in anomalies if "unité" in a]


def test_floating_dust_enters_closed_not_ignored(catalogue_reel):
    """Le lot #537 (« Fromage fouetté ») porte 5,55e-17. Sous 0,001 unité de
    base il entre avec remaining = 0 et un closed_at. Un lot IGNORÉ serait un
    écart de comptage au contrôle C1 — ce n'est pas la même chose."""
    lots, _ = plan_batches([_lot(product_id=1, amount=5.55e-17)],
                           catalogue_reel, locations_reelles(), today="2026-08-21")
    assert len(lots) == 1
    assert lots[0].quantity == 0.0
    assert lots[0].closed is True


def test_fractional_pieces_are_never_rounded(catalogue_reel):
    """0,08 concombre et 12,875 œufs existent. L'arrondi est un geste
    d'affichage, jamais de stockage — le lot 0 stocke des REAL pour ça."""
    for quantite in (0.08, 12.875, 5.98):
        lots, _ = plan_batches([_lot(product_id=4, amount=quantite, unit="Pièce")],
                               catalogue_reel, locations_reelles(), today="2026-08-21")
        assert lots[0].quantity == quantite


def test_the_eighteen_fractional_piece_batches_on_real_data(grocy_reel, catalogue_reel):
    lots, _ = plan_batches(grocy_reel["stock"], catalogue_reel,
                           locations_reelles(), today="2026-08-21")
    fractionnaires = [l for l in lots
                      if l.base_unit == "piece" and l.quantity != int(l.quantity)]
    assert len(fractionnaires) == 18


def test_the_sentinel_becomes_null(catalogue_reel):
    lots, _ = plan_batches([_lot(product_id=1, best_before="2999-12-31")],
                           catalogue_reel, locations_reelles(), today="2026-08-21")
    assert lots[0].best_before is None


def test_the_ten_sentinels_and_the_ninety_eight_real_dates(grocy_reel, catalogue_reel):
    lots, _ = plan_batches(grocy_reel["stock"], catalogue_reel,
                           locations_reelles(), today="2026-08-21")
    assert len([l for l in lots if l.best_before is None]) == 10
    assert len([l for l in lots if l.best_before is not None]) == 97


def test_the_six_already_expired_batches_come_in_as_they_are(grocy_reel, catalogue_reel):
    """Ce sont de vrais produits périmés dans un vrai placard, et
    binary_sensor.home_stock_expirations doit s'allumer dessus le premier
    jour. Les masquer serait mentir au propriétaire sur son frigo."""
    lots, _ = plan_batches(grocy_reel["stock"], catalogue_reel,
                           locations_reelles(), today="2026-08-21")
    perimes = [l for l in lots if l.best_before and l.best_before < "2026-08-21"]
    assert len(perimes) == 6


def test_a_batch_worth_more_than_twenty_euros_loses_its_price(catalogue_reel):
    lots, anomalies = plan_batches(
        [_lot(product_id=1, amount=1487, price=2.45, note="Ticket Carrefour")],
        catalogue_reel, locations_reelles(), today="2026-08-21")
    assert lots[0].price_per_base_unit is None
    assert any("2,45" in a or "2.45" in a for a in anomalies)


def test_a_price_is_never_zero_only_null(catalogue_reel):
    """Règle du lot 0 §7.4 : zéro voudrait dire « mesuré à zéro », NULL veut
    dire « inconnu ». sensor.home_stock_stock_value publie unpriced_batches ;
    un prix inconnu est VISIBLE, un prix à zéro est invisible."""
    lots, _ = plan_batches([_lot(product_id=1, amount=1487, price=2.45)],
                           catalogue_reel, locations_reelles(), today="2026-08-21")
    assert lots[0].price_per_base_unit is not 0.0
    assert lots[0].price_per_base_unit is None


def test_the_seven_dropped_prices_and_the_fifty_seven_kept(grocy_reel, catalogue_reel):
    """7 lots sur 64 portent 8 089 EUR des 8 140 EUR. Les 57 autres pèsent
    51 EUR. Un chiffre petit et vrai plutôt qu'énorme et faux."""
    lots, anomalies = plan_batches(grocy_reel["stock"], catalogue_reel,
                                   locations_reelles(), today="2026-08-21")
    values = [l for l in lots if l.price_per_base_unit is not None]
    assert len(values) == 57
    assert len([a for a in anomalies if "prix" in a.lower()]) == 7
    total = sum(l.quantity * l.price_per_base_unit for l in values)
    assert 45 <= total <= 60          # ~51 EUR, et surtout pas 8 140


def test_the_boundary_is_a_ditch_not_a_line(catalogue_reel):
    """Le lot le plus cher retenu vaut 13,80 EUR (une brique de lait), le
    premier écarté en vaut 47. Rien ne vit entre les deux."""
    garde, _ = plan_batches([_lot(product_id=4, amount=1, price=13.80, unit="Pièce")],
                            catalogue_reel, locations_reelles(), today="2026-08-21")
    assert garde[0].price_per_base_unit == 13.80
    ecarte, _ = plan_batches([_lot(product_id=4, amount=1, price=47.0, unit="Pièce")],
                             catalogue_reel, locations_reelles(), today="2026-08-21")
    assert ecarte[0].price_per_base_unit is None


def test_an_anomaly_quotes_the_note_word_for_word(catalogue_reel):
    """Les notes sont la PREUVE du défaut : quatre des sept portent le nom
    d'un autre produit que celui auquel le lot est attaché. Elles doivent se
    lire dans le rapport, parce que batch.note n'existe pas."""
    _, anomalies = plan_batches(
        [_lot(product_id=1, amount=1000, price=1.79,
              note="Ticket Carrefour 21/04/2026 — Fromage blanc 1kg (CORRIGÉ)")],
        catalogue_reel, locations_reelles(), today="2026-08-21")
    assert any("Fromage blanc 1kg" in a for a in anomalies)


def test_the_location_cascade_in_its_three_cases(grocy_reel, catalogue_reel):
    """29 lots sur 108 n'ont pas d'emplacement résoluble : 27 tombent sur le
    default_location du produit, 2 sur « Autre » (ils pointent l'emplacement
    id 1, SUPPRIMÉ du référentiel — le même défaut que l'unité id 1 que
    debloquer_unites.py a dû réparer en août)."""
    lots, anomalies = plan_batches(grocy_reel["stock"], catalogue_reel,
                                   locations_reelles(), today="2026-08-21")
    assert all(l.location_id is not None for l in lots)
    replis = [a for a in anomalies if "Autre" in a]
    assert len(replis) == 2
    assert any("Moutarde Burger Complet" in a for a in replis)
    assert any("Beurre Oméga-3" in a for a in replis)


def test_no_batch_is_ever_refused_for_its_location(grocy_reel, catalogue_reel):
    """Un paquet mal rangé reste un paquet qu'on possède."""
    lots, _ = plan_batches(grocy_reel["stock"], catalogue_reel,
                           locations_reelles(), today="2026-08-21")
    assert len(lots) == 107


def test_an_open_batch_without_an_open_date_uses_its_entry_date(catalogue_reel):
    """Un seul lot est ouvert, et opened_date est vide même sur celui-là."""
    lots, _ = plan_batches(
        [_lot(product_id=1, open=1, opened_date=None,
              purchased="2026-05-02")], catalogue_reel,
        locations_reelles(), today="2026-08-21")
    assert lots[0].opened_at.startswith("2026-05-02")


def test_opening_never_recomputes_the_best_before(catalogue_reel):
    """La règle du lot 0 §7.6 (avancer la DLC de days_after_opening jours)
    s'applique au GESTE d'ouverture, pas à la constatation qu'un paquet est
    ouvert depuis six mois. L'appliquer ici donnerait une DLC calculée depuis
    une date d'entrée : faux dans les deux sens."""
    lots, _ = plan_batches(
        [_lot(product_id=3, open=1, best_before="2026-09-30",
              purchased="2026-05-02")], catalogue_reel,
        locations_reelles(), today="2026-08-21")
    assert lots[0].best_before == "2026-09-30"
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_import_grocy_stock.py -q --timeout=60`
Expected: FAIL — `ModuleNotFoundError: …import_grocy_stock`

- [ ] **Step 3: Écrire `plan_batches`**

Points obligatoires :
- Conversion par `grocy.units.base_unit()`, la **même** table que le lot 0 — jamais une seconde.
- `quantity < 0.001` → `quantity = 0.0` et `closed = True`, jamais un `continue`.
- `best_before == const.GROCY_NEVER_EXPIRES` → `None`.
- `quantity_grocy * price > const.GROCY_MAX_BATCH_VALUE` → `price_per_base_unit = None` **et** une anomalie qui cite produit, quantité, prix, valeur calculée **et la note mot pour mot**.
- Cascade d'emplacement : nom du lot → `product.default_location_id` → l'emplacement « Autre », anomalie non bloquante au troisième cran.
- `StockImportError` au premier lot non résolu, avec l'id Grocy dans le message.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_import_grocy_stock.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| `continue` au lieu du lot clos, sur la poussière flottante | `test_floating_dust_enters_closed_not_ignored` **et** `test_the_hundred_and_seven_batches_resolve` (106) |
| `price_per_base_unit = 0.0` au lieu de `None` | `test_a_price_is_never_zero_only_null` |
| Seuil à 200 € au lieu de 20 € | `test_the_seven_dropped_prices_and_the_fifty_seven_kept` (le total repasse à ~8 140 €) |
| `round(quantity, 0)` | `test_fractional_pieces_are_never_rounded` |

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/import_grocy_stock.py tests/test_import_grocy_stock.py
git commit -m "feat: plan the 107 batches — units, sentinels, the seven bad prices"
```

---

## Task 7: L'écriture du stock — un mouvement par lot, aucun compteur qui saute

**Files:**
- Modify: `custom_components/home_stock/import_grocy_stock.py` (`import_stock`, `StockReport`)
- Test: `tests/test_import_grocy_stock.py` (bloc « écriture »)

**Interfaces:**
- `import_stock(db, grocy_path, *, apply=False) -> StockReport`
- `StockReport` : `batches`, `movements`, `packagings`, `list_items`, `skipped`, `anomalies`, `ok`, `as_dict()`

**UNE seule transaction.** `import_stock` ouvre **un** `db.write()` et appelle des helpers `_within(conn, …)` en dessous. **`Database._lock` n'est pas réentrant : deux `db.write()` imbriqués figent le processus sans lever.** Aucun helper de ce lot n'ouvre sa propre transaction. Tous les tests de cette tâche portent `--timeout=60` : un test qui dépasse 60 s ici n'est pas lent, il est **gelé**, et le timeout est ce qui le dit.

**Pourquoi un mouvement par lot.** Le lot 0, § 12 pose que « le journal étant en ajout seul, il suffit à tout reconstruire ». Cent sept lots apparus sans une ligne de journal casseraient cet invariant : la base ne saurait plus dire d'où vient son stock, et `home_stock.export_journal` cesserait d'être un filet.

**Pourquoi ça ne fausse rien.** `repo.totals_between()` — source unique de `kcal_total`, `cost_total` et `cost_waste_total` — ne somme que `reason = 'consumption'` (et les motifs de gaspillage pour `waste_cost`). Un `purchase` n'y entre **jamais**. C'est le contrôle C6, et c'est prouvé par un test, pas supposé.

- [ ] **Step 1: Écrire les tests**

```python
# --- écriture ---------------------------------------------------------------

def test_a_dry_run_writes_nothing(db, grocy_reel_db):
    rapport = import_stock(db, grocy_reel_db, apply=False)
    assert rapport.batches == 107
    assert repo.stock_rows(db.read()) == []


def test_a_dry_run_reports_the_same_anomalies_as_a_real_run(db, grocy_reel_db):
    """C'est tout l'intérêt de le lancer avant : le rapport de simulation doit
    être celui qu'on lira après. import_grocy.py du lot 0 tient déjà cette
    promesse ; elle ne se relâche pas ici."""
    sec = import_stock(db, grocy_reel_db, apply=False)
    vrai = import_stock(db, grocy_reel_db, apply=True)
    assert sec.anomalies == vrai.anomalies


def test_apply_writes_a_hundred_and_seven_batches(db, grocy_reel_db):
    import_stock(db, grocy_reel_db, apply=True)
    conn = db.read()
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM batch WHERE external_ref IS NOT NULL"
    ).fetchone()["n"] == 107


def test_every_batch_carries_its_grocy_reference(db, grocy_reel_db):
    import_stock(db, grocy_reel_db, apply=True)
    refs = {row["external_ref"] for row in db.read().execute(
        "SELECT external_ref FROM batch WHERE external_ref IS NOT NULL")}
    assert all(ref.startswith("grocy:stock:") for ref in refs)
    assert len(refs) == 107        # l'index unique partiel tient


def test_one_purchase_movement_per_batch(db, grocy_reel_db):
    import_stock(db, grocy_reel_db, apply=True)
    conn = db.read()
    lignes = conn.execute(
        "SELECT idempotency_key FROM movement WHERE reason = 'purchase'"
        " AND idempotency_key LIKE 'grocy:stock:%'").fetchall()
    assert len(lignes) == 107


def test_the_three_totals_do_not_move(db, grocy_reel_db):
    """C6, prouvé mécaniquement. Un purchase n'entre jamais dans
    totals_between : ni kcal_total, ni cost_total, ni cost_waste_total."""
    avant = repo.totals_between(db.read())
    import_stock(db, grocy_reel_db, apply=True)
    apres = repo.totals_between(db.read())
    assert avant == apres


def test_entry_movements_carry_no_kcal_and_no_cost(db, grocy_reel_db):
    """Aucun capteur ne les lit sur une entrée, et un chiffre que personne ne
    lit finit par être cru."""
    import_stock(db, grocy_reel_db, apply=True)
    for row in db.read().execute(
            "SELECT kcal, cost FROM movement WHERE reason = 'purchase'"
            " AND idempotency_key LIKE 'grocy:stock:%'"):
        assert row["kcal"] is None and row["cost"] is None


def test_a_second_run_changes_nothing(db, grocy_reel_db):
    import_stock(db, grocy_reel_db, apply=True)
    empreinte = _empreinte(db)
    second = import_stock(db, grocy_reel_db, apply=True)
    assert second.batches == 0
    assert second.skipped == 107
    assert _empreinte(db) == empreinte


def test_a_replay_does_not_undo_a_real_consumption(db, grocy_reel_db):
    """LE test de la rejouabilité. On a mangé depuis l'import ; un second
    passage qui remettrait remaining = initial défferait une consommation
    réelle SANS LAISSER DE TRACE — et movement est en ajout seul, donc on ne
    pourrait même pas la retrouver."""
    import_stock(db, grocy_reel_db, apply=True)
    with db.write() as conn:
        lot = conn.execute(
            "SELECT id, remaining FROM batch WHERE external_ref IS NOT NULL"
            " AND remaining > 10 ORDER BY id LIMIT 1").fetchone()
        repo.set_batch_remaining(conn, lot["id"], lot["remaining"] - 10)
    import_stock(db, grocy_reel_db, apply=True)
    apres = db.read().execute(
        "SELECT remaining FROM batch WHERE id = ?", (lot["id"],)).fetchone()
    assert apres["remaining"] == lot["remaining"] - 10


def test_the_fridge_is_finally_a_fridge(db, grocy_reel_db):
    """Défaut hérité du lot 0 : l'import du catalogue mappe location.kind sur
    is_freezer, et Grocy n'a pas de drapeau « réfrigérateur ». « Frigo » est
    donc enregistré en pantry dans la base de production. Corrigé ici PAR NOM
    EXACT, une seule ligne, et rapporté. Aucun autre nom n'est deviné."""
    import_stock(db, grocy_reel_db, apply=True)
    row = db.read().execute(
        "SELECT kind FROM location WHERE name = 'Frigo'").fetchone()
    assert row["kind"] == "fridge"


def test_no_other_location_name_is_guessed(db, grocy_reel_db):
    import_stock(db, grocy_reel_db, apply=True)
    kinds = {row["name"]: row["kind"] for row in db.read().execute(
        "SELECT name, kind FROM location")}
    assert kinds["Congélateur"] == "freezer"
    assert kinds["Placard"] == "pantry"


def test_the_import_never_opens_a_second_transaction(db, grocy_reel_db):
    """Database._lock n'est pas réentrant : deux db.write() imbriqués figent
    le processus SANS lever. Ce test ne peut donc pas échouer proprement — il
    expire. C'est pour lui que --timeout=60 est sur toute la suite."""
    import_stock(db, grocy_reel_db, apply=True)     # doit rendre la main
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

```bash
docker ps --filter ancestor=home-stock-test
./scripts/test.sh tests/test_import_grocy_stock.py -q --timeout=60
```
Expected: FAIL — `import_stock` n'existe pas.

- [ ] **Step 3: Écrire `import_stock`**

Squelette imposé :

```python
def import_stock(db: Database, grocy_path: str, *, apply: bool = False) -> StockReport:
    report = StockReport()
    grocy = _open_grocy(grocy_path)          # file:...?mode=ro, comme le lot 0
    try:
        with db.write() as conn:             # UNE transaction, et une seule
            catalogue = _catalogue_within(conn)
            locations = _locations_within(conn)
            planned, anomalies = plan_batches(...)
            report.anomalies.extend(anomalies)
            deja = _existing_refs_within(conn)      # batch.external_ref
            for lot in planned:
                if lot.external_ref in deja:
                    report.skipped += 1
                    continue                 # JAMAIS de réécriture : on a mangé depuis
                ...
                repo.insert_movement(conn, ..., reason=REASON_PURCHASE,
                                     kcal=None, cost=None,
                                     idempotency_key=lot.external_ref)
            _fix_fridge_within(conn, report)
            _import_packagings_within(conn, grocy, report, apply=apply)
            _import_shopping_within(conn, grocy, report, apply=apply)
            if not apply:
                conn.rollback()
    finally:
        grocy.close()
    return report
```

`repo.insert_batch` ne prend pas `external_ref` : le poser par un `UPDATE batch SET external_ref = ? WHERE id = ?` juste après l'insertion, dans la **même** transaction. Ne pas élargir la signature de `repo.insert_batch` pour ça — c'est la seule table du schéma qui vient d'en gagner un, et un `**fields` de plus sur un `insert_*` du dépôt est une porte ouverte sur `remaining`.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_import_grocy_stock.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| Réécrire `remaining` sur un lot déjà importé | `test_a_replay_does_not_undo_a_real_consumption` |
| `reason=REASON_CONSUMPTION` au lieu de `REASON_PURCHASE` | `test_the_three_totals_do_not_move` — **et c'est la preuve de C6** |
| Ne pas écrire de mouvement du tout | `test_one_purchase_movement_per_batch` |
| Envelopper `_import_packagings_within` dans son propre `db.write()` | **la suite gèle** ; c'est ce que `--timeout=60` transforme en échec lisible |

Faire la dernière mutation **pour de vrai**, une fois, et constater le gel : c'est le seul moyen de savoir que le timeout protège.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/import_grocy_stock.py tests/test_import_grocy_stock.py
git commit -m "feat: import the stock — one entry movement each, and no counter moves"
```

---

## Task 8: 14 `packaging` et 9 lignes de courses

**Files:**
- Modify: `custom_components/home_stock/import_grocy_stock.py`
- Test: `tests/test_import_grocy_stock.py` (bloc « conversions et courses »)

**Interfaces:**
- `_import_packagings_within(conn, grocy, report, *, apply)` — `quantity_unit_conversions` → `packaging`
- `_import_shopping_within(conn, grocy, report, *, apply)` — les 9 lignes ouvertes → `shopping_list_item` + `shopping_list_claim` d'origine `manual`

**Une dette du lot 0 qui se referme.** Le lot 0 avait renoncé à créer des `packaging` (« le poids net viendra d'Open Food Facts au lot 1, via `product_quantity`, qui est une mesure et non une devinette ; `repo.insert_packaging` existe déjà et l'attend »). Les 30 lignes de `quantity_unit_conversions` sont **15 paires aller-retour saisies à la main par le propriétaire** : ce sont des mesures, exactement au même titre que `product_quantity`. On ne retient que le sens **conditionnement → unité de base**, et seulement quand l'unité d'arrivée se convertit vers `product.base_unit`.

**Ce que ça vaut :** à partir de là, `home_stock` sait qu'une bouteille d'huile fait 750 ml — donc que « 1 cs » n'en est pas une. C'est la moitié du problème des 23 lignes d'ingrédient de la tâche 11.

- [ ] **Step 1: Écrire les tests**

```python
def test_fifteen_pairs_become_fourteen_packagings(db, grocy_reel_db):
    """30 lignes, 15 paires aller-retour : le sens inverse est le même fait
    écrit deux fois. Et « 1 Lot = 1 Pot » est écartée — les deux deviennent
    piece, facteur 1, c'est un no-op."""
    rapport = import_stock(db, grocy_reel_db, apply=True)
    assert rapport.packagings == 14


def test_a_bottle_of_olive_oil_is_seven_hundred_and_fifty_millilitres(db, grocy_reel_db):
    import_stock(db, grocy_reel_db, apply=True)
    row = db.read().execute(
        "SELECT pk.base_quantity FROM packaging AS pk"
        " JOIN product AS p ON p.id = pk.target_id"
        " WHERE pk.scope = 'product' AND pk.name = 'Bouteille'"
        "   AND p.name LIKE 'Huile d%olive%'").fetchone()
    assert row["base_quantity"] == 750.0


def test_a_piece_packaging_carries_grams(db, grocy_reel_db):
    """« Houmous bio Pascalou 160g » : 1 Pièce = 160 g."""
    import_stock(db, grocy_reel_db, apply=True)
    row = db.read().execute(
        "SELECT pk.base_quantity FROM packaging AS pk"
        " JOIN product AS p ON p.id = pk.target_id"
        " WHERE pk.name = 'Pièce' AND p.name LIKE 'Houmous%'").fetchone()
    assert row["base_quantity"] == 160.0


def test_a_no_op_conversion_is_dropped(db, grocy_reel_db):
    """« 1 Lot = 1 Pot » sur le yaourt aux fruits : Lot et Pot deviennent tous
    deux piece, facteur 1. Une ligne packaging qui dit « une pièce vaut une
    pièce » est du bruit."""
    import_stock(db, grocy_reel_db, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM packaging WHERE name = 'Lot'"
    ).fetchone()["n"] == 0


def test_an_existing_packaging_is_never_overwritten(db, grocy_reel_db):
    """Le lot 1 a pu en créer depuis Open Food Facts, et une mesure
    d'emballage vaut mieux qu'une conversion de 2026."""
    import_stock(db, grocy_reel_db, apply=True)
    with db.write() as conn:
        conn.execute("UPDATE packaging SET base_quantity = 700 WHERE name = 'Bouteille'")
    import_stock(db, grocy_reel_db, apply=True)
    assert db.read().execute(
        "SELECT base_quantity FROM packaging WHERE name = 'Bouteille' LIMIT 1"
    ).fetchone()["base_quantity"] == 700


def test_only_the_nine_open_shopping_rows_come_over(db, grocy_reel_db):
    """16 lignes cochées : une course faite n'a pas d'après."""
    rapport = import_stock(db, grocy_reel_db, apply=True)
    assert rapport.list_items == 9
    assert len(repo.list_items(db.read())) == 9


def test_each_line_gets_a_manual_claim(db, grocy_reel_db):
    """Leur origine réelle est inconnaissable, et `manual` est la seule des
    quatre origines qui ne prétende rien."""
    import_stock(db, grocy_reel_db, apply=True)
    origines = {row["origin"] for row in db.read().execute(
        "SELECT origin FROM shopping_list_claim")}
    assert origines == {"manual"}


def test_the_three_notes_travel_as_they_are(db, grocy_reel_db):
    """Ce sont des prescriptions médicamenteuses. La colonne est faite pour ça."""
    import_stock(db, grocy_reel_db, apply=True)
    avec_note = [i for i in repo.list_items(db.read()) if i["note"]]
    assert len(avec_note) == 3


def test_the_unique_open_product_index_passes_without_arbitration(db, grocy_reel_db):
    """Les 9 produits sont actifs et distincts : idx_list_open_product tient
    sans qu'on ait à trancher quoi que ce soit."""
    import_stock(db, grocy_reel_db, apply=True)
    ids = [i["product_id"] for i in repo.list_items(db.read())]
    assert len(ids) == len(set(ids)) == 9


def test_a_sachet_and_a_paquet_are_both_pieces(db, grocy_reel_db):
    """« Cerneaux de noix » : Sachet contre Paquet. Les deux deviennent piece,
    facteur 1, aucune conversion — et surtout pas une division."""
    import_stock(db, grocy_reel_db, apply=True)
    ligne = next(i for i in repo.list_items(db.read())
                 if "Cerneaux" in (i.get("product_name") or ""))
    assert ligne["quantity"] == 1.0


def test_no_shopping_session_and_no_store_are_invented(db, grocy_reel_db):
    """shopping_locations est VIDE chez Grocy : rien pour amorcer l'ordre des
    rayons du lot 4, et on n'en fabrique pas."""
    import_stock(db, grocy_reel_db, apply=True)
    conn = db.read()
    assert conn.execute("SELECT COUNT(*) AS n FROM shopping_session").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM store").fetchone()["n"] == 0
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_import_grocy_stock.py -q --timeout=60 -k packaging or shopping or claim`
Expected: FAIL.

- [ ] **Step 3: Écrire les deux helpers**

Tous deux prennent `conn`, **jamais** `db` : ils tournent dans la transaction ouverte par `import_stock`.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_import_grocy_stock.py -q --timeout=60`
Expected: PASS, suite complète de la tâche 6 à 8.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Importer les 30 lignes au lieu des 14 : `test_fifteen_pairs_become_fourteen_packagings` doit tomber, et `test_a_no_op_conversion_is_dropped` aussi. Importer les 25 lignes de courses au lieu des 9 : `test_only_the_nine_open_shopping_rows_come_over`.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/import_grocy_stock.py tests/test_import_grocy_stock.py
git commit -m "feat: fourteen packagings and nine open shopping lines"
```

---

## Task 9: `grocy/pictures.py` — les images sous `media/`, et aucune vue HTTP

**Files:**
- Create: `custom_components/home_stock/grocy/pictures.py`
- Test: `tests/grocy/test_pictures.py`

**Interfaces:**
- `Reference(NamedTuple)` : `family` (`"inline" | "grocy" | "external"`), `src`, `filename | None`
- `references(description: str) -> list[Reference]`
- `nom_de_fichier(url: str) -> str` — décode le base64 du nom Grocy ; lève `PictureNameError` si le nom ne se décode pas
- `nom_inline(recipe_id: int, rank: int) -> str` → `recette-<id>-inline-<n>.jpg`
- `media_id(dossier: str, filename: str) -> str` → `media-source://media_source/local/<dossier>/<filename>`
- `reecrire(description, mapping) -> str` — remplace les `src` rapatriés, **laisse Unsplash intact**
- `ecrire_inline(payload_b64, chemin) -> int` — décode et écrit ; rend le nombre d'octets

**La décision, une fois pour les deux.** Le lot 0 avait prévu « une vue HTTP pour les images d'articles » ; elle n'a jamais été écrite. **Elle est abandonnée.** Depuis le lot 4 le composant n'écrit **aucune** vue HTTP — le téléversement d'un ticket passe par `/api/media_source/local_source/upload`, fourni par Home Assistant — et le lot 5 a posé « chemin sous `media/`, jamais sous `www/` ». Les images de recettes et d'articles suivent la même règle, et le panneau les résout par la commande **native** `media_source/resolve_media`.

Écartées, et elles le restent : `config/www/` (servi **sans authentification** à tout le réseau) ; une vue HTTP du composant (écrire, authentifier et tester ce que HA fournit déjà) ; les data-URI en base (3,48 Mo de base64 relus à chaque ouverture — le README de `grocy-off` a fait marche arrière là-dessus) ; laisser les URL Grocy (c'est tout le problème).

**Qui copie quoi.** Le conteneur Home Assistant ne monte que `config/` et `media/` : il **ne voit pas** `/opt/nivuus/Grocy/config/data/storage/`. Les 55 `recipepictures` et les 33 `productpictures` sont donc copiés **par le propriétaire**, geste 3 de la procédure. L'import ne fait que **décoder les 62 data-URI** (la donnée est dans la base qu'il lit déjà) et **réécrire les URL**. Les 112 références Unsplash restent où elles sont : le critère est « est-ce que ça meurt avec le conteneur ? », et Unsplash n'en dépend pas.

- [ ] **Step 1: Écrire les tests**

Créer `tests/grocy/test_pictures.py` :

```python
"""Les images : trois familles, une seule meurt.

Aucun test de ce fichier ne sort sur le réseau. Les URL Unsplash sont des
chaînes qu'on laisse tranquilles, jamais des adresses qu'on visite.
"""
import base64
import pytest

from custom_components.home_stock.grocy import pictures as gp


def test_the_three_families_on_the_real_data(grocy_reel):
    compte = {"inline": 0, "grocy": 0, "external": 0}
    for ligne in grocy_reel["recipes"]:
        for ref in gp.references(ligne["description"]):
            compte[ref.family] += 1
    assert compte == {"inline": 62, "grocy": 55, "external": 112}


def test_the_forty_six_distinct_unsplash_photos(grocy_reel):
    """112 emplacements, 46 images distinctes. Dette assumée et inscrite : le
    jour où elles tomberont, elles tomberont toutes ensemble."""
    vues = {ref.src for l in grocy_reel["recipes"]
            for ref in gp.references(l["description"]) if ref.family == "external"}
    assert len(vues) == 46


def test_a_grocy_url_decodes_to_its_file_name():
    """C'est du base64 du nom, sans clé d'API. Le décodage est fait par le
    code, jamais recopié à la main."""
    assert gp.nom_de_fichier(
        "https://grocy.allanic.me/api/files/recipepictures/cmVjZXR0ZS00MS0wLmpwZw=="
    ) == "recette-41-0.jpg"


def test_a_name_that_does_not_decode_is_an_anomaly_not_a_shrug():
    with pytest.raises(gp.PictureNameError):
        gp.nom_de_fichier("https://grocy.allanic.me/api/files/recipepictures/!!!!")


def test_the_fifty_five_grocy_names_all_decode(grocy_reel):
    for ligne in grocy_reel["recipes"]:
        for ref in gp.references(ligne["description"]):
            if ref.family == "grocy":
                assert ref.filename.endswith(".jpg")


def test_an_inline_name_is_deterministic():
    """Déterministe pour que le rejeu réécrive le MÊME fichier au lieu d'en
    accumuler un nouveau par passage : l'idempotence du §8.8, appliquée au
    système de fichiers."""
    assert gp.nom_inline(41, 0) == "recette-41-inline-0.jpg"
    assert gp.nom_inline(41, 0) == gp.nom_inline(41, 0)
    assert gp.nom_inline(41, 1) != gp.nom_inline(41, 0)


def test_a_media_id_is_never_a_www_path():
    """Le lot 5 a tranché : jamais sous www/, qui est servi SANS
    authentification à tout le réseau."""
    ident = gp.media_id("home_stock/recipes", "recette-41-0.jpg")
    assert ident == "media-source://media_source/local/home_stock/recipes/recette-41-0.jpg"
    assert "www" not in ident
    assert not ident.startswith("/local/")


def test_rewriting_replaces_grocy_and_inline_but_never_unsplash():
    html = (
        '<img src="https://grocy.allanic.me/api/files/recipepictures/'
        'cmVjZXR0ZS00MS0wLmpwZw==">'
        '<img src="data:image/jpeg;base64,AAAA">'
        '<img src="https://images.unsplash.com/photo-123">')
    sortie = gp.reecrire(html, {
        "https://grocy.allanic.me/api/files/recipepictures/cmVjZXR0ZS00MS0wLmpwZw==":
            "media-source://media_source/local/home_stock/recipes/recette-41-0.jpg",
        "data:image/jpeg;base64,AAAA":
            "media-source://media_source/local/home_stock/recipes/recette-1-inline-0.jpg",
    })
    assert "grocy.allanic.me" not in sortie
    assert "data:image" not in sortie
    assert "images.unsplash.com/photo-123" in sortie      # intact


def test_no_residual_grocy_url_after_rewriting_the_real_data(grocy_reel):
    """C9 en germe : 0 URL grocy.allanic.me résiduelle."""
    for ligne in grocy_reel["recipes"]:
        mapping = {r.src: "media-source://x" for r in gp.references(ligne["description"])
                   if r.family in ("grocy", "inline")}
        assert "grocy.allanic.me" not in gp.reecrire(ligne["description"], mapping)


def test_an_inline_payload_is_written_as_a_real_file(tmp_path, grocy_reel):
    """La recette 41 garde ses data-URI intacts dans les fixtures, et c'est
    elle qui prouve qu'on écrit un VRAI JPEG."""
    r41 = next(l for l in grocy_reel["recipes"] if l["id"] == 41)
    ref = next(r for r in gp.references(r41["description"]) if r.family == "inline")
    chemin = tmp_path / "recette-41-inline-0.jpg"
    octets = gp.ecrire_inline(ref.src, str(chemin))
    assert octets > 0
    assert chemin.stat().st_size == octets
    assert chemin.read_bytes()[:2] == b"\xff\xd8"      # un JPEG, pas du texte


def test_a_zero_byte_write_is_refused(tmp_path):
    """Un fichier de 0 octet passerait tous les contrôles de base et
    n'afficherait rien. C9 le rattraperait ; autant ne jamais l'écrire."""
    with pytest.raises(gp.PictureNameError):
        gp.ecrire_inline("data:image/jpeg;base64,", str(tmp_path / "vide.jpg"))


def test_reconciliation_reports_the_orphan_without_blocking():
    """0 référence sans fichier, 1 fichier sans référence (test.jpg). Le
    manquant bloque, l'orphelin se signale."""
    manquants, orphelins = gp.reconcilier(
        references={"a.jpg", "b.jpg"}, fichiers={"a.jpg", "b.jpg", "test.jpg"})
    assert manquants == set()
    assert orphelins == {"test.jpg"}


def test_a_missing_file_is_reported_as_missing():
    manquants, _ = gp.reconcilier(references={"a.jpg", "c.jpg"}, fichiers={"a.jpg"})
    assert manquants == {"c.jpg"}


def test_no_test_in_this_file_touches_the_network():
    import inspect
    source = inspect.getsource(gp)
    for interdit in ("urlopen", "requests.", "aiohttp", "httpx"):
        assert interdit not in source
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/grocy/test_pictures.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Écrire le module**

`ecrire_inline` est la **seule** fonction du paquet `grocy/` qui touche au système de fichiers ; elle est isolée en fin de module, prend un chemin déjà résolu, et **ne construit jamais de chemin elle-même** (c'est le rôle de `validators.picture_dir`).

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/grocy/ -q`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| Réécrire aussi les `src` Unsplash | `test_rewriting_replaces_grocy_and_inline_but_never_unsplash` |
| `nom_inline` avec `uuid4()` | `test_an_inline_name_is_deterministic` |
| `media_id` rendant `/local/…` | `test_a_media_id_is_never_a_www_path` |

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/grocy/pictures.py tests/grocy/test_pictures.py
git commit -m "feat: recipe and article pictures under media/, no HTTP view at all"
```

---

## Task 10: Les 102 recettes, leurs 338 étapes et leurs 561 instructions

**Files:**
- Create: `custom_components/home_stock/import_grocy_recipes.py`
- Test: `tests/test_import_grocy_recipes.py`

**Interfaces:**
- `import_recipes(db, grocy_path, *, picture_dir, apply=False) -> RecipeReport`
- `RecipeReport` : `recipes`, `steps`, `instructions`, `ingredients`, `pictures`, `meals`, `unmatched`, `anomalies`, `ok`, `as_dict()`

**L'amendement au lot 3, § 18 — le point le plus important de cette tâche.** Le lot 3 écrit que les 15 recettes de type `1` « sont les copies fantômes ». **C'est faux.** Ce sont **15 vraies recettes**, créées le 2026-06-27 entre 18 h 45 et 18 h 55 par un outil qui a écrit `type = 1` au lieu de `type = 'normal'` (Salade de lentilles fraîche, Bowl protéiné fromage blanc, Taboulé quinoa été…). Elles portent **96 lignes d'ingrédients** et **10 entrées de planning** les référencent. Un `WHERE type = 'normal'` strict, tel que le lot 3 le prescrit, perdrait **15 recettes et 96 lignes en silence**. Le filtre est :

```sql
WHERE rec.type IN ('normal', '1')
```

Il laisse dehors les **166 vraies copies fantômes** (86 `mealplan-shadow`, 65 `mealplan-day`, 15 `mealplan-week`), toutes à identifiant **négatif**, toutes générées par les triggers `create_internal_recipe`, `update_internal_recipe` et `remove_internal_recipe` de `meal_plan`. **Décompte final : 102 recettes.**

`recipe.needs_review = 1` sur les **17 recettes réécrites** (41, 43-50, 96-103) dont `grocy-off/README.md` dit que « les étapes, les titres, les durées de minuteur et les ustensiles sont **inventés** ». C'est exactement ce que `needs_review` veut dire.

- [ ] **Step 1: Écrire les tests**

```python
def test_a_hundred_and_two_recipes_come_over(db, grocy_reel_db, tmp_media):
    """87 normal + 15 de type 1. Le lot 3 §18 disait 87 et traitait les 15
    comme des fantômes : c'était faux, et ce test est l'amendement."""
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert rapport.recipes == 102


def test_the_fifteen_type_one_recipes_are_named(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    noms = {r["name"] for r in repo.list_recipes(db.read())}
    assert "Salade de lentilles fraîche" in noms
    assert "Bowl protéiné fromage blanc" in noms
    assert "Gaspacho andalou" in noms


def test_no_phantom_copy_gets_through(db, grocy_reel_db, tmp_media):
    """166 copies générées par trois triggers de meal_plan, toutes à
    identifiant NÉGATIF. Les importer créerait 166 recettes fantômes."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    refs = [r["source_ref"] for r in repo.list_recipes(db.read())]
    assert all(int(ref) > 0 for ref in refs)
    assert len(refs) == 102


def test_recipes_nestings_is_never_read(db, grocy_reel_db, tmp_media):
    """5 651 lignes, presque toutes produites par les mêmes triggers.
    Abandonnée — décision reprise du lot 3 §20."""
    import inspect
    from custom_components.home_stock import import_grocy_recipes
    assert "recipes_nestings" not in inspect.getsource(import_grocy_recipes)


def test_three_hundred_and_thirty_eight_steps(db, grocy_reel_db, tmp_media):
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert rapport.steps == 338


def test_five_hundred_and_sixty_one_instructions(db, grocy_reel_db, tmp_media):
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert rapport.instructions == 561


def test_a_hundred_and_sixteen_timers_land_in_the_database(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_instruction WHERE timer_seconds IS NOT NULL"
    ).fetchone()["n"] == 116


def test_the_ingredients_page_is_never_imported_as_a_step(db, grocy_reel_db, tmp_media):
    """Elle est un RENDU de recipes_pos, jamais une source. La réimporter
    serait la deuxième écriture d'une même quantité, encore."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    titres = {row["title"] for row in db.read().execute(
        "SELECT title FROM recipe_step WHERE title IS NOT NULL")}
    assert "Ingrédients" not in titres


def test_the_meta_line_fills_minutes_and_utensils(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    row = db.read().execute(
        "SELECT total_minutes, utensils, summary FROM recipe WHERE source_ref = '1'"
    ).fetchone()
    assert row["total_minutes"] and row["utensils"] and row["summary"]


def test_the_calculated_kcal_of_the_meta_line_is_not_stored(db, grocy_reel_db, tmp_media):
    """C'est une valeur calculée par recettes_miseenpage.py depuis le
    catalogue. La recalculer à l'affichage vaut mieux que graver un chiffre
    daté — le lot 3 §20 a déjà différé « nutriments avant cuisson »."""
    colonnes = {r["name"] for r in db.read().execute("PRAGMA table_info(recipe)")}
    assert "reference_kcal" not in colonnes


def test_the_seventeen_rewritten_recipes_need_review(db, grocy_reel_db, tmp_media):
    """41, 43-50, 96-103 : le README de grocy-off dit que leurs étapes, leurs
    minutages et leurs ustensiles sont INVENTÉS."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    refs = {row["source_ref"] for row in db.read().execute(
        "SELECT source_ref FROM recipe WHERE needs_review = 1")}
    assert refs == {"41", *(str(n) for n in range(43, 51)),
                    *(str(n) for n in range(96, 104))}
    assert len(refs) == 17


def test_adapted_at_stays_null(db, grocy_reel_db, tmp_media):
    """Aucun agent n'a adapté ces recettes."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe WHERE adapted_at IS NOT NULL"
    ).fetchone()["n"] == 0


def test_the_sixty_two_inline_images_become_files(db, grocy_reel_db, tmp_media):
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    ecrits = list((tmp_media / "recipes").glob("*-inline-*.jpg"))
    assert len(ecrits) == 62
    assert rapport.pictures == 62


def test_no_image_url_still_points_at_grocy(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    conn = db.read()
    for table in ("recipe", "recipe_step"):
        assert conn.execute(
            f"SELECT COUNT(*) AS n FROM {table}"
            " WHERE image_url LIKE '%grocy.allanic.me%'").fetchone()["n"] == 0


def test_every_written_file_weighs_more_than_zero(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    for chemin in (tmp_media / "recipes").iterdir():
        assert chemin.stat().st_size > 0


def test_a_dry_run_writes_neither_rows_nor_files(db, grocy_reel_db, tmp_media):
    """Un import en simulation qui écrirait quand même les 6,5 Mo d'images
    serait une écriture déguisée. Le rollback SQL ne couvre pas le disque :
    c'est au code de ne pas écrire."""
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=False)
    assert rapport.recipes == 102
    assert repo.list_recipes(db.read()) == []
    assert not list(tmp_media.rglob("*.jpg"))


def test_a_second_run_changes_nothing(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    second = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert second.recipes == 0
    assert repo.list_recipes(db.read()).__len__() == 102


def test_a_replayed_inline_image_overwrites_instead_of_accumulating(
        db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    avant = sorted(p.name for p in (tmp_media / "recipes").iterdir())
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert sorted(p.name for p in (tmp_media / "recipes").iterdir()) == avant


def test_the_import_runs_in_one_transaction(db, grocy_reel_db, tmp_media):
    """Database._lock n'est pas réentrant. Ce test rend la main ou il gèle."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_import_grocy_recipes.py -q --timeout=60`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Écrire l'import**

Une transaction, `_within` en dessous, `apply` qui gouverne **et** les écritures SQL **et** les écritures de fichiers. Les images sont écrites **avant** le `rollback` conditionnel — donc protégées par un `if apply` explicite, pas par la transaction.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_import_grocy_recipes.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| `WHERE rec.type = 'normal'` | `test_a_hundred_and_two_recipes_come_over` (87), `test_the_fifteen_type_one_recipes_are_named` |
| `WHERE rec.type != 'mealplan-day'` | `test_no_phantom_copy_gets_through` (les négatifs entrent) |
| Écrire les images même sans `apply` | `test_a_dry_run_writes_neither_rows_nor_files` |

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/import_grocy_recipes.py tests/test_import_grocy_recipes.py
git commit -m "feat: 102 recipes — the fifteen type-1 ones were never phantoms"
```

---

## Task 11: Les 510 lignes d'ingrédients, dont 25 à arbitrer

**Files:**
- Modify: `custom_components/home_stock/import_grocy_recipes.py`
- Test: `tests/test_import_grocy_recipes.py` (bloc « ingrédients »)

**Interfaces:**
- `_import_ingredients_within(conn, grocy, recipe_ids, report, *, apply)`

**La règle, et ce qu'elle refuse.** Sur les **414 lignes des 87 recettes `normal`** : 0 ligne sans produit, 0 ligne pointant un produit inactif, **0 ligne dont `qu_id` diffère du `qu_id_stock` de son produit**. Sur les **96 lignes des 15 recettes de type `1`**, c'est une autre histoire : **23 lignes** portent une unité divergente et **2** pointent un produit inactif. Les 23 sont le défaut que le README de `grocy-off` décrit — « 42 lignes portaient l'unité de conditionnement (`1.5 Bouteille` d'huile d'olive) alors que le nombre était déjà en cl » — **jamais corrigé sur ces quinze recettes**, parce que `recettes_ingredients.py` filtre sur `type = 'normal'`. **Treize disent « 1 Bouteille » d'huile d'olive quand `variable_amount` dit « 1 cs »** : importées telles quelles, elles retireraient **750 ml d'huile pour une cuillère à soupe, à chaque repas validé**.

Une ligne divergente entre avec `amount = NULL`, `product_id` résolu, `match_state = 'unmatched'`, `raw_text = variable_amount`, et est **citée nommément** dans le rapport.

**On ne lit pas `variable_amount` pour retrouver la quantité.** « 1 cs » se résoudrait pourtant contre `culinary_measure` (semée par `m004`). **Refusé** : règle du lot 3, § 18 — `variable_amount` est de la provenance, « il ne revient pas par la porte de derrière ». Vingt-cinq lignes se corrigent à la main en dix minutes sur l'écran d'appariement du lot 3 ; un analyseur se corrigerait pendant des années.

**`match_state` des 485 autres : `'confirmed'`.** Le lot 3 réserve `'auto'` à un appariement **deviné et scoré** ; ici rien n'est deviné, le produit vient d'un identifiant. `match_score` reste `NULL` — écrire `1.0` laisserait croire qu'un algorithme a été très sûr de lui.

- [ ] **Step 1: Écrire les tests**

```python
def test_five_hundred_and_ten_ingredient_rows(db, grocy_reel_db, tmp_media):
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert rapport.ingredients == 510


def test_the_two_hundred_orphan_rows_are_left_out(db, grocy_reel_db, tmp_media):
    """710 lignes dans recipes_pos, 200 orphelines : leur recipe_id ne
    correspond à aucune ligne de recipes. Un LEFT JOIN les ramènerait ; le
    JOIN du filtre les écarte."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient").fetchone()["n"] == 510


def test_four_hundred_and_eighty_five_are_confirmed(db, grocy_reel_db, tmp_media):
    """« confirmed », pas « auto » : le lot 3 réserve auto à un appariement
    deviné et scoré. Ici le produit vient d'un identifiant."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    compte = {row["match_state"]: row["n"] for row in db.read().execute(
        "SELECT match_state, COUNT(*) AS n FROM recipe_ingredient GROUP BY match_state")}
    assert compte == {"confirmed": 485, "unmatched": 25}


def test_match_score_is_never_written(db, grocy_reel_db, tmp_media):
    """Écrire 1.0 laisserait croire qu'un algorithme a été très sûr de lui."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient WHERE match_score IS NOT NULL"
    ).fetchone()["n"] == 0


def test_the_twenty_three_diverging_units_lose_their_quantity(db, grocy_reel_db, tmp_media):
    """Treize disent « 1 Bouteille » d'huile d'olive quand variable_amount dit
    « 1 cs ». Importées telles quelles, elles retireraient 750 ml d'huile pour
    une cuillère à soupe, À CHAQUE REPAS VALIDÉ."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    lignes = db.read().execute(
        "SELECT amount, product_id FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND product_id IS NOT NULL").fetchall()
    assert len(lignes) == 23
    assert all(l["amount"] is None for l in lignes)
    assert all(l["product_id"] is not None for l in lignes)   # le produit est certain


def test_the_two_inactive_product_rows_have_no_product(db, grocy_reel_db, tmp_media):
    """« Riz basmati (doublon) » est désactivé chez Grocy, donc jamais importé
    au lot 0. Le rapport nomme le produit actif correspondant : c'est un
    appariement que seul un humain peut signer."""
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    lignes = db.read().execute(
        "SELECT amount FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND product_id IS NULL").fetchall()
    assert len(lignes) == 2
    assert any("Riz Basmati" in a for a in rapport.anomalies)


def test_every_diverging_line_is_named_in_the_report(db, grocy_reel_db, tmp_media):
    """Avec sa recette, son produit, la quantité Grocy, LES DEUX unités et le
    variable_amount. Sans ça, « 25 lignes à arbitrer » n'est pas actionnable."""
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    citees = [a for a in rapport.anomalies if "unité" in a]
    assert len(citees) == 23
    huile = [a for a in citees if "Huile d" in a]
    assert len(huile) == 13
    assert all("Bouteille" in a and "cs" in a for a in huile)


def test_variable_amount_is_never_parsed_into_a_quantity(db, grocy_reel_db, tmp_media):
    """Règle du lot 3 §18. Le grief n° 2 du lot 0 ne revient pas par la porte
    de derrière : aucune ligne unmatched ne repart avec une quantité."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND amount IS NOT NULL").fetchone()["n"] == 0
    import inspect
    from custom_components.home_stock import import_grocy_recipes
    source = inspect.getsource(import_grocy_recipes)
    assert "culinary_measure" not in source


def test_variable_amount_travels_as_provenance(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    row = db.read().execute(
        "SELECT raw_text FROM recipe_ingredient"
        " WHERE match_state = 'unmatched' AND raw_text LIKE '%cs%' LIMIT 1").fetchone()
    assert row is not None


def test_the_fifty_six_rows_without_variable_amount_get_a_composed_raw_text(
        db, grocy_reel_db, tmp_media):
    """raw_text est NOT NULL et 56 lignes n'ont pas de variable_amount. Il est
    composé mécaniquement — « 500 g », « 2 Pièce » : le même nombre dans la
    même unité, ce que la source disait. Rien d'inventé."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient"
        " WHERE raw_text IS NULL OR raw_text = ''").fetchone()["n"] == 0


def test_group_name_stays_null(db, grocy_reel_db, tmp_media):
    """ingredient_group est VIDE sur les 510 lignes : la ligne du lot 3 §18
    (« → group_name, direct ») est sans objet."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient WHERE group_name IS NOT NULL"
    ).fetchone()["n"] == 0


def test_packaging_and_measure_stay_null_on_the_confirmed_lines(
        db, grocy_reel_db, tmp_media):
    """0 ligne dont qu_id diffère du qu_id_stock, sur les 414 normal : il n'y
    a rien à exprimer dans une autre mesure."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient"
        " WHERE match_state = 'confirmed'"
        "   AND (packaging_id IS NOT NULL OR measure_id IS NOT NULL)"
    ).fetchone()["n"] == 0


def test_not_check_stock_fulfillment_is_reported_not_stored(db, grocy_reel_db, tmp_media):
    """4 lignes. Aucune colonne équivalente, sans effet sur la validation d'un
    repas qui vérifie le stock de toute façon. Mentionné au rapport."""
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True)
    assert any("stock_fulfillment" in a or "hors stock" in a for a in rapport.anomalies)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_import_grocy_recipes.py -q --timeout=60 -k ingredient or unmatched or raw_text`
Expected: FAIL.

- [ ] **Step 3: Écrire `_import_ingredients_within`**

Résolution du produit **par `product.external_ref`, jamais par nom**. Comparaison `qu_id` vs `qu_id_stock` **avant** toute conversion.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_import_grocy_recipes.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| Convertir la ligne divergente au lieu de la laisser à `NULL` | `test_the_twenty_three_diverging_units_lose_their_quantity` |
| `match_state = 'auto'` et `match_score = 1.0` | `test_four_hundred_and_eighty_five_are_confirmed`, `test_match_score_is_never_written` |
| Analyser « 1 cs » contre `culinary_measure` | `test_variable_amount_is_never_parsed_into_a_quantity` |

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/import_grocy_recipes.py tests/test_import_grocy_recipes.py
git commit -m "feat: 510 ingredient rows, 25 of them left for a human to sign"
```

---

## Task 12: Le planning — l'avenir, et rien que l'avenir

**Files:**
- Modify: `custom_components/home_stock/import_grocy_recipes.py`
- Test: `tests/test_import_grocy_recipes.py` (bloc « planning »)

**Interfaces:**
- `_import_meal_plan_within(conn, grocy, recipe_ids, report, *, today, apply)`

**La décision, qui n'admet pas de milieu.** `meal_plan` compte **108 entrées**, **42 à venir**. Les 66 passées sont abandonnées :
- les importer `state = 'done'` affirmerait des repas validés — or **valider un repas écrit des mouvements** (lot 3), et il n'y en aurait aucun derrière. Un repas `done` sans mouvement est un mensonge dans une base dont le journal est la seule source de vérité ;
- les importer `planned` peuplerait le calendrier de 66 repas à cuisiner dans le passé, et `sensor.home_stock_next_meal` irait les chercher.

**Cette décision referme d'elle-même le seul problème de correspondance du planning.** `meal_plan_sections` porte une quatrième ligne, **`id = -1`, sans nom** — le « sans section » de Grocy, que `m004` n'a pas semée. **30 entrées l'utilisent, et les 30 sont dans le passé.** Les 42 à venir se répartissent proprement : 12 `breakfast`, 19 `lunch`, 11 `dinner`, **0** sans section.

- [ ] **Step 1: Écrire les tests**

```python
def test_forty_two_future_meals_come_over(db, grocy_reel_db, tmp_media):
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media,
                             apply=True, today="2026-08-21")
    assert rapport.meals == 42


def test_the_sixty_six_past_entries_stay_out(db, grocy_reel_db, tmp_media):
    """Un plan passé n'est ni un repas mangé ni un repas à cuisiner."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM meal WHERE day < '2026-08-21'").fetchone()["n"] == 0


def test_no_meal_is_ever_written_done(db, grocy_reel_db, tmp_media):
    """Valider un repas écrit des mouvements. Un repas done sans mouvement
    derrière est un mensonge dans une base dont le journal est la seule
    source de vérité — et meal_plan.done est donc IGNORÉ."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    etats = {row["state"] for row in db.read().execute("SELECT state FROM meal")}
    assert etats == {"planned"}


def test_the_minus_one_section_never_has_to_be_mapped(db, grocy_reel_db, tmp_media):
    """30 entrées utilisent la section -1 (le « sans section » de Grocy, que
    m004 n'a pas semée) et LES TRENTE SONT DANS LE PASSÉ. La décision de ne
    reprendre que l'avenir referme ce problème d'elle-même."""
    rapport = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                             today="2026-08-21")
    assert not [a for a in rapport.anomalies if "section" in a.lower()]


def test_the_three_slots_get_their_share(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    compte = {row["slot_key"]: row["n"] for row in db.read().execute(
        "SELECT slot_key, COUNT(*) AS n FROM meal GROUP BY slot_key")}
    assert compte == {"breakfast": 12, "lunch": 19, "dinner": 11}


def test_the_two_notes_travel_without_a_recipe(db, grocy_reel_db, tmp_media):
    """20 des 108 entrées sont des notes ; 2 d'entre elles sont à venir."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    assert db.read().execute(
        "SELECT COUNT(*) AS n FROM meal WHERE recipe_id IS NULL AND note IS NOT NULL"
    ).fetchone()["n"] == 2


def test_fractional_servings_pass_as_they_are(db, grocy_reel_db, tmp_media):
    """0,15 ; 0,2 ; 0,25 sur 10 entrées. meal.servings est un REAL avec
    CHECK (servings > 0) : elles passent telles quelles, sans arrondi."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    valeurs = [row["servings"] for row in db.read().execute(
        "SELECT servings FROM meal WHERE servings < 1")]
    assert len(valeurs) == 10
    assert 0.15 in valeurs


def test_the_uid_makes_replay_free(db, grocy_reel_db, tmp_media):
    """meal.uid est UNIQUE : l'idempotence du planning est gratuite."""
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    uids = {row["uid"] for row in db.read().execute("SELECT uid FROM meal")}
    assert len(uids) == 42
    assert all(u.startswith("grocy-meal-") and u.endswith("@home_stock") for u in uids)
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    assert db.read().execute("SELECT COUNT(*) AS n FROM meal").fetchone()["n"] == 42


def test_the_forty_two_reach_twenty_three_distinct_recipes(db, grocy_reel_db, tmp_media):
    import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=True,
                   today="2026-08-21")
    ids = {row["recipe_id"] for row in db.read().execute(
        "SELECT recipe_id FROM meal WHERE recipe_id IS NOT NULL")}
    assert len(ids) == 23


def test_an_entry_pointing_at_a_missing_recipe_stops_the_plan(db, grocy_reel_db,
                                                              tmp_media):
    """Le planning se réimporte en dix secondes ; une entrée orpheline se
    découvre au dîner."""
    with pytest.raises(RecipeImportError):
        import_recipes(db, _plan_pointant_une_recette_absente(grocy_reel_db),
                       picture_dir=tmp_media, apply=True, today="2026-08-21")


def test_the_horizon_moves_with_today(db, grocy_reel_db, tmp_media):
    """« À venir » se calcule au jour de la bascule, jamais sur une date
    figée : la cible bouge, et le code compte ce qu'il trouve."""
    tot = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=False,
                         today="2026-03-01").meals
    tard = import_recipes(db, grocy_reel_db, picture_dir=tmp_media, apply=False,
                          today="2026-08-31").meals
    assert tot == 108
    assert tard < 42
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_import_grocy_recipes.py -q --timeout=60 -k meal or plan or slot`
Expected: FAIL.

- [ ] **Step 3: Écrire `_import_meal_plan_within`**

`today` est un **paramètre**, avec `None` = date du jour. Ne jamais écrire `"2026-08-21"` dans le code de production.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/ -q --timeout=60 -x`
Expected: PASS, et le total Python remonte à **1914 + les tests des tâches 1 à 12**.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| Importer les 108 entrées | `test_forty_two_future_meals_come_over`, `test_the_sixty_six_past_entries_stay_out`, `test_the_minus_one_section_never_has_to_be_mapped` |
| `state = 'done'` sur les entrées `done` de Grocy | `test_no_meal_is_ever_written_done` |
| `round(servings)` | `test_fractional_servings_pass_as_they_are` |

La première mutation doit faire tomber **trois** tests, dont celui de la section `-1` : c'est la preuve que la décision « l'avenir seulement » referme bien ce problème, et non un hasard.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/import_grocy_recipes.py tests/test_import_grocy_recipes.py
git commit -m "feat: the 42 meals ahead, and why the 66 behind would be a lie"
```

---

## Task 13: Les contrôles C0 à C6 — et leurs planchers

**Files:**
- Create: `custom_components/home_stock/migration_check.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/test_migration_check.py`

**Interfaces:**
- `CheckResult(NamedTuple)` : `code`, `label`, `grocy_count`, `home_count`, `gap`, `verdict` (`"ok" | "empty" | "gap" | "unacknowledged"`), `blocking: bool`, `details: list[str]` (plafonnée à **50** entrées)
- `check_migration(db, grocy_path, *, acknowledged=(), archive=True, now=None) -> CheckReport`
- `CheckReport` : `checks: list[CheckResult]`, `blocking: list[str]`, `ok: bool`, `archive_path: str | None`, `as_dict()`
- `const.MIGRATION_CHECKS: tuple[str, ...] = ("C0", "C1", …, "C11")`

> **La leçon du lot 6, recopiée pour qu'elle ne se reperde pas.** Son vérificateur ouvrait les pages contre l'instance réelle ; les commandes websocket n'existaient pas encore, « il mesure un écran vide et déclare que tout va bien ». **Un contrôle qui passe à vide est pire que pas de contrôle** : il transforme une absence de donnée en preuve de succès.

**Chaque contrôle porte donc un plancher** : un seuil en dessous duquel il échoue *parce qu'il n'a rien mesuré*, indépendamment de tout écart. **Un contrôle qui compare 0 à 0 est rouge, jamais vert.** C'est le cœur du lot, et cette tâche est celle dont les tests comptent le plus.

| # | Contrôle | Plancher — échoue si | Bloquant |
|---|---|---|---|
| **C0** | Schéma et gel : `schema_version = 8`, copie de moins de 2 h, Grocy n'a rien écrit depuis (`MAX(row_created_timestamp)` de `stock`, `stock_log`, `products`, `meal_plan`) | version < 8, ou copie absente | **Oui** |
| **C1** | Un `batch` par ligne de `stock`, apparié par `external_ref` | `stock` Grocy vide **ou** `batch` importés = 0 | **Oui**, tout écart |
| **C2** | `batch.remaining` = `amount × facteur`, à **10⁻⁶** près | idem C1 | **Oui**, tout écart |
| **C3** | `best_before` = date Grocy, sauf les 10 sentinelles attendues à `NULL` | 0 lot daté | **Oui** si l'écart n'est pas une sentinelle |
| **C4** | Les lots à `price_per_base_unit IS NULL` sont **exactement** les 50 attendus (43 sans prix + 7 écartés), chacun nommé avec sa note | 0 lot valorisé | **Oui** tant que les 7 ne sont pas **acquittés** |
| **C5** | Un `movement` `purchase` par `batch`, `idempotency_key = grocy:stock:<id>` ; `SUM(quantity)` par produit = stock du produit | `movement` importés = 0 | **Oui** |
| **C6** | `kcal_total`, `cost_total`, `cost_waste_total` **n'ont pas bougé** | les trois lus à `unknown` | **Oui** |

- [ ] **Step 1: Écrire les tests — les planchers D'ABORD**

Créer `tests/test_migration_check.py`. **Écrire les trois tests de plancher avant tout autre**, parce qu'ils sont la raison d'être du module :

```python
"""Les onze contrôles, et surtout : un contrôle qui ne mesure rien échoue.

Les trois premiers tests de ce fichier sont les plus importants du lot 7. Ils
rejouent, un par un, les trois cas réels du §16.3 — ceux qu'un contrôle naïf
laisse passer en affichant « écart : 0 ». Le lot 6 a démontré qu'un
vérificateur qui mesure du vide déclare tout conforme ; ces tests sont ce qui
empêche cette panne de se rejouer.
"""
import pytest

from custom_components.home_stock.migration_check import check_migration


# --- les planchers ----------------------------------------------------------

def test_a_forgotten_copy_of_grocy_db_fails_before_anything_else(db, tmp_path):
    """Cas 1 du §16.3 : la copie a été oubliée. Sans plancher, C1 compare
    0 lot à 0 lot et affiche « écart : 0 ». C0 doit échouer D'ABORD, sur la
    fraîcheur — sinon les dix autres contrôles mentent en cascade."""
    rapport = check_migration(db, str(tmp_path / "absente.db"), archive=False)
    assert rapport.ok is False
    c0 = _check(rapport, "C0")
    assert c0.verdict == "empty"
    assert c0.blocking is True
    assert "C0" in rapport.blocking


def test_a_dry_run_left_in_simulation_is_red_not_green(db, grocy_reel_db):
    """Cas 2 du §16.3 : l'import est resté en simulation. C1 trouve 0 batch
    et ÉCHOUE, au lieu de « 0 écart sur 0 lot »."""
    rapport = check_migration(db, grocy_reel_db, archive=False)
    c1 = _check(rapport, "C1")
    assert c1.home_count == 0
    assert c1.grocy_count == 108
    assert c1.verdict == "empty"        # et surtout PAS "ok"
    assert c1.blocking is True


def test_a_check_that_compares_zero_to_zero_is_never_green(db, tmp_path):
    """Le principe, isolé : deux bases vides ne prouvent rien. Ce test tient
    pour LES ONZE contrôles, pas seulement pour C1 — c'est ce qui interdit
    d'en ajouter un douzième sans plancher."""
    vide = _grocy_vide(tmp_path)
    rapport = check_migration(db, vide, archive=False)
    for controle in rapport.checks:
        assert controle.verdict != "ok", controle.code
    assert rapport.ok is False


def test_every_declared_check_has_a_floor():
    """Garde-fou structurel : un contrôle sans plancher ne doit pas pouvoir
    exister dans le module."""
    from custom_components.home_stock import migration_check as mc
    from custom_components.home_stock.const import MIGRATION_CHECKS
    assert len(MIGRATION_CHECKS) == 12          # C0..C11
    for code in MIGRATION_CHECKS:
        assert code in mc.FLOORS, code
        assert callable(mc.FLOORS[code])


# --- C0 ---------------------------------------------------------------------

def test_c0_refuses_a_schema_below_eight(db_schema_seven, grocy_reel_db):
    rapport = check_migration(db_schema_seven, grocy_reel_db, archive=False)
    c0 = _check(rapport, "C0")
    assert c0.verdict != "ok"
    assert "8" in " ".join(c0.details)


def test_c0_refuses_a_copy_older_than_two_hours(db, grocy_reel_db, monkeypatch):
    rapport = check_migration(db, grocy_reel_db, archive=False,
                              now="2026-08-22T09:00:00")
    assert _check(rapport, "C0").verdict != "ok"


def test_c0_catches_a_write_that_happened_after_the_copy(db, grocy_ecrit_apres):
    """LA cible mobile. Un produit créé dans Grocy après la copie invalide
    TOUS les autres contrôles : C0 le dit avant qu'ils mentent. C'est
    exactement le scénario du Sorbet Fraise, créé le 21 août à 18 h 54."""
    rapport = check_migration(db, grocy_ecrit_apres, archive=False)
    c0 = _check(rapport, "C0")
    assert c0.blocking is True
    assert any("écrit" in d for d in c0.details)


# --- C1, C2, C3 -------------------------------------------------------------

def test_c1_matches_batch_for_batch(db_migre, grocy_reel_db):
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    c1 = _check(rapport, "C1")
    assert c1.grocy_count == 108 and c1.home_count == 108
    assert c1.gap == 0 and c1.verdict == "ok"


def test_c1_names_a_missing_batch(db_migre, grocy_reel_db):
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET external_ref = NULL WHERE id ="
                     " (SELECT MIN(id) FROM batch WHERE external_ref IS NOT NULL)")
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    c1 = _check(rapport, "C1")
    assert c1.gap == 1 and c1.blocking is True
    assert c1.details                     # nommé, pas juste compté


def test_c2_compares_quantities_to_a_millionth(db_migre, grocy_reel_db):
    """10⁻⁶ unité de base : assez serré pour attraper une conversion ratée,
    assez lâche pour ne pas se battre avec les flottants."""
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    assert _check(rapport, "C2").verdict == "ok"
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = remaining + 0.01"
                     " WHERE external_ref = 'grocy:stock:419'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C2").verdict == "gap"


def test_c2_tolerates_a_millionth(db_migre, grocy_reel_db):
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = remaining + 1e-9"
                     " WHERE external_ref = 'grocy:stock:419'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C2").verdict == "ok"


def test_c3_expects_the_ten_sentinels_at_null(db_migre, grocy_reel_db):
    rapport = check_migration(db_migre, grocy_reel_db, archive=False)
    c3 = _check(rapport, "C3")
    assert c3.verdict == "ok"
    assert any("2999-12-31" in d for d in c3.details)   # documenté, pas caché


def test_c3_flags_a_null_that_is_not_a_sentinel(db_migre, grocy_reel_db):
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET best_before = NULL"
                     " WHERE external_ref = 'grocy:stock:255'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C3").blocking is True


# --- C4 ---------------------------------------------------------------------

def test_c4_expects_exactly_fifty_unpriced_batches(db_migre, grocy_reel_db):
    """43 sans prix chez Grocy + les 7 écartés du §8.4. « Exactement » : un
    prix perdu en plus est aussi grave qu'un prix aberrant conservé."""
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C4")
    assert c4.home_count == 50


def test_c4_blocks_until_the_seven_are_acknowledged(db_migre, grocy_reel_db):
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C4")
    assert c4.verdict == "unacknowledged"
    assert c4.blocking is True
    assert len(c4.details) == 7
    assert any("Fromage blanc 1kg" in d for d in c4.details)   # la note, mot pour mot


def test_c4_passes_once_the_seven_are_named(db_migre, grocy_reel_db):
    sept = ["grocy:stock:241", "grocy:stock:250", "grocy:stock:255",
            "grocy:stock:256", "grocy:stock:257", "grocy:stock:264",
            "grocy:stock:419"]
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                acknowledged=sept), "C4")
    assert c4.verdict == "ok" and c4.blocking is False


def test_acknowledging_six_of_seven_is_not_acknowledging(db_migre, grocy_reel_db):
    c4 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                acknowledged=["grocy:stock:241"]), "C4")
    assert c4.blocking is True


# --- C5, C6 -----------------------------------------------------------------

def test_c5_wants_one_purchase_movement_per_batch(db_migre, grocy_reel_db):
    c5 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C5")
    assert c5.verdict == "ok" and c5.home_count == 107


def test_c5_checks_the_sum_per_product_too(db_migre, grocy_reel_db):
    """Un mouvement par lot ne suffit pas : SUM(quantity) par produit doit
    égaler le stock du produit, sinon le journal ne reconstruit plus rien."""
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = remaining / 2"
                     " WHERE external_ref = 'grocy:stock:419'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C5").verdict == "gap"


def test_c6_proves_the_three_totals_never_moved(db_migre, grocy_reel_db):
    """La preuve MÉCANIQUE du §8.7 : un purchase n'entre jamais dans
    totals_between. C'est le même mécanisme qui interdit la réinjection de
    l'historique au §9."""
    c6 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C6")
    assert c6.verdict == "ok"
    assert set(c6.details) >= {"kcal_total", "cost_total", "cost_waste_total"}


def test_c6_fails_when_the_three_are_unknown(db_vide, grocy_reel_db):
    """Plancher : trois compteurs à `unknown` ne prouvent rien du tout."""
    assert _check(check_migration(db_vide, grocy_reel_db, archive=False),
                  "C6").verdict == "empty"


def test_details_are_capped_at_fifty(db_migre, grocy_reel_db):
    """Le reste part dans l'archive : un rapport de 500 lignes n'est pas lu."""
    with db_migre.write() as conn:
        conn.execute("UPDATE batch SET remaining = 0 WHERE external_ref IS NOT NULL")
    for controle in check_migration(db_migre, grocy_reel_db, archive=False).checks:
        assert len(controle.details) <= 50
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_migration_check.py -q --timeout=60`
Expected: FAIL — `ModuleNotFoundError: …migration_check`

- [ ] **Step 3: Écrire `migration_check.py`, planchers en premier**

Le module s'écrit dans cet ordre, non négociable :

```python
# Le plancher AVANT la comparaison. Un contrôle qui compare 0 à 0 est rouge,
# jamais vert : le lot 6 a démontré qu'un vérificateur qui mesure du vide
# déclare tout conforme, et transforme une absence de donnée en preuve de
# succès. Chaque entrée de FLOORS rend True quand il y a de quoi mesurer.
FLOORS: dict[str, Callable[[Measures], bool]] = { ... }


def _verdict(code, grocy_count, home_count, gap, measures, acknowledged):
    if not FLOORS[code](measures):
        return "empty"                  # d'abord, toujours
    if code in _NEEDS_ACK and not _fully_acknowledged(code, acknowledged):
        return "unacknowledged"
    return "ok" if gap == 0 else "gap"
```

C0 est **évalué en premier** et, s'il est `empty` ou `gap`, le rapport le dit en tête de `blocking` : les dix autres contrôles sont exécutés quand même (on veut leur mesure) mais **`ok` reste faux**.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_migration_check.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

**La mutation la plus importante du lot :** supprimer l'appel à `FLOORS[code]` dans `_verdict` — les contrôles ne feront plus que comparer. Doivent tomber : `test_a_forgotten_copy_of_grocy_db_fails_before_anything_else`, `test_a_dry_run_left_in_simulation_is_red_not_green`, `test_a_check_that_compares_zero_to_zero_is_never_green`, `test_c6_fails_when_the_three_are_unknown`. **Si un seul de ces quatre reste vert, le plancher qu'il prétend couvrir n'existe pas.** Remettre.

Seconde mutation : accepter un acquittement partiel (`if acknowledged:` au lieu de la comparaison d'ensembles). `test_acknowledging_six_of_seven_is_not_acknowledging` doit tomber.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/migration_check.py custom_components/home_stock/const.py \
        tests/test_migration_check.py
git commit -m "feat: C0-C6, each with a floor that fails when it measured nothing"
```

---

## Task 14: Les contrôles C7 à C11 — piles, recettes, images, planning, résidus

**Files:**
- Modify: `custom_components/home_stock/migration_check.py`
- Test: `tests/test_migration_check.py` (bloc « C7-C11 »)

| # | Contrôle | Plancher | Bloquant |
|---|---|---|---|
| **C7** | **Piles et équipements** (lot 5). `battery` et `equipment` non vides, `summary_diff` vide | `battery` = 0 **ou** `equipment` = 0 | **Oui** — sans quoi le raccord ferme 14 tâches |
| **C8** | **Recettes.** 102 `recipe`, 510 `recipe_ingredient`, 561 `recipe_instruction`, 116 minuteurs ; **0 recette au `source_ref` négatif** | `recipe` = 0 | **Oui** sur les comptes ; **non** sur les 25 `unmatched`, qui sont **acquittées** |
| **C9** | **Images.** Chaque `image_url` sous `media/` **désigne un fichier qui existe et pèse > 0 octet** ; 117 fichiers attendus ; 0 URL `grocy.allanic.me` résiduelle | fichiers trouvés = 0 | **Oui** |
| **C10** | **Planning et liste.** 42 `meal` à venir, 23 recettes distinctes atteignables, 9 `shopping_list_item` ouverts ; 0 `meal` pointant une recette absente | `meal` = 0 | **Oui** |
| **C11** | **Résidus Grocy dans la maison.** Entités `grocy.*` encore lues ; `todo.grocy_batteries` encore cité par `maintenance.jinja` ou par `maintenance_sync_taches` | — | **Oui** tant que le raccord du lot 5 n'est pas appliqué |

**C7 est une dépendance d'ordre, pas une politesse.** Un import d'équipements non fait **avant** l'application du raccord ferait **disparaître** les tâches de pile au lieu de les déplacer — c'est écrit dans `docs/raccord/README.md`, étape 2, et c'est la seule dépendance du lot 5 vers le lot 7. Le lot 7 **vérifie**, il ne refait pas l'import.

**C9 sort de la base.** Un contrôle qui ne fait que relire des colonnes ne prouve **rien** sur des fichiers : les `image_url` peuvent être parfaitement cohérentes et pointer un dossier vide. C9 fait un `stat()` sur chaque fichier, et un fichier de **0 octet** est un échec — il passerait tous les contrôles de base et n'afficherait rien.

**C11 lit des fichiers de `config/` — en lecture seule, et par un chemin passé en paramètre.** Il ne les écrit jamais, ne les recharge jamais, et **n'applique jamais le raccord**. Quand le chemin n'existe pas (cas des tests, et de toute exécution hors de l'instance), C11 rend `empty` : il ne prétend pas que la maison est propre parce qu'il n'a pas su regarder.

- [ ] **Step 1: Écrire les tests**

```python
def test_c7_verifies_lot5_but_never_redoes_it(db_migre, grocy_reel_db):
    import inspect
    from custom_components.home_stock import migration_check as mc
    assert "import_grocy_equipment(" not in inspect.getsource(mc)


def test_c7_fails_when_batteries_are_empty(db_sans_piles, grocy_reel_db):
    """Sans cet import, le raccord du lot 5 FERME 14 tâches de pile au lieu
    de les déplacer. C'est la seule dépendance d'ordre du lot 5 vers le 7."""
    c7 = _check(check_migration(db_sans_piles, grocy_reel_db, archive=False), "C7")
    assert c7.verdict == "empty" and c7.blocking is True


def test_c7_wants_an_empty_summary_diff(db_migre, grocy_reel_db):
    c7 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C7")
    assert c7.verdict == "ok"
    assert c7.grocy_count == 26 and c7.home_count == 26


def test_c8_counts_all_four_numbers(db_migre, grocy_reel_db):
    c8 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C8")
    detail = " ".join(c8.details)
    assert "102" in detail and "510" in detail and "561" in detail and "116" in detail


def test_c8_catches_a_phantom_that_slipped_through(db_migre, grocy_reel_db):
    """Une copie fantôme a un source_ref NÉGATIF. Si une seule passe, le
    filtre type IN ('normal','1') a été relâché quelque part."""
    with db_migre.write() as conn:
        conn.execute("UPDATE recipe SET source_ref = '-42'"
                     " WHERE source_ref = '1'")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C8").blocking is True


def test_c8_lists_the_twenty_five_unmatched_without_blocking_on_counts(
        db_migre, grocy_reel_db):
    c8 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C8")
    assert c8.verdict == "unacknowledged"
    assert len([d for d in c8.details if "unmatched" in d or "sans quantité" in d]) == 25


def test_c8_passes_when_the_twenty_five_are_acknowledged(db_migre, grocy_reel_db):
    ids = _ids_unmatched(db_migre)
    assert len(ids) == 25
    c8 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                acknowledged=ids), "C8")
    assert c8.verdict == "ok"


def test_c9_stats_every_file(db_migre, grocy_reel_db, tmp_media):
    """Cas 3 du §16.3 : les images sont dans le mauvais dossier, les
    image_url sont écrites, la base est cohérente avec elle-même, tout est
    vert — jusqu'à ce que C9 aille stat() chaque fichier."""
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=tmp_media), "C9")
    assert c9.home_count == 117 and c9.verdict == "ok"


def test_c9_fails_when_the_folder_is_empty(db_migre, grocy_reel_db, tmp_path):
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=tmp_path), "C9")
    assert c9.verdict == "empty" and c9.blocking is True


def test_c9_refuses_a_zero_byte_file(db_migre, grocy_reel_db, tmp_media):
    """Un fichier de 0 octet passerait tous les contrôles de base et
    n'afficherait rien sur la tablette."""
    cible = next((tmp_media / "recipes").iterdir())
    cible.write_bytes(b"")
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=tmp_media), "C9")
    assert c9.blocking is True
    assert any(cible.name in d for d in c9.details)


def test_c9_finds_no_residual_grocy_url(db_migre, grocy_reel_db, tmp_media):
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=tmp_media), "C9")
    assert not [d for d in c9.details if "grocy.allanic.me" in d]


def test_c9_leaves_unsplash_alone(db_migre, grocy_reel_db, tmp_media):
    """46 images distinctes, 112 emplacements, laissées à leur source. Le
    critère est « est-ce que ça meurt avec le conteneur ? » — Unsplash n'en
    dépend pas, et C9 ne va JAMAIS les chercher sur le réseau."""
    c9 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                picture_dir=tmp_media), "C9")
    assert c9.verdict == "ok"


def test_c10_wants_forty_two_meals_and_nine_list_items(db_migre, grocy_reel_db):
    c10 = _check(check_migration(db_migre, grocy_reel_db, archive=False), "C10")
    detail = " ".join(c10.details)
    assert "42" in detail and "23" in detail and "9" in detail


def test_c10_catches_a_meal_pointing_at_a_missing_recipe(db_migre, grocy_reel_db):
    with db_migre.write() as conn:
        conn.execute("DELETE FROM recipe WHERE id ="
                     " (SELECT recipe_id FROM meal WHERE recipe_id IS NOT NULL LIMIT 1)")
    assert _check(check_migration(db_migre, grocy_reel_db, archive=False),
                  "C10").blocking is True


def test_c11_blocks_while_the_lot5_raccord_is_not_applied(db_migre, grocy_reel_db,
                                                          config_avec_raccord_absent):
    """Vérifié au 2026-08-21 : maintenance.jinja a encore ses 142 lignes et
    son bloc 3, et automations.yaml (l. 4304-4321) lit encore
    todo.grocy_batteries. Le poser est un PRÉALABLE à toute extinction — et
    ce plan ne le pose pas."""
    c11 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                 config_dir=config_avec_raccord_absent), "C11")
    assert c11.blocking is True
    assert any("maintenance.jinja" in d for d in c11.details)
    assert any("todo.grocy_batteries" in d for d in c11.details)


def test_c11_passes_once_the_raccord_is_in_place(db_migre, grocy_reel_db,
                                                 config_avec_raccord_pose):
    c11 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                 config_dir=config_avec_raccord_pose), "C11")
    assert c11.verdict == "ok"


def test_c11_is_empty_when_it_could_not_look(db_migre, grocy_reel_db, tmp_path):
    """Il ne prétend pas que la maison est propre parce qu'il n'a pas su
    regarder. C'est un plancher, comme les dix autres."""
    c11 = _check(check_migration(db_migre, grocy_reel_db, archive=False,
                                 config_dir=str(tmp_path / "nulle-part")), "C11")
    assert c11.verdict == "empty"


def test_c11_never_writes_anything(db_migre, grocy_reel_db, config_avec_raccord_absent):
    """LE test qui empêche le composant de « réparer » la maison tout seul."""
    avant = _empreinte_dossier(config_avec_raccord_absent)
    check_migration(db_migre, grocy_reel_db, archive=False,
                    config_dir=config_avec_raccord_absent)
    assert _empreinte_dossier(config_avec_raccord_absent) == avant


def test_nothing_in_the_module_stops_a_container(db_migre, grocy_reel_db):
    """Le composant n'arrête JAMAIS Grocy. Arrêter un conteneur de la maison
    est un geste humain, et rien de ce module ne doit pouvoir le faire."""
    import inspect
    from custom_components.home_stock import migration_check as mc
    source = inspect.getsource(mc)
    for interdit in ("docker", "subprocess", "os.system", "Popen"):
        assert interdit not in source


def test_all_eleven_pass_on_a_fully_migrated_database(db_migre, grocy_reel_db,
                                                      tmp_media,
                                                      config_avec_raccord_pose):
    """Le seul chemin vers ok: true — et il exige les deux acquittements."""
    rapport = check_migration(
        db_migre, grocy_reel_db, archive=False, picture_dir=tmp_media,
        config_dir=config_avec_raccord_pose,
        acknowledged=[*_sept_lots(), *_ids_unmatched(db_migre)])
    assert rapport.blocking == []
    assert rapport.ok is True
    assert len(rapport.checks) == 12
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_migration_check.py -q --timeout=60 -k C7 or C8 or C9 or C10 or C11`
Expected: FAIL.

- [ ] **Step 3: Écrire C7 à C11**

C11 lit `config_dir` en `pathlib`, ouvre `maintenance.jinja` et `automations.yaml` en **lecture**, cherche les motifs `todo.grocy_batteries`, `grocy_shopping_list`, `sensor.grocy_meal_plan`, `grocy-recipes.html` et le bloc 3 du `.jinja`. Aucune écriture, aucun `subprocess`, aucun `docker`.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_migration_check.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| C9 sans `stat()`, en ne lisant que les colonnes | `test_c9_fails_when_the_folder_is_empty`, `test_c9_refuses_a_zero_byte_file` |
| C11 rendant `ok` quand le dossier est absent | `test_c11_is_empty_when_it_could_not_look` |
| Ajouter `subprocess.run(["docker", "stop", "grocy"])` | `test_nothing_in_the_module_stops_a_container` — le supprimer **immédiatement** |

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/migration_check.py tests/test_migration_check.py
git commit -m "feat: C7-C11 — batteries, recipes, files on disk, plan, and what still reads Grocy"
```

---

## Task 15: L'archive de l'historique — 1 123 lignes en JSON, pas dans le journal

**Files:**
- Modify: `custom_components/home_stock/migration_check.py` (`_write_archive`)
- Test: `tests/test_migration_check.py` (bloc « archive »)

**Interfaces:**
- `_write_archive(grocy, destination, *, on) -> str` — rend le chemin écrit
- Nom : `home_stock_grocy_archive_<AAAA-MM-JJ>.json`, sous `config/`

**La décision, et les quatre raisons qui tuent l'idée inverse.** Les 1 123 lignes de `stock_log` **ne sont pas réinjectées** dans `movement` :

1. **Les valeurs sont fausses d'un facteur trente.** 387 sorties non annulées × calories du catalogue = **2 804 847 kcal sur 35 journées** ; médiane 867 kcal/jour, moyenne 80 138, maximum le 2026-08-17 à **2 556 904 kcal**. **6 journées sur 35** dans une fourchette plausible. Les mêmes défauts d'unité qu'au § 8.4 sont dans le journal : « 1 000 Pot » de sel consommés comptent mille pots — mais sur 387 lignes au lieu de 7, et sur des paquets qu'on ne peut plus aller regarder puisqu'ils sont mangés.
2. **La couverture est de 20 %.** 37 journées sur **187**. Un graphe montrerait 150 journées à zéro, et « zéro kcal » se lit « n'a rien mangé », pas « n'a rien saisi » — l'ambiguïté que le lot 2 a passé un lot entier à éviter avec `unvalued_movements`.
3. **L'heure est celle de la saisie, pas du repas.** 131 sorties à 10 h, 56 à 19 h, 55 à 20 h, 49 à 12 h. Une saisie en rafale à dix heures n'est pas un petit déjeuner de 131 aliments — et `used_date` est une date **sans heure**, quand la journée alimentaire du lot 2 court de 4 h à 4 h.
4. **Trois compteurs sauteraient d'un bloc.** `kcal_total`, `cost_total` et `cost_waste_total` lisent `totals_between(conn)` **sans bornes**. Injecter 353 sorties chiffrées les ferait monter de 2,8 millions de kcal en un rafraîchissement, et depuis le lot 4 ils sont `state_class: TOTAL` : Home Assistant enregistrerait honnêtement la marche d'escalier **pour toujours**. Le journal étant en ajout seul, la reprendre demanderait 353 contrepassations. Le coût ne serait même pas calculable : **188 des 353 sorties n'ont aucun prix**.

**Rien n'est jeté** — ce n'est simplement pas versé dans la comptabilité. **JSON et pas SQLite** : l'archive doit se lire dans dix ans, sur une machine qui n'aura plus le schéma de Grocy 4.6 en tête. Écrite **dans `config/`**, donc emportée par les sauvegardes natives de Home Assistant.

- [ ] **Step 1: Écrire les tests**

```python
def test_the_archive_holds_all_eleven_hundred_and_twenty_three_rows(db_migre,
                                                                    grocy_reel_db,
                                                                    tmp_path):
    chemin = check_migration(db_migre, grocy_reel_db, archive=True,
                             archive_dir=str(tmp_path)).archive_path
    contenu = json.loads(Path(chemin).read_text("utf-8"))
    assert len(contenu["stock_log"]) == 1123


def test_the_six_undone_rows_keep_their_flag(db_migre, grocy_reel_db, tmp_path):
    """Une annulation fait partie de l'histoire."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    assert len([l for l in contenu["stock_log"] if l["undone"]]) == 6


def test_each_row_carries_its_product_name(db_migre, grocy_reel_db, tmp_path):
    """Dans dix ans, un product_id de Grocy ne voudra plus rien dire."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    assert all(l.get("product_name") for l in contenu["stock_log"])


def test_the_archive_also_holds_the_notes_the_chores_and_the_past_plan(
        db_migre, grocy_reel_db, tmp_path):
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    assert len(contenu["batch_notes"]) == 25
    assert len(contenu["chores_log"]) == 39
    assert len(contenu["past_meal_plan"]) == 66


def test_the_six_chores_are_named_even_though_they_are_abandoned(db_migre,
                                                                 grocy_reel_db,
                                                                 tmp_path):
    """3,5 % de suivi sur six mois (39 pointages pour 6 tâches quotidiennes
    sur 187 jours). Abandonnées — mais leurs 39 pointages sont archivés, et
    le chemin de repli est dans docs/exploitation.md, pas dans le code."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    noms = {l["chore_name"] for l in contenu["chores_log"]}
    assert "Nettoyer la litière" in noms
    assert len(noms) == 6


def test_the_archive_is_json_not_sqlite(db_migre, grocy_reel_db, tmp_path):
    chemin = check_migration(db_migre, grocy_reel_db, archive=True,
                             archive_dir=str(tmp_path)).archive_path
    assert chemin.endswith(".json")
    assert Path(chemin).read_bytes()[:1] == b"{"


def test_the_file_name_carries_the_date(db_migre, grocy_reel_db, tmp_path):
    chemin = check_migration(db_migre, grocy_reel_db, archive=True,
                             archive_dir=str(tmp_path), now="2026-09-04T21:00:00"
                             ).archive_path
    assert Path(chemin).name == "home_stock_grocy_archive_2026-09-04.json"


def test_no_stock_log_row_ever_reaches_the_movement_table(db_migre, grocy_reel_db,
                                                          tmp_path):
    """LE test de la décision du §9. 353 sorties chiffrées feraient monter
    kcal_total de 2,8 millions en un rafraîchissement, et depuis le lot 4 ces
    compteurs sont state_class TOTAL : la marche d'escalier resterait dans
    les statistiques long terme POUR TOUJOURS."""
    avant = repo.totals_between(db_migre.read())
    check_migration(db_migre, grocy_reel_db, archive=True, archive_dir=str(tmp_path))
    assert repo.totals_between(db_migre.read()) == avant
    assert db_migre.read().execute(
        "SELECT COUNT(*) AS n FROM movement WHERE idempotency_key LIKE 'grocy:log:%'"
    ).fetchone()["n"] == 0


def test_no_archive_movement_table_was_created(db_migre):
    """Envisagée et refusée : elle serait écrite une fois et lue jamais.
    L'archive est un fichier."""
    tables = {row["name"] for row in db_migre.read().execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "archive_movement" not in tables


def test_archive_false_writes_no_file(db_migre, grocy_reel_db, tmp_path):
    rapport = check_migration(db_migre, grocy_reel_db, archive=False,
                              archive_dir=str(tmp_path))
    assert rapport.archive_path is None
    assert not list(tmp_path.iterdir())


def test_the_archive_is_readable_without_the_grocy_schema(db_migre, grocy_reel_db,
                                                          tmp_path):
    """Pas d'id nu, pas de code de statut : des noms, des dates, des
    quantités et des unités lisibles."""
    contenu = _archive(db_migre, grocy_reel_db, tmp_path)
    ligne = contenu["stock_log"][0]
    assert {"product_name", "amount", "unit", "used_date",
            "transaction_type", "undone"} <= set(ligne)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_migration_check.py -q --timeout=60 -k archive`
Expected: FAIL.

- [ ] **Step 3: Écrire `_write_archive`**

`json.dump(..., ensure_ascii=False, indent=1)`. Le chemin est **fourni** (`archive_dir`), jamais construit depuis un chemin absolu deviné.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_migration_check.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Insérer les 353 sorties comme mouvements `consumption` : `test_no_stock_log_row_ever_reaches_the_movement_table` doit tomber, **et** `test_the_three_totals_do_not_move` de la tâche 7 aussi. Deux tests dans deux fichiers : c'est la même décision, tenue à deux endroits.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/migration_check.py tests/test_migration_check.py
git commit -m "feat: archive the 1123 history rows as JSON, never into the journal"
```

---

## Task 16: Les trois services, et les validateurs qu'ils partagent

**Files:**
- Modify: `custom_components/home_stock/services.py`
- Modify: `custom_components/home_stock/services.yaml`
- Modify: `custom_components/home_stock/validators.py`
- Modify: `custom_components/home_stock/translations/fr.json`, `translations/en.json`
- Test: `tests/test_services_migration.py`, `tests/test_validators.py`

**Interfaces:**

| Service | Paramètres | Rend |
|---|---|---|
| `home_stock.import_grocy_stock` | `database_path` (défaut `grocy_import.db`), `apply` (défaut `false`) | lots, mouvements, `packaging`, lignes de courses, anomalies, `ok` |
| `home_stock.import_grocy_recipes` | `database_path`, `picture_dir` (défaut `media/home_stock`), `apply` | recettes, étapes, instructions, ingrédients, images écrites, repas, anomalies, `ok` |
| `home_stock.check_grocy_migration` | `database_path`, `archive` (défaut `true`), `acknowledged` (liste, défaut vide) | les onze contrôles, `blocking`, `ok` |

Tous **en simulation par défaut**, tous `SupportsResponse.ONLY`, tous journalisés — comme `import_grocy_catalog` depuis le lot 0 et `import_grocy_equipment` depuis le lot 5.

- Nouveaux validateurs, **une seule fois** dans `validators.py` : `grocy_database_path` (non vide, relatif, **pas de `..`**), `picture_dir` (sous `media/`, réutilise la logique de `media_path` déjà en place), `acknowledgement_list` (liste de chaînes bornées, **jamais `"all"`, jamais `"*"`**).
- Les chemins sont résolus par `hass.config.path()` : le composant ne lit **jamais** en dehors de `config/`. C'est ce qui rend la copie de `grocy.db` dans `config/` obligatoire — elle l'est déjà pour l'import du catalogue.

**Les deux imports n'ont PAS de jumeau websocket**, et c'est un choix inscrit, pas un oubli : même asymétrie que `import_grocy_catalog`, `import_grocy_equipment` et `resync_off`. Un import de masse se lance depuis Outils de développement, **une fois**, en lisant son rapport en entier. Le contrôle, lui, se relance vingt fois pendant la bascule, une main dans le placard et l'autre sur le téléphone : il lui faut le panneau (tâche 17).

- [ ] **Step 1: Écrire les tests**

```python
async def test_the_three_services_are_registered(hass, entree):
    for nom in ("import_grocy_stock", "import_grocy_recipes",
                "check_grocy_migration"):
        assert hass.services.has_service("home_stock", nom)


async def test_a_dry_run_is_the_default(hass, entree, grocy_dans_config):
    reponse = await hass.services.async_call(
        "home_stock", "import_grocy_stock", {}, blocking=True, return_response=True)
    assert reponse["batches"] == 107
    # Rien écrit : le défaut ne peut pas être destructeur.
    assert reponse["ok"] in (True, False)
    assert _batches(hass) == 0


async def test_apply_true_refreshes_the_coordinator(hass, entree, grocy_dans_config):
    await hass.services.async_call(
        "home_stock", "import_grocy_stock", {"apply": True},
        blocking=True, return_response=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_stock_stock_value") is not None


async def test_a_dry_run_does_not_refresh_the_coordinator(hass, entree,
                                                          grocy_dans_config):
    """Rafraîchir après une simulation ne ferait que gâcher une lecture —
    query_stock et export_journal ne le font pas non plus."""
    ...


@pytest.mark.parametrize("chemin", [
    "/etc/passwd", "../secrets.yaml", "../../grocy.db", "", "   ",
])
async def test_a_path_outside_config_is_refused(hass, entree, chemin):
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            "home_stock", "import_grocy_stock", {"database_path": chemin},
            blocking=True, return_response=True)


@pytest.mark.parametrize("dossier", [
    "www/home_stock", "/config/www", "../media", "config/home_stock",
])
async def test_a_picture_dir_outside_media_is_refused(hass, entree, dossier):
    """Le lot 5 a tranché : jamais sous www/, qui est servi SANS
    authentification à tout le réseau de la maison."""
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(
            "home_stock", "import_grocy_recipes", {"picture_dir": dossier},
            blocking=True, return_response=True)


async def test_acknowledging_everything_does_not_exist(hass, entree,
                                                       grocy_dans_config):
    """« Un bouton "tout va bien" finit toujours par être pressé sans
    regarder. » L'acquittement est NOMINATIF, et ces trois valeurs sont des
    tentatives de contournement, pas des identifiants."""
    for valeur in ("all", "*", ["all"], ["*"]):
        with pytest.raises((vol.Invalid, HomeAssistantError)):
            await hass.services.async_call(
                "home_stock", "check_grocy_migration", {"acknowledged": valeur},
                blocking=True, return_response=True)


async def test_the_check_returns_twelve_lines_and_a_verdict(hass, entree,
                                                            grocy_dans_config):
    reponse = await hass.services.async_call(
        "home_stock", "check_grocy_migration", {"archive": False},
        blocking=True, return_response=True)
    assert len(reponse["checks"]) == 12
    assert "blocking" in reponse and "ok" in reponse


async def test_services_yaml_describes_all_three(hass, entree):
    from homeassistant.helpers.service import async_get_all_descriptions
    d = await async_get_all_descriptions(hass)
    for nom in ("import_grocy_stock", "import_grocy_recipes",
                "check_grocy_migration"):
        assert d["home_stock"][nom]["description"]
        assert d["home_stock"][nom].get("response") is not None


async def test_no_service_can_stop_a_container(hass, entree):
    """Le composant n'arrête JAMAIS Grocy."""
    assert not hass.services.has_service("home_stock", "stop_grocy")
    assert not hass.services.has_service("home_stock", "shutdown_grocy")
```

Et dans `tests/test_validators.py` :

```python
def test_grocy_database_path_refuses_what_climbs():
    for mauvais in ("../x.db", "a/../../x.db", "/x.db", ""):
        with pytest.raises(vol.Invalid):
            validators.grocy_database_path(mauvais)
    assert validators.grocy_database_path("grocy_import.db") == "grocy_import.db"


def test_picture_dir_must_live_under_media():
    assert validators.picture_dir("media/home_stock") == "media/home_stock"
    for mauvais in ("www/x", "media/../www", "/media/x", "config/x"):
        with pytest.raises(vol.Invalid):
            validators.picture_dir(mauvais)


def test_acknowledgement_list_refuses_a_blanket():
    for mauvais in (["all"], ["*"], "all", [""], [" " * 5]):
        with pytest.raises(vol.Invalid):
            validators.acknowledgement_list(mauvais)
    assert validators.acknowledgement_list(["grocy:stock:419"]) == ["grocy:stock:419"]
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_services_migration.py tests/test_validators.py -q --timeout=60`
Expected: FAIL — services absents.

- [ ] **Step 3: Écrire les services et les validateurs**

Les trois handlers suivent **exactement** la forme d'`import_grocy_catalog` : `_run(hass, partial(...))`, `async_request_refresh()` **uniquement si `apply`**, retour du `as_dict()`. Les schémas voluptuous lisent les validateurs de `validators.py`, **jamais** `cv.string` nu sur un chemin.

Dans `services.yaml`, trois blocs en français, chacun disant en une phrase que le service **ne touche rien sans `apply: true`** et que **le contrôle n'arrête pas Grocy**.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_services_migration.py tests/test_validators.py -q --timeout=60`
Expected: PASS.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

| Mutation | Test qui doit tomber |
|---|---|
| `vol.Optional("apply", default=True)` | `test_a_dry_run_is_the_default` |
| `cv.string` sur `database_path` | `test_a_path_outside_config_is_refused` |
| Accepter `"all"` dans `acknowledged` | `test_acknowledging_everything_does_not_exist` |

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/services.py custom_components/home_stock/services.yaml \
        custom_components/home_stock/validators.py custom_components/home_stock/translations/ \
        tests/test_services_migration.py tests/test_validators.py
git commit -m "feat: three migration services, dry-run by default, paths validated once"
```

---

## Task 17: `home_stock/migration/check` — une commande, et la parité

**Files:**
- Modify: `custom_components/home_stock/websocket_api.py`
- Test: `tests/test_websocket_migration.py`, `tests/test_surface_parity.py`

**Interfaces:**
- `home_stock/migration/check` — mêmes paramètres, **même code**, **même réponse** que `home_stock.check_grocy_migration`.

**Aucune des deux surfaces n'a le droit d'être la plus faible.** Les deux lisent la **même** constante de schéma et appellent la **même** fonction. `test_surface_parity.py` gagne ses cas.

**Aucune entité nouvelle.** La bascule est un **événement**, pas un état. Un `binary_sensor.home_stock_migration_ok` resterait `on` pour toujours après le premier passage et n'apprendrait plus rien à personne. Le rapport est une réponse.

- [ ] **Step 1: Écrire les tests**

```python
async def test_the_command_answers_the_eleven_checks(hass, ws_client, grocy_dans_config):
    await ws_client.send_json({"id": 1, "type": "home_stock/migration/check",
                               "archive": False})
    reponse = await ws_client.receive_json()
    assert reponse["success"]
    assert len(reponse["result"]["checks"]) == 12


async def test_both_surfaces_return_the_very_same_object(hass, ws_client,
                                                         grocy_dans_config):
    """Même code, même réponse. Une divergence ici serait une porte dérobée
    dans la validation, et elle s'ouvre toujours du côté qu'on n'a pas testé."""
    await ws_client.send_json({"id": 1, "type": "home_stock/migration/check",
                               "archive": False})
    par_ws = (await ws_client.receive_json())["result"]
    par_service = await hass.services.async_call(
        "home_stock", "check_grocy_migration", {"archive": False},
        blocking=True, return_response=True)
    assert par_ws == par_service


async def test_the_two_imports_have_no_websocket_twin(hass, ws_client):
    """Choix inscrit, pas oubli : un import de masse se lance depuis Outils
    de développement, une fois, en lisant son rapport en entier."""
    for commande in ("home_stock/migration/import_stock",
                     "home_stock/migration/import_recipes"):
        await ws_client.send_json({"id": 9, "type": commande})
        assert not (await ws_client.receive_json())["success"]


async def test_no_new_entity_is_created(hass, entree):
    """La bascule est un événement, pas un état."""
    assert hass.states.get("binary_sensor.home_stock_migration_ok") is None
```

Et dans `tests/test_surface_parity.py`, ajouter à `CAS_LIMITES` :

```python
    ("home_stock/migration/check", "check_grocy_migration",
     {"database_path": "../secrets.yaml"}, "refusé"),
    ("home_stock/migration/check", "check_grocy_migration",
     {"database_path": "/etc/passwd"}, "refusé"),
    ("home_stock/migration/check", "check_grocy_migration",
     {"acknowledged": ["all"]}, "refusé"),
    ("home_stock/migration/check", "check_grocy_migration",
     {"acknowledged": "grocy:stock:419"}, "refusé"),   # une chaîne, pas une liste
    ("home_stock/migration/check", "check_grocy_migration",
     {"archive": False}, "accepté"),
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_websocket_migration.py tests/test_surface_parity.py -q --timeout=60`
Expected: FAIL.

- [ ] **Step 3: Écrire la commande**

Le schéma websocket réutilise les **mêmes** validateurs que le service, importés depuis `validators.py`. Ne pas retranscrire les bornes.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/ -q --timeout=60`
Expected: PASS, suite Python complète.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Retirer `acknowledgement_list` du **seul** schéma websocket : `test_both_surfaces_return_the_very_same_object` ne bouge pas, mais le cas `{"acknowledged": ["all"]}` de `test_surface_parity` doit tomber. C'est exactement l'asymétrie qu'on cherche — celle qui ne se voit pas dans le cas nominal.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/websocket_api.py tests/test_websocket_migration.py \
        tests/test_surface_parity.py
git commit -m "feat: home_stock/migration/check, as strict as its service twin"
```

---

## Task 18: Le bloc « Bascule » dans l'écran Réglages

**Files:**
- Modify: `frontend/src/ecrans/reglages.ts`
- Create: `frontend/tests/reglages-bascule.test.ts`

**Un bloc, pas un écran.** `reglages.ts` existe et appelle déjà un service (`home_stock.resync_off`) : il gagne un bloc **« Bascule »** — un bouton « Contrôler », les onze lignes avec leur écart, les bloquantes en rouge. **Rien d'autre : pas de bouton « Importer », pas de bouton « Éteindre Grocy ».** Le panneau **montre** l'état de la bascule ; il ne la conduit pas. Un écran « Bascule » à part entière est écarté pour toujours : un bloc suffit pour un événement qui n'arrive qu'une fois.

Contraintes de rendu inchangées : **412 px** de large, cibles ≥ **44 px**, contraste ≥ **5:1**, vérifiés par `node outils/verifier-rendu.mjs`.

- [ ] **Step 1: Écrire les tests**

Créer `frontend/tests/reglages-bascule.test.ts` :

```ts
describe('le bloc Bascule', () => {
  it('affiche les onze lignes de contrôle', async () => { /* 12 lignes, C0 à C11 */ });

  it('met en rouge une ligne bloquante et elle seule', async () => { /* … */ });

  it("affiche l'écart chiffré des deux côtés", async () => {
    // 108 chez Grocy, 107 chez nous, écart 1 : les trois nombres sont
    // visibles, parce qu'un « écart : 1 » sans ses deux termes ne dit pas
    // de quel côté il manque quelque chose.
  });

  it("dit qu'un contrôle n'a rien mesuré, au lieu d'afficher « écart : 0 »", async () => {
    // Le verdict "empty" ne se rend JAMAIS comme un succès. C'est la leçon
    // du lot 6, portée jusque dans le rendu.
  });

  it("n'offre aucun bouton d'import", async () => {
    // Un import de masse se lance depuis Outils de développement, une fois.
  });

  it("n'offre aucun bouton d'extinction", async () => {
    // Arrêter un conteneur de la maison est un geste humain. Le panneau ne
    // doit même pas suggérer que c'est un clic.
    expect(rendu.textContent).not.toMatch(/éteindre|arrêter|docker/i);
  });

  it("affiche « à acquitter » sans offrir d'acquitter en un geste", async () => {
    // L'acquittement est nominatif et passe par le service. Un bouton
    // « tout va bien » finit toujours par être pressé sans regarder.
  });

  it('ne casse pas la hauteur quand le rapport est absent', async () => { /* … */ });

  it('affiche un état d’attente pendant le contrôle', async () => { /* … */ });

  it('rend lisible une erreur de service en français', async () => { /* … */ });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test -- reglages-bascule`
Expected: FAIL.

- [ ] **Step 3: Écrire le bloc**

Dans `reglages.ts`, à la suite du bloc `resync_off`. Appel par `this.connexion.appeler('home_stock/migration/check', { archive: false })` — la **commande websocket**, pas le service : le panneau relance ce contrôle vingt fois pendant la bascule.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test`
Expected: PASS, **536 + 10 = 546** tests.

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Rendre un verdict `empty` avec la même couleur qu'un `ok` : `test « dit qu'un contrôle n'a rien mesuré »` doit tomber. Ajouter un bouton « Importer le stock » : deux tests doivent tomber.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/ecrans/reglages.ts frontend/tests/reglages-bascule.test.ts
git commit -m "feat: a Bascule block in Réglages — it shows the migration, it never drives it"
```

---

## Task 19: Le vérificateur de rendu — 70 exécutions deviennent 72

**Files:**
- Modify: `frontend/outils/verifier-rendu.mjs`
- Test: la sortie du vérificateur elle-même

**Interfaces:**
- Un scénario `reglages-bascule` de plus, joué **aux deux formats** (dense et étroit) → 70 exécutions passent à **72**.

Le scénario doit charger un rapport **avec au moins une ligne bloquante et une ligne `empty`** : un scénario où tout est vert ne mesure pas le rouge, et c'est précisément le piège du lot 6 rejoué au niveau du rendu.

- [ ] **Step 1: Écrire le scénario**

Ajouter au tableau des scénarios de `verifier-rendu.mjs` une entrée `reglages` avec un rapport de douze contrôles figé, dont `C0` en `empty`, `C4` en `unacknowledged` et `C1` en `gap`.

- [ ] **Step 2: Lancer le vérificateur**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs`
Expected: **72 exécutions**, toutes vertes. Débordement, cible < 44 px, contraste < 5:1 et texte tronqué sont des échecs — le rouge du bloquant doit passer le contraste **sur les deux thèmes**.

- [ ] **Step 3: Corriger ce que le vérificateur trouve**

Si le rouge ne passe pas le contraste, changer le **jeton**, pas le seuil. Le seuil est la contrainte ; la couleur est le réglage.

- [ ] **Step 4: Relancer les deux suites front**

```bash
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: 546 tests, 72 exécutions, tout vert. **Toujours pas de `npm run build`.**

- [ ] **Step 5: Commit**

```bash
git add frontend/outils/verifier-rendu.mjs
git commit -m "test: a render scenario for the Bascule block, red included"
```

---

## Task 20: La procédure d'extinction — livrée, jamais exécutée

**Files:**
- Create: `docs/extinction/README.md`
- Create: `docs/extinction/inventaire-grocy.md`
- Create: `docs/extinction/retour-arriere.md`
- Modify: `docs/exploitation.md`
- Modify: `docs/superpowers/specs/2026-08-21-home-stock-lot7-design.md` (§ 22 seulement, si un chiffre mesuré diffère)
- Test: `tests/test_extinction_docs.py`

> **Aucun geste de cette tâche n'est exécuté.** On **écrit** la procédure. On n'arrête pas Grocy, on ne copie pas `grocy.db` dans `config/`, on ne touche pas à `maintenance.jinja`, on ne modifie pas `automations.yaml`, on ne retire aucune route Pomerium, on ne commente aucune ligne de crontab. Le lot 5 a livré son raccord dans `docs/raccord/` et **ne l'a jamais appliqué** ; le lot 7 fait pareil, à plus grande échelle.

**Ce qui casse le jour de l'arrêt** — inventaire **cherché**, pas supposé (`grep -ril grocy` sur `config/` et `data/tools/` en lecture seule, plus le registre d'entités, la crontab root et la configuration du reverse proxy). Chacun doit apparaître dans la procédure, avec son geste :

| Quoi | Où | Geste |
|---|---|---|
| **`maintenance.jinja` bloc 3 + `maintenance_sync_taches`** lisant `todo.grocy_batteries` | `config/custom_templates/maintenance.jinja` (**142 lignes, bloc 3 toujours là**), `config/automations.yaml` **l. 4304-4321** | **Appliquer le raccord du lot 5**, `docs/raccord/README.md`, **dans son ordre** : piles d'abord, `.jinja` ensuite, automation en dernier. 88 lignes contre 142 |
| **`script.afficher_recette_cuisine`** → iframe `/local/grocy-recipes.html` | `config/scripts.yaml` l. 293-331 | La page reste servie mais **interroge l'API de Grocy** : elle affichera une erreur. Pointer la vue du panneau, ou supprimer |
| **`script.afficher_repas_prevu`** → `state_attr('sensor.grocy_meal_plan','meals')` | `config/scripts.yaml` l. 407-435 | L'attribut devient `None` : branche « pas de recette », **dégradation silencieuse**. `sensor.home_stock_next_meal` porte déjà `meal_id` |
| **`automation.grocy_rappel_liste_de_courses_au_depart`** | `config/automations.yaml` l. 3672-3699 | **Le pire des cas** : l'entité passe `unavailable`, `int(0)` la lit `0`, l'automation **ne se déclenche plus jamais, sans erreur**. Rebrancher sur `todo.home_stock_shopping` ou supprimer |
| **Les 55 images hébergées** par `grocy.allanic.me` | HTML des descriptions | Traité par les tâches 9 et 10. C'est la raison d'être du rapatriement |
| **Le cron root de 5 h 40**, `grocy-off/sync.sh` | crontab root | Échouera chaque nuit contre un port fermé, dans `/var/log/grocy-off.log`. **À commenter** |
| **Les 2 routes Pomerium** `grocy.allanic.me` → `127.0.0.1:9283` | `/opt/nivuus/Pomerium/config.yaml` | 502. À retirer, **après une sauvegarde datée** |
| **Les 21 entités** de la plateforme `grocy` (7 `binary_sensor`, 6 `sensor`, 6 `todo`, 1 `calendar`) | registre | `unavailable`. Supprimer l'**entrée de configuration**, puis désinstaller le dépôt HACS |

**Ce qui était déjà mort, et ne demande aucun geste** — à écrire aussi, sinon quelqu'un ira le « réparer » : `data/tools/wallpanel/rooms.py` (générateur périmé depuis le 2026-08-02, le modifier n'a **aucun effet**) ; `.storage/lovelace.wallpanel_cuisine` (16 références dans un dashboard périmé, gardé comme filet) ; `data/tools/wallpanel-app/src/` (**zéro** occurrence, deux tests le tiennent) ; les 8 sauvegardes `*.backup-*`.

- [ ] **Step 1: Écrire les tests des documents**

Créer `tests/test_extinction_docs.py` — des tests, parce qu'une procédure incomplète est un incident dans six semaines :

```python
"""La procédure d'extinction est un livrable, donc elle se teste.

Ces tests lisent des fichiers Markdown. Ils ne lancent rien, n'arrêtent rien
et ne touchent à aucun fichier de /opt/nivuus/HomeAssistant/config/.
"""
from pathlib import Path

PROCEDURE = Path("docs/extinction/README.md").read_text("utf-8")
INVENTAIRE = Path("docs/extinction/inventaire-grocy.md").read_text("utf-8")
RETOUR = Path("docs/extinction/retour-arriere.md").read_text("utf-8")


def test_the_procedure_is_a_numbered_list_of_eighteen_gestures():
    numeros = [l for l in PROCEDURE.splitlines() if l[:3].strip().rstrip(".").isdigit()]
    assert len(numeros) >= 18


def test_every_thing_that_breaks_has_its_gesture():
    """L'inventaire du §17.1, relu. Chacun doit apparaître dans la procédure,
    avec le geste correspondant — pas seulement dans le tableau."""
    for casse in ("maintenance.jinja", "todo.grocy_batteries",
                  "script.afficher_recette_cuisine", "script.afficher_repas_prevu",
                  "automation.grocy_rappel_liste_de_courses_au_depart",
                  "grocy-off/sync.sh", "Pomerium", "grocy-recipes.html"):
        assert casse in PROCEDURE, casse


def test_the_silent_one_is_flagged_as_silent():
    """L'automation de rappel de courses SE TAIRA SANS ERREUR : int(0) lit
    une entité unavailable comme 0. C'est le pire des cas, et il doit être
    écrit comme tel — une panne bruyante se voit, celle-ci non."""
    bloc = PROCEDURE[PROCEDURE.index("grocy_rappel_liste_de_courses"):][:600]
    assert "sans erreur" in bloc or "silencieu" in bloc


def test_the_raccord_is_named_as_a_prerequisite():
    """Le raccord du lot 5 n'est TOUJOURS PAS posé : maintenance.jinja a
    encore ses 142 lignes. Le poser est un préalable, pas une option."""
    assert "docs/raccord/README.md" in PROCEDURE
    assert "préalable" in PROCEDURE or "avant" in PROCEDURE


def test_the_freeze_comes_before_the_stock_import():
    assert PROCEDURE.index("Geler Grocy") < PROCEDURE.index("import_grocy_stock")


def test_the_catalogue_replay_comes_before_the_stock():
    """La cible bouge : le rejeu rattrape ce qui a été créé depuis, au moins
    le produit #350."""
    assert PROCEDURE.index("import_grocy_catalog") < PROCEDURE.index("import_grocy_stock")


def test_the_equipment_import_comes_before_the_raccord():
    """Seule dépendance d'ordre du lot 5 vers le lot 7 : sans l'import, le
    raccord FERME 14 tâches de pile au lieu de les déplacer."""
    assert PROCEDURE.index("import_grocy_equipment") < PROCEDURE.index("docs/raccord")


def test_nothing_is_stopped_before_the_check_is_green():
    assert PROCEDURE.index("check_grocy_migration") < PROCEDURE.index("docker compose stop")
    assert "tant que `ok` n'est pas `true`" in PROCEDURE


def test_the_proof_happens_while_grocy_is_still_running():
    """Ouvrir une recette, vérifier l'image, arrêter TEMPORAIREMENT, rouvrir,
    redémarrer. On n'éteint pas encore."""
    assert "docker start grocy" in PROCEDURE
    assert "temporairement" in PROCEDURE.lower()


def test_the_stop_is_never_a_down_minus_v():
    assert "docker compose stop" in PROCEDURE
    assert "down -v" not in PROCEDURE.replace("PAS `down -v`", "")
    assert "watchtower" in PROCEDURE.lower()      # sinon il le relance


def test_the_retention_periods_are_written():
    for duree in ("12 mois", "3 mois"):
        assert duree in RETOUR


def test_grocy_is_never_restarted_to_be_used_again():
    """Il est rallumé pour être LU. Le sens de la migration ne s'inverse
    jamais — décision du lot 0, « Écriture vers Grocy : jamais »."""
    assert "ne rien saisir" in RETOUR
    assert "127.0.0.1:9283" in RETOUR      # l'accès local, après le retrait Pomerium


def test_what_never_comes_back_is_said_before_not_after():
    assert "statistiques long terme" in RETOUR
    assert "ajout seul" in RETOUR


def test_the_dead_things_are_listed_so_nobody_repairs_them():
    for mort in ("wallpanel/rooms.py", "lovelace.wallpanel_cuisine",
                 "wallpanel-app"):
        assert mort in INVENTAIRE


def test_the_docs_never_ask_the_component_to_stop_anything():
    """Toutes les commandes docker de ces documents sont adressées au
    PROPRIÉTAIRE. Aucune n'est appelable par le composant."""
    for fichier in (PROCEDURE, INVENTAIRE, RETOUR):
        assert "hass.services" not in fichier or "docker" not in fichier


def test_exploitation_says_the_journal_starts_on_switchover_day():
    texte = Path("docs/exploitation.md").read_text("utf-8")
    assert "commence le jour de la bascule" in texte
    assert "local_todo" in texte        # le chemin de repli des 6 corvées
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_extinction_docs.py -q`
Expected: FAIL — `FileNotFoundError: docs/extinction/README.md`

- [ ] **Step 3: Écrire les trois documents**

`docs/extinction/README.md` — **18 gestes numérotés**, dans cet ordre exact, avec pour chacun ce qu'on vérifie avant de passer au suivant :

1. **Sauvegarder** — sauvegarde native HA complète, puis `grocy.db`, `storage/`, `config.php` datés dans le dossier personnel.
2. **Geler Grocy** — ne plus rien y saisir. Rappel : un produit y a été créé le 2026-08-21 à 18 h 54. Tant que quelqu'un range une course dans Grocy, **aucun contrôle d'égalité ne veut rien dire**.
3. **Copier la source dans `config/`** — le conteneur HA ne voit pas `/opt/nivuus/Grocy` : `grocy_import.db`, `media/home_stock/recipes/`, `media/home_stock/articles/`, moins `test.jpg` et les vignettes `__downscaledto64x64`.
4. **Déployer les lots 2 à 6** — la base de production est au schéma **2** ; `m003` → `m008` s'appliquent au redémarrage. Puis `repairs/list_issues` à **0**, et C0 doit voir `schema_version = 8`.
5. **Supprimer les statistiques des trois cumuls** — `kcal_total`, `cost_total`, `cost_waste_total`. Rendu obligatoire par le passage en `state_class: total` du lot 4. **Irréversible.**
6. **Rejouer l'import du catalogue** — `apply: false`, exiger `ok: true` et `anomalies: []`, puis `apply: true`. Rattrape au moins le produit #350.
7. **Importer piles et équipements** — `apply: false`, `summary_diff` **vide**, puis `apply: true`.
8. **Appliquer le raccord `maintenance.jinja`** — `docs/raccord/README.md`, **dans son ordre**, sans sauter une étape. C'est lui qui débranche `todo.grocy_batteries`.
9. **Importer le stock** — `apply: false`, lire **toutes** les anomalies, en particulier les 7 lots avec leurs notes. Puis `apply: true`.
10. **Importer recettes, images et planning** — `apply: false` puis `apply: true`.
11. **Contrôler** — `check_grocy_migration` ou le bloc « Bascule ». Acquitter **nominativement** les 7 lots et les 25 lignes. **Ne pas continuer tant que `ok` n'est pas `true`.**
12. **Preuve sur pièce, Grocy encore allumé** — ouvrir une recette sur la tablette cuisine, vérifier que l'image s'affiche, `docker stop grocy` **temporairement**, rouvrir. Si elle s'affiche encore, le rapatriement a tenu. `docker start grocy` ensuite — **on n'éteint pas encore**.
13. **Débrancher ce qui reste** — les deux scripts et l'automation silencieuse. `automation.reload`, `script.reload`, `repairs/list_issues` à 0.
14. **Commenter le cron de 5 h 40**.
15. **Arrêter Grocy, sans le supprimer** — `docker compose stop`, **PAS `down -v`**. Retirer le label Watchtower. **Ne pas supprimer `/opt/nivuus/Grocy/config/`** avant le délai de rétention.
16. **Retirer les deux routes Pomerium**, sauvegarde datée d'abord, puis recharger.
17. **Supprimer l'entrée de configuration `grocy`** (retire les 21 entités), puis désinstaller le dépôt HACS. `repairs/list_issues` à 0.
18. **Ranger** — supprimer `config/grocy_import.db` (un intrant, pas un fichier d'exploitation), retirer `grocy-scanner.html` et `grocy-recipes.html` de `config/www/`.

En tête du document : **« Compter une soirée, sans interruption. Les gestes 1 à 11 tiennent dans une même session, parce que le geste 2 gèle Grocy et que rien ne doit être rangé entre-temps. »**

`docs/extinction/inventaire-grocy.md` reprend les trois tableaux du § 17. `docs/extinction/retour-arriere.md` reprend le § 19 : rétentions (12 mois / 3 mois / toujours), les trois situations d'après-coup, et l'ordre **strict** de redémarrage — **Grocy en dernier des services, ses fichiers de configuration en dernier des fichiers**.

Dans `docs/exploitation.md` : la comptabilité kcal/€ **commence le jour de la bascule** (et pourquoi les graphes sont vides avant) ; les images sous `media/` ; les statistiques à supprimer une fois ; le chemin de repli des 6 corvées (`local_todo` + une automation quotidienne, **hors composant**).

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_extinction_docs.py -q`
Expected: PASS.

- [ ] **Step 5: Vérifier qu'aucun geste n'a été exécuté**

```bash
docker ps --format '{{.Names}}' | grep -c '^grocy$'      # attendu : 1, Grocy TOURNE TOUJOURS
wc -l /opt/nivuus/HomeAssistant/config/custom_templates/maintenance.jinja   # attendu : 142
grep -c 'grocy_batteries' /opt/nivuus/HomeAssistant/config/automations.yaml # attendu : > 0
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain              # rien hors du dépôt
ls /opt/nivuus/HomeAssistant/config/grocy_import.db 2>&1                   # attendu : absent
```

**Ces cinq vérifications sont la preuve que le lot a livré sans exécuter.** Si l'une échoue, quelque chose a été fait qui ne devait pas l'être : arrêter et le dire.

- [ ] **Step 6: Commit**

```bash
git add docs/extinction/ docs/exploitation.md docs/superpowers/specs/ tests/test_extinction_docs.py
git commit -m "docs: the shutdown procedure — eighteen gestures, none of them executed here"
```

---

## Task 21: Le bundle, les suites, et le décompte final

**Files:**
- Modify: `custom_components/home_stock/panel/home-stock-panel.js` (artefact de build)
- Modify: `docs/exploitation.md` (dernière relecture)

**C'est la SEULE tâche autorisée à lancer `npm run build`.** `custom_components/home_stock/` est bind-monté dans le conteneur Home Assistant : le bundle construit est servi tel quel, immédiatement. Une seule construction, à la toute fin, quand tout le reste est vert.

- [ ] **Step 1: Vérifier qu'un seul conteneur de test tourne**

```bash
docker ps --filter ancestor=home-stock-test
# Tuer les surnuméraires : plusieurs exécutions concurrentes se disputent le
# processeur et font passer une suite de 9 minutes à 50.
```

- [ ] **Step 2: Lancer la suite Python complète**

Run: `./scripts/test.sh -q`
Expected: PASS. Le total doit être **strictement supérieur à 1914** ; noter le nombre exact.

- [ ] **Step 3: Lancer les deux suites front, avant construction**

```bash
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: **546** tests, **72** exécutions.

- [ ] **Step 4: Construire le bundle**

Run (depuis `frontend/`) : `npm run build`

Puis vérifier ce qui a été écrit :

```bash
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain custom_components/home_stock/panel/
```
Un seul fichier doit avoir changé.

- [ ] **Step 5: Vérifier le bundle réellement en place**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs --deploye`
Expected: mêmes 72 exécutions vertes, cette fois sur le bundle construit.

- [ ] **Step 6: Vérifier une dernière fois que rien n'a été touché dehors**

```bash
docker ps --format '{{.Names}}' | grep -c '^grocy$'                         # 1
wc -l /opt/nivuus/HomeAssistant/config/custom_templates/maintenance.jinja   # 142
ls /opt/nivuus/HomeAssistant/config/media/home_stock 2>&1                   # absent
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain               # propre après commit
```

- [ ] **Step 7: Commit**

```bash
git add custom_components/home_stock/panel/home-stock-panel.js docs/exploitation.md
git commit -m "chore: build the panel bundle, and the lot 7 counts"
```

---

## Ce que ce plan ne fait pas

Rappel, pour qu'aucune tâche n'aille les chercher :

- **Éteindre Grocy.** **L'extinction elle-même ne fait pas partie de ce plan.** Le lot livre une procédure de dix-huit gestes numérotés dans `docs/extinction/README.md` ; aucune tâche n'en exécute un seul. Pas de `docker compose stop`, pas de retrait de route Pomerium, pas de ligne de crontab commentée, pas d'entrée de configuration supprimée. Arrêter un conteneur de la maison est un geste humain.
- **Appliquer le raccord `maintenance.jinja` du lot 5.** Il est livré dans `docs/raccord/` depuis le lot 5 et **toujours pas posé** : le `.jinja` a encore ses 142 lignes, `automations.yaml` lit encore `todo.grocy_batteries`. Le plan le **nomme comme préalable** (geste 8) et le **mesure** (contrôle C11). Il ne le pose pas.
- **Déployer les lots 2 à 6.** La base de production est au schéma **2** ; `m003` → `m008` s'appliqueront au prochain redémarrage de Home Assistant, que **personne ne déclenche ici**.
- **Copier `grocy.db` ou les 94 fichiers d'images dans `config/`.** Geste 3 de la procédure, fait par le propriétaire — le conteneur Home Assistant ne voit pas `/opt/nivuus/Grocy/config/data/storage/`.
- **Réinjecter l'historique** de `stock_log`. Jamais : faux d'un facteur trente, couvert à 20 %, sans heure de repas, et il ferait sauter trois compteurs `TOTAL` pour toujours. Archivé en JSON, pas versé dans la comptabilité.
- **Reprendre les prix historiques.** Même défaut d'unité. Ils se réapprennent en trois sessions de courses (lot 4) et par Open Prices (lot 1).
- **Analyser `variable_amount`** pour retrouver les 23 quantités. Vingt-cinq lignes à la main valent mieux qu'un analyseur à vie.
- **Rapatrier les 112 images Unsplash** (46 distinctes). Elles ne meurent pas avec le conteneur — même dette assumée que `strMealThumb` au lot 3. Et **aucun test ne va les chercher sur le réseau**.
- **Reprendre les 6 corvées.** 3,5 % de suivi mesuré sur six mois, hors modèle de `todo.maintenance` qui est conditionnel et non périodique. Le chemin de repli (`local_todo` + une automation quotidienne) est écrit dans `docs/exploitation.md`, **pas dans le composant**.
- **`recipes_nestings`** — 5 651 lignes, presque toutes générées par les triggers de `meal_plan`. Aucun usage réel constaté.
- **Une seconde minuterie par puce** (`recipe_timer`). 8 puces sur 553 ; le dédoublement ne perd rien, et une table changerait le contrat de la vue cuisine du lot 3.
- **Une vue HTTP d'images dans le composant** — le `http.py` du lot 0. **Abandonné pour de bon** : `media_source` de Home Assistant fait le travail, avec l'authentification en prime.
- **Un écran « Bascule » à part entière**, ou une entité `binary_sensor.home_stock_migration_ok`. La bascule est un événement qui n'arrive qu'une fois : un bloc dans Réglages et une réponse de service suffisent.
- **`batch.note`.** Les 25 notes sont dans le rapport d'import et dans l'archive. Une colonne que rien ne lit finit par être crue.
- **Écrire quoi que ce soit vers Grocy.** Décision du lot 0, jamais assouplie — y compris pendant un retour arrière, où Grocy est rallumé pour être **lu**, jamais pour être réutilisé.
