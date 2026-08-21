# home_stock — Lot 5 : équipements, piles et consommables — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `todo.maintenance` marche sans Grocy — mêmes tâches, mêmes seuils, et une bascule qui n'ouvre ni ne ferme rien. Puis trois choses que Grocy ne savait pas faire : savoir quel format de pile acheter et s'il en reste une au placard, cesser de deviner le verbe et les exclusions par des motifs sur un `entity_id`, et tenir les équipements du foyer (achat, garantie, notice, consommables) sur le catalogue existant plutôt que sur un modèle parallèle.

**Architecture:** Quatre tables (`battery`, `battery_event`, `equipment`, `equipment_consumable`) rattachées au catalogue du lot 0 sans y ajouter une seule colonne — une rechange est un `product` avec `edible = 0`, une pile installée est une *place* qui pointe vers ce produit. La règle qui crée ou ferme une tâche vit dans un module de domaine **pur** (`domain/maintenance.py`) : ni `hass`, ni registre, ni SQLite, donc testable sans démarrer Home Assistant et surtout sans la maison. Le coordinateur résout les ancres du registre d'entités et écrit `last_reading_at` **en base**, ce qui affranchit « muet depuis N heures » de l'uptime de Home Assistant. Le raccord avec `maintenance.jinja` est un **service à réponse**, `home_stock.maintenance_plan` : le macro perd son bloc « Piles », l'automation appelle le service, et un drapeau `peut_fermer` interdit toute fermeture quand le plan est incomplet.

**Tech Stack:** Python 3.13 / Home Assistant 2026.8.2 / SQLite (WAL, écrivain unique) / `pytest-homeassistant-custom-component` — TypeScript / `lit` / rollup / vitest / playwright-core.

**Spec:** `docs/superpowers/specs/2026-08-21-home-stock-lot5-design.md`

**Base de départ :** `master`, propre, **623 tests Python** (`./scripts/test.sh` depuis la racine) et **247 tests front** (`npm test` depuis `frontend/`) au vert. Toute tâche qui laisse un de ces deux chiffres en baisse est une tâche qui n'est pas finie.

---

## Global Constraints

Ces règles lient **toutes** les tâches. Elles sont recopiées de la spec et des lots 0 à 2.

- **Nommage.** Code, schéma et identifiants Python **en anglais** ; textes affichés **en français**. Les `entity_id` sont en anglais, les noms affichés vivent dans `translations/fr.json`. Le front garde ses identifiants, ses noms de fichiers et ses commentaires **en français**, comme aux lots 0 à 2.
- **Rien ne touche l'instance vivante.** Pas de `docker compose` (hors `scripts/test.sh`, qui construit une image de test et ne parle à aucun conteneur de la maison), pas de rechargement de l'intégration, pas de redémarrage, pas de lecture du jeton dans `.mcp.json`, **aucune écriture dans `/opt/nivuus/HomeAssistant/config/`**. Règle posée au lot 1 après un redémarrage non demandé du Home Assistant du foyer.
- **Le raccord se livre, il ne s'installe pas.** `maintenance.jinja` et l'automation `maintenance_sync_taches` vivent dans `config/`. Ce plan **écrit le diff attendu** dans `docs/raccord/`, le teste dans un Home Assistant de test, et **ne l'applique jamais**. L'application est le geste du propriétaire, à la main. Même discipline que le blueprint du lot 2. La **lecture** de `config/custom_templates/maintenance.jinja` et de `config/automations.yaml` est autorisée : elle sert à fabriquer les copies de référence, une fois.
- **Grocy est en lecture seule**, et uniquement sur une **copie** de `grocy.db` — jamais celle en production. Aucune écriture, jamais.
- **`npm run build` est interdit avant la dernière tâche.** `custom_components/home_stock/` est **bind-monté** dans le conteneur Home Assistant : le bundle construit est servi tel quel. Une seule construction, à la toute fin, quand tout le reste est vert. Un vérificateur ne déploie pas ; un build, si.
- **Commandes de test.** Python : `./scripts/test.sh` depuis la racine du dépôt (image Docker alignée sur HA 2026.8.2 — le Python de l'hôte ne peut pas charger le plugin). Front : `npm test` puis `node outils/verifier-rendu.mjs`, **depuis `frontend/`**.
- **Aucune des deux surfaces n'a le droit d'être la plus faible.** Ce que le websocket refuse, le service le refuse aussi, et réciproquement. Concrètement, et pour chaque contrainte : `kind` par `vol.In(BATTERY_KINDS)` ; `battery_event.kind` par `vol.In(BATTERY_EVENT_KINDS)` ; `low_percent`/`keep_percent` par `finite_float` puis `0 ≤ v ≤ 100` puis l'invariant `keep_percent >= low_percent` ; `cell_count` par `bounded_int` puis `≥ 1` ; `tracked` par un booléen strict ou `None` ; `exclusion_reason` par `bounded_text` **non vide quand `tracked = 0`** ; `purchased_on`/`installed_on`/`occurred_at` (partie date) par `iso_date` ; tous les identifiants par `bounded_int` ; tous les textes par `bounded_text`. La tâche 4 met ces règles dans **une** fonction que les deux surfaces appellent — c'est la seule façon de ne pas les faire diverger.
- **Jamais de fermeture sur un capteur indisponible.** État non numérique, entité disparue, ancre orpheline, pile jamais relevée → `keep` **sans** `items`. On ne ferme une tâche que sur une mesure qui prouve que la condition a disparu. C'est la règle de CLAUDE.md, et c'est l'invariant que la tâche 2 teste.
- **`items ⊆ keep`**, toujours, sur tous les cas. Sa violation est exactement le clignotement de tâche que CLAUDE.md décrit.
- **Les résumés sont identiques au caractère près.** La grammaire est `«{verbe} — {libellé}»`, sans exception, plus `«Pile HS ? — {libellé}»`. La réconciliation apparie sur `summary` : un caractère de différence ferme une tâche et en ouvre une autre, et Bleuenn l'annonce. Les descriptions, elles, ont le droit de s'enrichir : elles ne servent qu'au rafraîchissement.
- **`REASONS` ne change pas.** Un remplacement consomme une rechange avec le motif `consumption` existant. Aucun motif `battery` : la distinction se lit déjà dans `product.edible = 0`.
- **Aucune colonne n'est ajoutée à `product`, `article` ni `batch`.** C'est le critère qui prouve que la réutilisation du catalogue en est vraiment une.
- **`battery_event` est en ajout seul**, comme `movement` : deux déclencheurs SQLite refusent `UPDATE` et `DELETE`.
- **La garantie ne produit jamais de tâche**, et l'achat d'un équipement **n'écrit jamais de mouvement**. Une échéance se regarde, elle ne se coche pas ; une télévision à 900 € dans `cost_today` rendrait ce capteur inutilisable pour toujours, dans un journal non corrigible.
- **`warranty_ends_on` est calculé, jamais stocké.** Une date dérivée stockée finit par diverger de ses sources.
- **Aucun téléversement de fichier**, jamais, et **jamais rien sous `config/www/`** : tout ce qui s'y trouve est servi sur `/local/` sans authentification, et une notice porte un numéro de série.
- **Deux appuis pour toute action destructive du panneau** : armement puis confirmation. Aucun geste de navigation, aucun appui long. Toutes les écritures passent par la file hors-ligne du lot 1, et **toute** commande d'écriture accepte une `idempotency_key`.
- **Contraintes de rendu** : 412 × 915 et 1280 × 800, cibles ≥ **48 px**, contraste ≥ **4,5:1**, aucun débordement horizontal, aucun texte tronqué. Ce sont les seuils que `frontend/outils/verifier-rendu.mjs` applique déjà (`CIBLE_MIN_PX = 48`, `CONTRASTE_MIN = 4.5`). Ne jamais désactiver un contrôle pour faire passer un écran.
- **Jamais deux `db.write()` imbriqués.** `Database._lock` est un `threading.Lock` simple, non réentrant : imbriquer deux transactions **bloque le processus pour toujours**. Structurant pour la tâche 7 (un événement de pile + un mouvement, dans **une** transaction).

---

## Fusion avec le lot 3 — fichiers à fort risque de conflit

Les lots 3 et 5 sont implémentés **en parallèle, dans deux worktrees git séparés**, puis fusionnés dans `master`. Les fichiers ci-dessous seront touchés par les deux. La consigne est la même partout : **ajouter en fin de liste, ne jamais réordonner, ne jamais renuméroter ce que l'autre lot a posé.**

| Fichier | Consigne de fusion |
|---|---|
| `storage/migrations/__init__.py` | **La seule exception à « ne jamais renuméroter ».** Le lot 3 prend `m004` / `VERSION = 4` ; **le lot 5 prend `m005` / `VERSION = 5`** — et non `m006` comme la spec l'envisageait par prudence, le lot 4 n'existant pas encore. Au merge, **relire le fichier** et prendre le premier numéro libre : `apply_migrations()` n'applique que `VERSION > MAX(version)`, donc une base passée en version 5 sans avoir vu `m004` la sauterait **définitivement et silencieusement**. Le test de contiguïté (tâche 1) rend la règle exécutoire : **le lot qui fusionne en second renumérote sa migration** (module, `VERSION`, tests) jusqu'à ce que le test repasse. Ajouter le module en **fin** du tuple `MIGRATIONS`. |
| `tests/storage/test_migrations.py` | Le test de contiguïté est écrit par les **deux** lots (aucun ne peut supposer que l'autre a fusionné en premier). Au merge, **garder une seule copie** — elles sont identiques par construction : voir le texte exact en tâche 1. Le reste : ajouts **en fin de fichier**. |
| `const.py` | Constantes du lot **en fin de fichier**, dans un bloc commenté `# --- lot 5 : …`. Ne pas réordonner `REASONS` — le lot 5 n'y touche pas du tout, le lot 3 y ajoute `cooked` **après** `REASON_CONVERSION`. |
| `translations/fr.json` (et `en.json` s'il existe) | Ajouter les clés **à l'intérieur** de `entity.<plateforme>`, sans toucher aux clés existantes. Conflit textuel, résolu à la main en gardant **les deux** blocs. Le lot 3 ajoute une plateforme (`calendar`) que le lot 5 n'a pas ; le lot 5 n'ajoute que des clés `sensor`. |
| `services.yaml` | Blocs de service **en fin de fichier**. Aucun réordonnancement. |
| `services.py` | Handlers en closures **en fin** de `async_register_services`, `async_register` correspondants **en fin** du bloc d'enregistrement, schémas module-level **après** `RESYNC_SCHEMA`. |
| `websocket_api.py` | **Le lot 5 n'y ajoute que deux lignes** : un `from .websocket_batteries import async_register_battery_commands` et son appel en fin de `async_register_websocket`. Les onze commandes vivent dans un module neuf (décision en tête de la tâche 12), exactement comme le lot 3 fait pour `websocket_recipes`. Si les deux lots suivent cette règle, il n'y a plus de conflit que sur deux lignes voisines : garder **les deux**. |
| `sensor.py` | Nouvelles classes **en fin de fichier**, instances **en fin** de la liste passée à `async_add_entities`. |
| `binary_sensor.py` | **Le lot 5 ne le modifie pas.** Les rechanges remontent dans `shortages` parce que ce sont des produits sous leur `min_quantity` — la tâche 10 le **prouve par un test**, sans une ligne de code. Aucun `binary_sensor.home_stock_spares_missing` : ce serait la même donnée sous deux noms. |
| `todo.py` | **Le lot 5 ne le modifie pas.** `todo.home_stock_expirations` reste la liste des péremptions ; la maintenance passe par `todo.maintenance`, qui appartient à l'automation de la maison. |
| `coordinator.py` | Le lot 5 ajoute **deux** clés à `coordinator.data` (`"batteries"`, `"warranties"`) via un unique travail d'exécuteur. Ne pas réécrire `_async_update_data` : y insérer sa lecture en gardant celle de l'autre lot. |
| `application.py` | Nouvelles méthodes de `StockManager` **en fin de classe**. Le lot 5 ne refactore rien d'existant ; le lot 3 extrait `_consume_within` / `_add_stock_within` — au merge, la tâche 7 du lot 5 doit **réutiliser** ces helpers s'ils sont là, plutôt que de rouvrir une transaction. |
| `storage/repositories.py` | Nouvelles fonctions **en fin de fichier**, dans une section commentée `# --- lot 5 …`. Aucune modification de fonction existante. |
| `validators.py` | Nouveaux helpers **en fin de fichier**. Aucun helper existant modifié. |
| `messages.py` | Nouveaux couples (motif, phrase) **en fin** de `DOMAIN_ERROR_PATTERNS`. L'ordre compte (premier motif qui matche gagne) : n'insérer nulle part ailleurs. |
| `frontend/src/panneau.ts` | `Ecran` gagne ses valeurs **en fin d'union** ; les branches de `rendreEcran()` s'ajoutent **avant** le `return` du scanner ; les boutons de navigation **en fin** de barre ; les `import './ecrans/…'` **en fin** de la liste d'imports. |
| `frontend/outils/verifier-rendu.mjs` | Scénarios **en fin** du tableau `SCENARIOS`. |
| `tests/test_offline_queue_contract.py` | Ajouts **en fin** de l'ensemble `EXPECTED_QUEUED_COMMAND_TYPES`. |
| `docs/exploitation.md` | Une section `## Lot 5 — …` **à la fin du fichier**. Aucune retouche des sections précédentes. |

---

## Structure des fichiers

**Python — créés**

| Fichier | Responsabilité |
|---|---|
| `custom_components/home_stock/domain/maintenance.py` | `battery_plan()` et `merge_plan()`. **Pur** : pas de `hass`, pas de registre, pas de SQLite, pas d'horloge implicite (le « maintenant » est un argument). |
| `custom_components/home_stock/storage/migrations/m005_equipment.py` | Quatre tables, quatre index, deux déclencheurs d'ajout-seul. **Pas de hook `apply()`** : peupler demande le registre, donc `hass`, qu'une migration dans l'exécuteur n'a pas et ne doit pas avoir. |
| `custom_components/home_stock/websocket_batteries.py` | Les onze commandes du lot, dans leur propre module pour réduire la surface de conflit avec le lot 3. |
| `custom_components/home_stock/import_grocy_equipment.py` | Second import, indépendant de `import_grocy.py` : piles, rechanges, équipements, balayage du registre et rapport de contrôle. |
| `docs/raccord/maintenance.jinja` | **Copie de référence**, jamais installée : le macro sans son bloc 3. |
| `docs/raccord/maintenance_sync.yaml` | **Copie de référence**, jamais installée : l'automation avec `peut_fermer`. |
| `docs/raccord/README.md` | Ce que sont ces deux fichiers, et la procédure d'application à la main. |
| `tests/fixtures/maintenance/etats.json` | Instantané versionné des états (28 capteurs de pile, filtres, plantes, `update`), capturé **une fois** depuis `ha_sync/entities/sensor.json`. |
| `tests/fixtures/maintenance/avant.jinja` | Copie de l'**actuel** `maintenance.jinja`, pour prouver que la suppression du bloc 3 n'a rien emporté d'autre. |
| `tests/fixtures/maintenance/automation_avant.yaml` | Copie de l'**actuelle** automation `maintenance_sync_taches`, pour le test de regex dupliquée. |
| `tests/fixtures/grocy/equipment.sql` | Extrait anonymisé et versionné des tables `batteries` et `equipment` d'une **copie** de `grocy.db`. |

**Python — modifiés**

| Fichier | Ce qui change |
|---|---|
| `const.py` | `BATTERY_KINDS`, `BATTERY_EVENT_KINDS`, `BATTERY_VERBS`, `BATTERY_MUTE_HOURS`, `MUTE_SUMMARY_PREFIX`, `DEFAULT_LOW_PERCENT`, `DEFAULT_KEEP_PERCENT`, `CONSUMABLE_ROLES`, `CONSUMABLE_UNITS` |
| `validators.py` | `percent_threshold`, `cell_count`, `strict_bool_or_none`, `check_battery_fields` (l'invariant partagé par les deux surfaces) |
| `storage/migrations/__init__.py` | `m005` en fin du tuple `MIGRATIONS` |
| `storage/repositories.py` | Dépôts des quatre tables, écriture du dernier relevé, stock d'une rechange, échéances de garantie |
| `application.py` | `declare_battery`, `update_battery`, `list_batteries`, `record_reading`, `record_battery_event`, `maintenance_plan`, `create_equipment`, `update_equipment`, `list_equipment`, `get_equipment`, `link_consumable`, `unlink_consumable` |
| `coordinator.py` | Résolution des ancres du registre, relevés, `last_reading_at`, deux clés de plus dans `coordinator.data` |
| `sensor.py` | Trois capteurs : `batteries_low`, `batteries_undeclared`, `warranty_next` |
| `services.py`, `services.yaml` | `maintenance_plan` (réponse `ONLY`), `record_battery_event`, `import_grocy_equipment` (réponse `ONLY`) |
| `websocket_api.py` | Deux lignes : import et appel de `async_register_battery_commands` |
| `messages.py` | Les phrases françaises des refus du lot |
| `translations/fr.json` | Noms français des trois capteurs |
| `docs/exploitation.md` | Section « Lot 5 » : procédure d'import, application du raccord à la main, ce qu'il faut regarder après |

**Front — créés**

| Fichier | Responsabilité |
|---|---|
| `frontend/src/ecrans/piles.ts` | L'écran « Piles » : suivies, à déclarer, fiche, événements. |
| `frontend/src/ecrans/equipements.ts` | L'écran « Équipements » : liste par emplacement, fiche, garantie, notice, consommables. |
| `frontend/tests/piles.test.ts` · `frontend/tests/equipements.test.ts` | Leurs tests. |

**Front — modifiés**

| Fichier | Ce qui change |
|---|---|
| `frontend/src/panneau.ts` | Deux valeurs de plus dans `Ecran`, deux branches, deux boutons de navigation |
| `frontend/outils/verifier-rendu.mjs` | Deux scénarios de plus |

**Documents de raccord (`docs/raccord/`)**

| Fichier | Ce qu'il est, ce qu'il n'est pas |
|---|---|
| `maintenance.jinja` | **Est** la copie exacte de ce que le propriétaire devra poser dans `config/custom_templates/`. **N'est pas** installé, ni par le composant, ni par un test, ni par une tâche de ce plan. Les tests le montent dans `hass.config.path('custom_templates/')` d'un Home Assistant **de test**, dans un répertoire temporaire. |
| `maintenance_sync.yaml` | **Est** le bloc YAML de l'automation `maintenance_sync_taches`, avec `peut_fermer`. **N'est pas** collé dans `config/automations.yaml`. |
| `README.md` | La procédure à la main, dans l'ordre : sauvegarder, poser le `.jinja`, `homeassistant.reload_custom_templates`, vérifier le rendu dans Outils de développement, remplacer le bloc d'automation, recharger, contrôler que `todo.maintenance` n'a ni gagné ni perdu de tâche. |

---

## Task 1: Migration `m005`, contiguïté des `VERSION`, et les constantes du lot

**Files:**
- Create: `custom_components/home_stock/storage/migrations/m005_equipment.py`
- Modify: `custom_components/home_stock/storage/migrations/__init__.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/storage/test_migrations.py`

**Interfaces:**
- Consomme : `apply_migrations(conn)` et son lecteur de `MAX(version)`, en place depuis le lot 0.
- Produit :
  - `m005_equipment.VERSION = 5`, `m005_equipment.SQL`. **Aucun `apply(conn)`** : le remplissage vient du service d'import (tâche 13), parce que peupler 14 lignes demande le registre d'entités, donc `hass`, qu'une migration tournant dans l'exécuteur sur une connexion SQLite n'a pas — et ne doit pas avoir.
  - Quatre tables : `battery`, `battery_event`, `equipment`, `equipment_consumable`, exactement comme le DDL de la spec § 6.2.
  - Quatre index : `idx_battery_tracked`, `idx_battery_anchor` (UNIQUE partiel sur `entity_registry_id IS NOT NULL`), `idx_battery_event_battery`, `idx_equipment_consumable`.
  - Deux déclencheurs : `battery_event_no_update`, `battery_event_no_delete`.
  - Dans `const.py`, **en fin de fichier** :

```python
# --- lot 5 : équipements, piles et consommables -----------------------------
BATTERY_KINDS: Final = ("primary", "rechargeable_cell", "built_in")
BATTERY_EVENT_KINDS: Final = ("install", "charge", "replacement", "removal")

# Le verbe affiché, par nature. C'est la SEULE source de la grammaire des
# résumés : `«{verbe} — {libellé}»`. Un caractère de plus ici ferme toutes les
# tâches ouvertes de cette nature et en rouvre autant, avec l'annonce vocale
# qui va avec.
BATTERY_VERBS: Final = {
    "primary": "Pile à changer",
    "rechargeable_cell": "Piles à recharger",
    "built_in": "Recharger",
}
MUTE_SUMMARY_PREFIX: Final = "Pile HS ? — "

# Zigbee2MQTT ne publie `offline` pour un appareil sur pile qu'après 25 h de
# silence (passive.timeout par défaut). En dessous, un capteur muet est un
# capteur qui n'a rien eu à dire. Ce seuil n'est plus contraint par l'uptime
# de Home Assistant depuis que `battery.last_reading_at` vit en base : le
# macro devait se contenter d'1 h parce que `last_changed` repartait à chaque
# démarrage — et un seuil de 12 h avait laissé la porte d'entrée muette 9
# jours (2026-08-07 → 08-16) sans jamais créer de tâche.
BATTERY_MUTE_HOURS: Final = 26

# Les seuils d'AUJOURD'HUI, repris tels quels pour que la bascule ne déplace
# aucune tâche. Ils deviennent réglables par pile, ils ne changent pas de
# valeur par défaut.
DEFAULT_LOW_PERCENT: Final = 20.0
DEFAULT_KEEP_PERCENT: Final = 25.0

CONSUMABLE_ROLES: Final = ("filter", "bag", "brush", "cartridge", "other")
CONSUMABLE_UNITS: Final = ("percent", "minutes")
```

**Décision de plan — le numéro est `5`, et la contiguïté est un test.** La spec § 6.1 réservait `m005` au lot 4 et prenait `m006` par prudence. Le lot 4 n'est pas écrit ; laisser un trou serait sans conséquence pour `apply_migrations()` mais **un dépassement est fatal et silencieux** : une base passée en 6 ne verrait jamais `m004` ni `m005`. Le lot 5 prend donc **le premier numéro libre après le lot 3**, soit `5`, et le test ci-dessous transforme la règle en quelque chose que la suite fait respecter au lieu d'une chose dont il faut se souvenir. Le lot 3 écrit le même test dans sa propre tâche 1 : au merge, **garder une seule copie**.

- [x] **Step 1: Écrire les tests de la migration et de la contiguïté**

Dans `tests/storage/test_migrations.py`, **en fin de fichier**. Lire d'abord le haut du fichier et **reprendre les helpers déjà présents** (`_migrated(tmp_path)`, `_migrated_to(tmp_path, version=…)`, `_open(tmp_path)`) plutôt que d'en écrire d'autres.

**Relâché le temps des deux worktrees.** Le lot 3 (`m004_recipes`) s'implémente en parallèle
dans un autre worktree ; tant que les deux n'ont pas fusionné, `MIGRATIONS` a un trou en 4 et la
forme stricte ci-dessous (`versions == list(range(1, len(versions) + 1))`) échouerait pour
toujours dans ce worktree. Le test est donc écrit sous une forme relâchée — unicité, croissance
stricte, première VERSION à 1, `CURRENT_VERSION` égal à la dernière — qui redevient la forme
stricte au merge du lot 3, quand `m004_recipes` comble le trou.

```python
def test_migration_versions_are_contiguous_from_one():
    """Un trou dans les VERSION est sans conséquence ; un DÉPASSEMENT est
    fatal et muet. `apply_migrations()` n'applique que les migrations dont la
    VERSION dépasse MAX(version) : une base passée en 5 sans avoir vu m004 ne
    la verrait plus jamais, et l'intégration démarrerait sur un schéma amputé,
    sans une ligne de log. Ce test est ce qui oblige le lot qui fusionne en
    second à renuméroter sa migration."""
    versions = [m.VERSION for m in MIGRATIONS]
    assert len(set(versions)) == len(versions)
    assert versions == sorted(versions)
    assert versions[0] == 1
    assert CURRENT_VERSION == versions[-1]
    # À RESSERRER AU MERGE DU LOT 3 : une fois `m004_recipes` inséré dans
    # MIGRATIONS, remplacer les quatre assertions ci-dessus par la forme
    # stricte, qui est celle que ce test doit avoir en fin de compte :
    #     assert versions == list(range(1, len(versions) + 1))
    # Le trou 4 n'existe que le temps où les lots 3 et 5 vivent dans deux
    # worktrees séparés. `apply_migrations()` n'applique que les migrations
    # dont la VERSION dépasse MAX(version) : une base passée en 5 sans avoir
    # vu m004 ne la verrait PLUS JAMAIS, sans une ligne de log.


def test_migration_modules_are_named_after_their_version():
    """m003_consumption.VERSION == 3. Un module renuméroté à moitié (VERSION
    changée, fichier non renommé) est exactement le genre d'erreur que le
    merge des lots 3 et 5 peut produire."""
    for module in MIGRATIONS:
        assert module.__name__.rsplit(".", 1)[-1].startswith(f"m{module.VERSION:03d}_")


def test_m005_creates_the_four_tables(tmp_path):
    conn = _migrated(tmp_path)
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"battery", "battery_event", "equipment", "equipment_consumable"} <= tables
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(battery)")}
    assert {"entity_registry_id", "device_id", "kind", "product_id", "cell_count",
            "tracked", "exclusion_reason", "low_percent", "keep_percent",
            "last_percent", "last_reading_at", "external_ref"} <= columns


def test_m005_adds_no_column_to_the_catalogue(tmp_path):
    """Le critère qui prouve que la réutilisation du catalogue en est une : si
    une pile avait eu besoin d'une colonne dans `product`, c'est que ce n'était
    pas un produit."""
    before = _migrated_to(tmp_path / "avant", version=4)
    after = _migrated(tmp_path / "apres")
    for table in ("product", "article", "batch"):
        assert ({r["name"] for r in before.execute(f"PRAGMA table_info({table})")}
                == {r["name"] for r in after.execute(f"PRAGMA table_info({table})")})


def test_m005_battery_event_is_append_only(tmp_path):
    conn = _migrated(tmp_path)
    _seed_one_battery_event(conn)                 # helper à ajouter, voir Step 3
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE battery_event SET note = 'x' WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM battery_event WHERE id = 1")


def test_m005_refuses_an_unknown_kind(tmp_path):
    conn = _migrated(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO battery (label, kind) VALUES ('X', 'nimh')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO battery (label, kind, cell_count) "
                     "VALUES ('X', 'primary', 0)")


def test_m005_refuses_two_batteries_on_the_same_anchor(tmp_path):
    """L'ancre est unique — mais seulement quand elle existe : deux piles sans
    ancre (une poêle à pile, une pile déclarée avant d'être branchée) doivent
    coexister. C'est ce que l'index UNIQUE PARTIEL achète."""
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO battery (label, kind, entity_registry_id) "
                 "VALUES ('A', 'primary', 'abc')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO battery (label, kind, entity_registry_id) "
                     "VALUES ('B', 'primary', 'abc')")
    conn.execute("INSERT INTO battery (label, kind) VALUES ('C', 'primary')")
    conn.execute("INSERT INTO battery (label, kind) VALUES ('D', 'primary')")


def test_m005_refuses_two_identical_consumable_links(tmp_path):
    conn = _migrated(tmp_path)
    _seed_equipment_and_product(conn)             # helper à ajouter, voir Step 3
    conn.execute("INSERT INTO equipment_consumable (equipment_id, product_id, role) "
                 "VALUES (1, 1, 'filter')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO equipment_consumable (equipment_id, product_id, role) "
                     "VALUES (1, 1, 'filter')")


def test_m005_is_replayable(tmp_path):
    """Rejouer `apply_migrations` sur une base déjà en version 5 ne doit rien
    changer et rien lever."""
    conn = _migrated(tmp_path)
    assert apply_migrations(conn) == 5
    assert apply_migrations(conn) == 5


def test_m005_applies_on_a_copy_of_the_lot2_database(tmp_path):
    """Pas sur une base vide : sur une base qui a déjà des produits, des lots
    et des mouvements — c'est celle-là qui existe dans la maison."""
    conn = _migrated_to(tmp_path, version=4)
    _seed_one_movement(conn)                      # helper déjà présent dans ce fichier
    assert apply_migrations(conn) == 5
    assert conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"] == 1
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q`
Expected: FAIL — `ModuleNotFoundError` / `AssertionError` sur la contiguïté, `sqlite3.OperationalError: no such table: battery`.

- [x] **Step 3: Écrire `m005_equipment.py`, les helpers de test et l'inscription**

`m005_equipment.py` reprend **littéralement** le DDL de la spec § 6.2, commentaires compris (ils disent pourquoi `battery` est une place et non une cellule — c'est l'idée que tout le lot repose dessus). Puis `storage/migrations/__init__.py` :

```python
from . import m001_initial, m002_scan, m003_consumption, m005_equipment

MIGRATIONS = (m001_initial, m002_scan, m003_consumption, m005_equipment)
```

> Au merge avec le lot 3, `m004_recipes` s'insère **avant** `m005_equipment` dans le tuple, et le test de contiguïté est ce qui le dit.

Ajouter dans le fichier de test les deux helpers `_seed_one_battery_event(conn)` et `_seed_equipment_and_product(conn)`, sur le modèle de `_seed_one_movement` déjà présent.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q`
Expected: PASS

- [x] **Step 5: La suite entière**

Run: `./scripts/test.sh -q`
Expected: PASS, ≥ 623 tests.

---

## Task 2: `domain/maintenance.py` — le plan des piles, pur

**Files:**
- Create: `custom_components/home_stock/domain/maintenance.py`
- Test: `tests/domain/test_maintenance.py`

**Interfaces:**
- Consomme : `const.BATTERY_VERBS`, `const.BATTERY_MUTE_HOURS`, `const.MUTE_SUMMARY_PREFIX`.
- Produit :
  - `summary_for(kind: str, label: str) -> str` — `f"{BATTERY_VERBS[kind]} — {label}"`.
  - `mute_summary_for(label: str) -> str`
  - `battery_plan(batteries: Sequence[Mapping[str, Any]], *, now: datetime, mute_hours: int = BATTERY_MUTE_HOURS) -> dict[str, list]` — rend `{"items": [...], "keep": [...]}`, chaque item portant `summary`, `description` et `entity`.
  - `PlanItem = TypedDict("PlanItem", {"summary": str, "description": str, "entity": str | None})`

**Ce que ce module reçoit.** Un dictionnaire par pile, tel que la tâche 5 le fabriquera depuis SQLite + le registre. Ce module ne va jamais le chercher :

```python
{
  "id": 7, "label": "Velux (CH)", "kind": "primary", "tracked": True,
  "entity_id": "sensor.velux_ch_batterie" | None,   # résolu par le coordinateur
  "state": "18" | "unavailable" | None,             # None = ancre orpheline
  "last_percent": 18.0 | None,
  "last_reading_at": "2026-08-21T06:00:00" | None,  # UTC naïf, comme partout
  "spare": {"label": "CR2032", "cell_count": 1, "in_stock": 0.0} | None,
}
```

**Pourquoi ce module est pur.** Même discipline que `domain/foodday.py` au lot 2, et pour la même raison : la règle qui décide de créer ou de fermer une tâche dans la vraie maison doit se tester sans démarrer Home Assistant, et surtout sans la maison. `now` est un argument, jamais `datetime.now()`.

**Décisions de plan, à graver dans le module :**

1. **`tracked` à `None` ou `False` → la pile n'apparaît nulle part**, ni dans `items`, ni dans `keep`. Elle est **silencieuse** dans `todo.maintenance` ; sa visibilité vient de `sensor.home_stock_batteries_undeclared` et du panneau. La règle « rien n'échoue silencieusement » est tenue par le compteur, pas par la liste.
2. **La description d'un item de niveau est `f"{int(percent)} %"`** — pas `f"{percent} %"`. Le macro rend `s.state | int(-1)`, donc un entier ; une pile à 19,6 % écrivait « 19 % ». Écrire « 19.6 % » ne fermerait aucune tâche (la description ne sert qu'au rafraîchissement) mais rafraîchirait les 14 tâches le jour de la bascule pour rien.
3. **Le seuil se compare sur le réel, la description s'affiche en entier.** `19.6 < 20` est vrai, et `int(19.6) | int` du macro l'est aussi : les deux surfaces produisent le même ensemble d'items. C'est vérifié par le test de neutralité de la tâche 14.
4. **`last_reading_at` absent ⇒ aucune conclusion.** Une pile jamais relevée (déclaration fraîche) ne produit **ni** item de niveau **ni** « Pile HS ? ». Elle alimente `keep`, et rien d'autre.

- [x] **Step 1: Écrire les tests**

Créer `tests/domain/test_maintenance.py` :

```python
"""La règle qui crée et ferme les tâches de pile, testée sans Home Assistant.

Deux invariants dominent tout le fichier :
  - `items ⊆ keep` : sa violation est le clignotement de tâche que CLAUDE.md
    décrit — la tâche apparaît, la synchro suivante la ferme, la suivante la
    rouvre, et Bleuenn l'annonce à chaque fois.
  - jamais de fermeture sur un capteur indisponible : tout ce qui n'est pas une
    mesure numérique fraîche produit `keep` SANS `items`.
"""
from datetime import datetime, timedelta

import pytest

from custom_components.home_stock.const import BATTERY_MUTE_HOURS
from custom_components.home_stock.domain.maintenance import (
    battery_plan, mute_summary_for, summary_for,
)

NOW = datetime(2026, 8, 21, 12, 0, 0)


def _pile(**kw):
    base = {"id": 1, "label": "Velux (CH)", "kind": "primary", "tracked": True,
            "entity_id": "sensor.velux_ch_batterie", "state": "18",
            "last_percent": 18.0, "last_reading_at": "2026-08-21T11:00:00",
            "low_percent": 20.0, "keep_percent": 25.0, "spare": None}
    return {**base, **kw}


def _resumes(plan):
    return [i["summary"] for i in plan["items"]]


def test_the_three_kinds_give_the_three_verbs():
    assert summary_for("primary", "Velux (CH)") == "Pile à changer — Velux (CH)"
    assert summary_for("rechargeable_cell", "Capteur") == "Piles à recharger — Capteur"
    assert summary_for("built_in", "Rideau") == "Recharger — Rideau"
    assert mute_summary_for("Velux (CH)") == "Pile HS ? — Velux (CH)"


def test_a_battery_under_its_threshold_becomes_an_item():
    plan = battery_plan([_pile()], now=NOW)
    assert _resumes(plan) == ["Pile à changer — Velux (CH)"]
    assert plan["items"][0]["description"] == "18 %"
    assert plan["items"][0]["entity"] == "sensor.velux_ch_batterie"


def test_the_description_is_a_whole_percent_like_the_macro_renders_it():
    """Le macro rend `s.state | int(-1)`. Écrire « 19.6 % » rafraîchirait les
    14 tâches le jour de la bascule sans qu'aucune valeur n'ait bougé."""
    plan = battery_plan([_pile(state="19.6", last_percent=19.6)], now=NOW)
    assert plan["items"][0]["description"] == "19 %"


def test_hysteresis_between_the_two_thresholds():
    # 22 % : au-dessus du seuil d'apparition, sous celui de maintien.
    plan = battery_plan([_pile(state="22", last_percent=22.0)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — Velux (CH)"]
    # 26 % : la tâche a le droit de se fermer.
    plan = battery_plan([_pile(state="26", last_percent=26.0)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == []


def test_the_thresholds_are_per_battery():
    """Une CR2032 annonce 100 % jusqu'à mourir en trois jours ; une AAA descend
    lentement. C'est le cas concret qui justifie des seuils déclarables."""
    plan = battery_plan([_pile(state="45", last_percent=45.0,
                               low_percent=50.0, keep_percent=60.0)], now=NOW)
    assert _resumes(plan) == ["Pile à changer — Velux (CH)"]


def test_a_mute_sensor_protects_both_summaries():
    """Une pile faible qui se tait ne prouve pas qu'elle a été changée : on
    garde « Pile HS ? — X » ET « Pile à changer — X »."""
    vieux = (NOW - timedelta(hours=BATTERY_MUTE_HOURS + 1)).isoformat()
    plan = battery_plan([_pile(state="unavailable", last_reading_at=vieux)], now=NOW)
    assert _resumes(plan) == ["Pile HS ? — Velux (CH)"]
    assert set(plan["keep"]) == {"Pile HS ? — Velux (CH)", "Pile à changer — Velux (CH)"}
    assert "27 h" in plan["items"][0]["description"]


def test_a_sensor_mute_for_less_than_the_threshold_creates_nothing():
    """25 h de silence, c'est un appareil sur pile qui n'a rien eu à dire :
    Z2M ne le déclare `offline` qu'après 25 h. Aucun item — mais keep, parce
    qu'on ne ferme rien sur un capteur muet."""
    recent = (NOW - timedelta(hours=BATTERY_MUTE_HOURS - 1)).isoformat()
    plan = battery_plan([_pile(state="unavailable", last_reading_at=recent)], now=NOW)
    assert plan["items"] == []
    assert set(plan["keep"]) == {"Pile HS ? — Velux (CH)", "Pile à changer — Velux (CH)"}


def test_a_never_read_battery_produces_no_item_at_all():
    """Déclaration fraîche : `last_reading_at` est NULL. Ni item de niveau, ni
    « Pile HS ? » — on ne sait rien, donc on n'affirme rien. keep seulement."""
    plan = battery_plan([_pile(state=None, last_percent=None,
                               last_reading_at=None)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — Velux (CH)"]


def test_a_non_numeric_state_keeps_without_creating():
    for state in ("unknown", "", "faible", "NaN"):
        plan = battery_plan([_pile(state=state, last_percent=None)], now=NOW)
        assert plan["items"] == [], state
        assert plan["keep"] == ["Pile à changer — Velux (CH)"], state


def test_an_orphaned_anchor_never_closes_a_task():
    """L'entrée de registre a disparu (appareil remplacé, migration ZHA → Z2M
    du 2026-07-14 qui en a frappé plusieurs d'un coup) : `entity_id` est None.
    keep sans items, et surtout AUCUNE fermeture."""
    plan = battery_plan([_pile(entity_id=None, state=None)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — Velux (CH)"]


def test_an_untracked_battery_is_silent_everywhere():
    """tracked = 0 (tablette murale sur secteur) et tracked = NULL (découvert,
    pas décidé) : ni items, ni keep. Leur visibilité passe par le compteur
    `batteries_undeclared` et par le panneau, pas par todo.maintenance."""
    for tracked in (False, None):
        plan = battery_plan([_pile(tracked=tracked, state="3",
                                   last_percent=3.0)], now=NOW)
        assert plan == {"items": [], "keep": []}, tracked


def test_an_inactive_battery_is_ignored():
    plan = battery_plan([_pile(active=False, state="3", last_percent=3.0)], now=NOW)
    assert plan == {"items": [], "keep": []}


def test_the_spare_enriches_the_description_without_touching_the_summary():
    """Le suffixe est ce que le lot 5 apporte de neuf ; le résumé, lui, ne
    bouge pas d'un caractère, sinon la tâche existante se ferme."""
    plan = battery_plan([_pile(spare={"label": "CR2032", "cell_count": 1,
                                      "in_stock": 0.0})], now=NOW)
    assert plan["items"][0]["summary"] == "Pile à changer — Velux (CH)"
    assert plan["items"][0]["description"] == "18 % — 1× CR2032, aucune en stock"
    plan = battery_plan([_pile(spare={"label": "AAA", "cell_count": 2,
                                      "in_stock": 4.0})], now=NOW)
    assert plan["items"][0]["description"] == "18 % — 2× AAA, 4 en stock"


@pytest.mark.parametrize("pile", [
    _pile(), _pile(state="22", last_percent=22.0), _pile(state="26", last_percent=26.0),
    _pile(state="unavailable", last_reading_at="2026-08-19T00:00:00"),
    _pile(state="unknown"), _pile(entity_id=None, state=None),
    _pile(state=None, last_percent=None, last_reading_at=None),
    _pile(kind="built_in"), _pile(kind="rechargeable_cell"),
])
def test_items_are_always_a_subset_of_keep(pile):
    """L'invariant global. Sa violation EST le clignotement de tâche."""
    plan = battery_plan([pile], now=NOW)
    assert {i["summary"] for i in plan["items"]} <= set(plan["keep"])


def test_the_order_is_stable_and_lowest_first():
    piles = [_pile(id=1, label="A", state="18", last_percent=18.0),
             _pile(id=2, label="B", state="5", last_percent=5.0),
             _pile(id=3, label="C", state="12", last_percent=12.0)]
    assert _resumes(battery_plan(piles, now=NOW)) == [
        "Pile à changer — B", "Pile à changer — C", "Pile à changer — A"]


def test_keep_has_no_duplicates():
    """Deux piles portant le même libellé (deux « Capteur » dans deux pièces)
    ne doivent pas doubler une entrée de keep : `rejectattr('summary','in',…)`
    s'en moque, mais un doublon est le signe d'un libellé à corriger et il ne
    doit pas coûter deux fois."""
    piles = [_pile(id=1, state="22", last_percent=22.0),
             _pile(id=2, state="23", last_percent=23.0)]
    assert battery_plan(piles, now=NOW)["keep"] == ["Pile à changer — Velux (CH)"]
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_maintenance.py -q`
Expected: FAIL — `ModuleNotFoundError: custom_components.home_stock.domain.maintenance`

- [x] **Step 3: Écrire `domain/maintenance.py`**

Un seul passage sur la liste, dans l'ordre : pile inactive ou `tracked` non vrai → rien ; ancre orpheline (`entity_id is None`) ou état non numérique → `keep` seul ; état `unavailable`/`unknown` **et** `last_reading_at` connu et plus vieux que `mute_hours` → item « Pile HS ? » + les **deux** résumés dans `keep` ; sinon comparaison de `last_percent` aux deux seuils. Les items sont triés par `last_percent` croissant, `keep` est dédupliqué en conservant l'ordre de première apparition. Le suffixe de rechange est ajouté **à la description seule**.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/domain/test_maintenance.py -q`
Expected: PASS

---

## Task 3: La fusion du plan, toujours pure

**Files:**
- Modify: `custom_components/home_stock/domain/maintenance.py`
- Test: `tests/domain/test_maintenance.py`

**Interfaces:**
- Produit : `merge_plan(own: dict, *, extra_items: Sequence[Any] | None, extra_keep: Sequence[Any] | None, spares: Mapping[str, Mapping] | None = None) -> dict[str, list]`.

**Décisions de plan :**

1. **Un item qu'on ne comprend pas est recopié tel quel, jamais écarté.** Le service ne doit pas pouvoir faire disparaître la tâche du filtre du purificateur parce que la forme d'un item a évolué. « Ne pas comprendre » couvre : un item sans `summary`, un item qui n'est pas un dictionnaire, un item avec des clés en trop.
2. **L'ordre est stable** : les items du macro d'abord, dans leur ordre, puis ceux du lot 5. La réconciliation ne dépend pas de l'ordre, mais un ordre stable rend les diffs de test lisibles et l'annonce de Bleuenn reproductible.
3. **L'enrichissement d'un item du macro se fait par `entity`**, jamais par le texte du résumé. C'est la leçon exacte du raccord Grocy actuel, qui cherche un `entity_id` dans une description en clair : ici, `spares` est indexé par `entity_id` et l'appariement est une clé de dictionnaire.
4. **Un résumé en double entre les deux plans est fusionné, pas dupliqué** : c'est celui du macro qui gagne, sa description enrichie. `home_stock` n'a pas à écraser la mesure d'un aspirateur.

- [x] **Step 1: Écrire les tests**

Ajouter à `tests/domain/test_maintenance.py` :

```python
from custom_components.home_stock.domain.maintenance import merge_plan

MACRO = {
    "items": [
        {"summary": "Purificateur — filtre à remplacer",
         "description": "12 %", "entity": "sensor.purificateur_filtre"},
        {"summary": "Arroser Plante Télévision",
         "description": "18 % d'humidité", "entity": "sensor.plante_television_humidite"},
    ],
    "keep": ["Purificateur — filtre à remplacer", "Arroser Plante Télévision"],
}


def test_called_bare_the_merge_returns_the_batteries_alone():
    own = battery_plan([_pile()], now=NOW)
    fusion = merge_plan(own, extra_items=None, extra_keep=None)
    assert fusion == own


def test_the_macro_items_come_first_and_keep_their_order():
    own = battery_plan([_pile()], now=NOW)
    fusion = merge_plan(own, extra_items=MACRO["items"], extra_keep=MACRO["keep"])
    assert [i["summary"] for i in fusion["items"]] == [
        "Purificateur — filtre à remplacer", "Arroser Plante Télévision",
        "Pile à changer — Velux (CH)"]


def test_an_item_it_does_not_understand_is_copied_verbatim():
    """Le service ne doit PAS pouvoir faire disparaître la tâche du
    purificateur parce que la forme d'un item a évolué."""
    bizarres = [{"summary": "Vider la poubelle"},                 # pas d'entity
                {"summary": "Truc", "description": "x", "entity": "y", "urgence": 3},
                {"resume": "clé inconnue"},                       # pas de summary
                "une chaîne toute nue"]
    fusion = merge_plan(battery_plan([], now=NOW),
                        extra_items=bizarres, extra_keep=["Vider la poubelle"])
    assert fusion["items"] == bizarres


def test_a_macro_item_gets_its_spare_suffix_by_entity_not_by_text():
    fusion = merge_plan(
        battery_plan([], now=NOW), extra_items=MACRO["items"], extra_keep=MACRO["keep"],
        spares={"sensor.purificateur_filtre":
                {"label": "Filtre HEPA MB4", "cell_count": 1, "in_stock": 0.0}})
    assert fusion["items"][0]["description"] == "12 % — 1× Filtre HEPA MB4, aucun en stock"
    # La plante n'a pas de rechange : sa description est intacte.
    assert fusion["items"][1]["description"] == "18 % d'humidité"


def test_an_unknown_entity_in_spares_changes_nothing():
    fusion = merge_plan(battery_plan([], now=NOW), extra_items=MACRO["items"],
                        extra_keep=MACRO["keep"],
                        spares={"sensor.disparu": {"label": "X", "cell_count": 1,
                                                   "in_stock": 0.0}})
    assert fusion["items"] == MACRO["items"]


def test_a_summary_present_on_both_sides_is_merged_not_duplicated():
    own = battery_plan([_pile(label="Velux (CH)")], now=NOW)
    doublon = [{"summary": "Pile à changer — Velux (CH)",
                "description": "ancienne description", "entity": "sensor.velux_ch_batterie"}]
    fusion = merge_plan(own, extra_items=doublon, extra_keep=[])
    assert len(fusion["items"]) == 1
    assert fusion["items"][0]["description"] == "ancienne description"


def test_keep_is_the_union_deduplicated_and_ordered():
    own = battery_plan([_pile(state="22", last_percent=22.0)], now=NOW)
    fusion = merge_plan(own, extra_items=[], extra_keep=MACRO["keep"] + ["Arroser Plante Télévision"])
    assert fusion["keep"] == ["Purificateur — filtre à remplacer",
                              "Arroser Plante Télévision",
                              "Pile à changer — Velux (CH)"]


def test_the_merge_preserves_the_subset_invariant():
    own = battery_plan([_pile()], now=NOW)
    fusion = merge_plan(own, extra_items=MACRO["items"], extra_keep=MACRO["keep"])
    assert {i["summary"] for i in fusion["items"] if isinstance(i, dict) and "summary" in i} \
        <= set(fusion["keep"])


def test_extra_keep_that_is_not_a_list_of_strings_is_tolerated():
    """`extra_keep` arrive d'un rendu Jinja : il peut contenir n'importe quoi
    le jour où le macro change. Rien ne doit lever — une exception ici DÉSARME
    la fermeture (tâche 15), ce qui est correct mais coûte une synchro."""
    fusion = merge_plan(battery_plan([], now=NOW), extra_items=[],
                        extra_keep=["ok", None, 42, {"summary": "x"}])
    assert "ok" in fusion["keep"]
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_maintenance.py -q`
Expected: FAIL — `ImportError: cannot import name 'merge_plan'`

- [x] **Step 3: Écrire `merge_plan`**

Dans `domain/maintenance.py`, à la suite de `battery_plan`. Un item du macro est « compris » si c'est un `dict` avec un `summary` non vide ; sinon il est recopié à l'identique et n'entre dans aucun appariement. `extra_keep` est filtré aux chaînes non vides, dédupliqué en conservant l'ordre.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/domain/test_maintenance.py -q`
Expected: PASS

---

## Task 4: Les invariants de pile, écrits une fois pour les deux surfaces

**Files:**
- Modify: `custom_components/home_stock/validators.py`
- Modify: `custom_components/home_stock/messages.py`
- Test: `tests/test_validators.py`

**Interfaces:**
- Consomme : `finite_float`, `bounded_int`, `bounded_text`, `iso_date`, `preview` — déjà présents.
- Produit, **en fin de `validators.py`** :
  - `percent_threshold(value) -> float` — fini, `0 ≤ v ≤ 100`.
  - `cell_count(value) -> int` — entier vrai (pas un `bool`), `1 ≤ n ≤ 24`.
  - `tracked_flag(value) -> bool | None` — `True`, `False` ou `None`, strictement ; un `0`/`1`/`"oui"` est refusé.
  - `check_battery_fields(fields: Mapping[str, Any], *, kind: str) -> None` — lève `vol.Invalid` en anglais. Les six règles :
    1. `keep_percent >= low_percent` ;
    2. `tracked is False` ⇒ `exclusion_reason` non vide après `strip()` ;
    3. `kind == "built_in"` ⇒ `product_id is None` ;
    4. `cell_count >= 1` ;
    5. `low_percent` et `keep_percent` dans `[0, 100]` ;
    6. `installed_on` par `iso_date`.
  - `check_battery_event(kind: str, *, battery_kind: str, consume_spare: bool, product_id: int | None) -> None` — `charge` interdit sur `primary` ; `replacement` interdit sur `built_in` ; `consume_spare` vrai sans `product_id` refusé.

**Décision de plan — pourquoi une fonction et pas deux schémas.** Le voluptuous d'un service et celui d'un websocket peuvent valider *un champ* de la même façon sans effort ; ils **divergent toujours** sur les règles qui lient deux champs, parce que ce sont les seules qu'on écrit à la main deux fois. `keep_percent >= low_percent` est exactement de celles-là, et un `keep` plus bas qu'un `low` fait clignoter la tâche à chaque synchronisation — le piège que CLAUDE.md documente, rendu ici **impossible à poser**. Les tâches 11 et 12 appellent toutes les deux `check_battery_fields`, et un test croisé (tâche 12) le prouve commande par commande.

- [x] **Step 1: Écrire les tests**

Dans `tests/test_validators.py`, **en fin de fichier** :

```python
from custom_components.home_stock.validators import (
    cell_count, check_battery_event, check_battery_fields, percent_threshold,
    tracked_flag,
)


def test_percent_threshold_accepts_the_range_and_refuses_the_rest():
    assert percent_threshold(20) == 20.0
    assert percent_threshold("25,5") == 25.5
    assert percent_threshold(0) == 0.0
    assert percent_threshold(100) == 100.0
    for mauvais in (-0.1, 100.1, float("nan"), float("inf"), "beaucoup", None, True):
        with pytest.raises(vol.Invalid):
            percent_threshold(mauvais)


def test_cell_count_refuses_zero_a_float_and_a_bool():
    assert cell_count(2) == 2
    for mauvais in (0, -1, 2.0, True, "2", None, 25):
        with pytest.raises(vol.Invalid):
            cell_count(mauvais)


def test_tracked_flag_is_strict():
    assert tracked_flag(True) is True
    assert tracked_flag(False) is False
    assert tracked_flag(None) is None
    for mauvais in (0, 1, "oui", "true", ""):
        with pytest.raises(vol.Invalid):
            tracked_flag(mauvais)


def test_keep_must_not_be_below_low():
    """Un seuil de maintien plus bas que le seuil d'apparition fait clignoter
    la tâche à CHAQUE synchronisation : elle apparaît sous 20, se ferme au-
    dessus de 15, réapparaît. Impossible à poser, aux deux surfaces."""
    with pytest.raises(vol.Invalid):
        check_battery_fields({"low_percent": 20.0, "keep_percent": 15.0}, kind="primary")
    check_battery_fields({"low_percent": 20.0, "keep_percent": 20.0}, kind="primary")


def test_untracked_requires_a_reason():
    with pytest.raises(vol.Invalid):
        check_battery_fields({"tracked": False}, kind="primary")
    with pytest.raises(vol.Invalid):
        check_battery_fields({"tracked": False, "exclusion_reason": "   "}, kind="primary")
    check_battery_fields({"tracked": False, "exclusion_reason": "tablette sur secteur"},
                         kind="primary")


def test_a_built_in_battery_has_no_spare():
    """Une batterie soudée ne se remplace pas : lui donner un produit de
    rechange, c'est promettre une ligne de courses qui ne servira jamais."""
    with pytest.raises(vol.Invalid):
        check_battery_fields({"product_id": 4}, kind="built_in")
    check_battery_fields({"product_id": 4}, kind="primary")


def test_a_primary_cannot_be_charged_and_a_built_in_cannot_be_replaced():
    with pytest.raises(vol.Invalid):
        check_battery_event("charge", battery_kind="primary",
                            consume_spare=False, product_id=None)
    with pytest.raises(vol.Invalid):
        check_battery_event("replacement", battery_kind="built_in",
                            consume_spare=False, product_id=None)
    check_battery_event("charge", battery_kind="rechargeable_cell",
                        consume_spare=False, product_id=None)
    check_battery_event("replacement", battery_kind="primary",
                        consume_spare=True, product_id=3)


def test_consuming_a_spare_that_does_not_exist_is_refused_before_writing():
    with pytest.raises(vol.Invalid):
        check_battery_event("replacement", battery_kind="primary",
                            consume_spare=True, product_id=None)
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_validators.py -q`
Expected: FAIL — `ImportError: cannot import name 'percent_threshold'`

- [x] **Step 3: Écrire les helpers et les phrases françaises**

Dans `validators.py`, en fin de fichier. Les messages restent **en anglais** (ce sont des exceptions de code) ; leur traduction va dans `messages.py`, **en fin** de `DOMAIN_ERROR_PATTERNS` :

```python
(re.compile(r"^keep_percent must not be below low_percent"), "invalid_value",
 lambda m: "Le seuil de maintien ne peut pas être sous le seuil d'apparition : "
           "la tâche apparaîtrait et se refermerait à chaque synchronisation."),
(re.compile(r"^an untracked battery needs a reason$"), "invalid_value",
 lambda m: "Ignorer une pile demande un motif — sinon personne ne saura "
           "pourquoi elle n'est plus suivie."),
(re.compile(r"^a built_in battery has no spare$"), "invalid_value",
 lambda m: "Une batterie intégrée ne se remplace pas : elle n'a pas de pile de rechange."),
(re.compile(r"^a primary battery cannot be charged$"), "invalid_value",
 lambda m: "Une pile jetable ne se recharge pas."),
(re.compile(r"^a built_in battery cannot be replaced$"), "invalid_value",
 lambda m: "Une batterie intégrée ne se remplace pas : on la recharge."),
(re.compile(r"^unknown battery (\d+)$"), "not_found",
 lambda m: f"Pile {m.group(1)} inconnue."),
(re.compile(r"^unknown equipment (\d+)$"), "not_found",
 lambda m: f"Équipement {m.group(1)} inconnu."),
```

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_validators.py -q`
Expected: PASS

---

## Task 5: Les dépôts des quatre tables

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/storage/test_repositories_equipment.py` (nouveau)

**Interfaces:**
- Produit, **en fin de `repositories.py`**, dans une section `# --- lot 5 : piles, équipements, consommables ---` :
  - `insert_battery(conn, *, label: str, kind: str, **fields) -> int`
  - `update_battery_fields(conn, battery_id: int, fields: dict) -> None` (via `_update_fields`, déjà présent)
  - `get_battery(conn, battery_id) -> dict | None`
  - `list_batteries(conn, *, active_only: bool = True) -> list[dict]` — jointure gauche sur `product` pour le libellé de la rechange, et sur `equipment` pour le nom.
  - `battery_by_anchor(conn, entity_registry_id: str) -> dict | None`
  - `set_battery_reading(conn, battery_id: int, *, percent: float, at: str) -> None`
  - `insert_battery_event(conn, *, battery_id, occurred_at, kind, movement_id=None, note=None, idempotency_key=None) -> int`
  - `battery_event_by_key(conn, idempotency_key: str) -> dict | None`
  - `list_battery_events(conn, battery_id: int, limit: int = 20) -> list[dict]`
  - `spare_stock(conn, product_ids: Sequence[int]) -> dict[int, float]` — quantité restante par produit, réutilisant la logique de `stock_rows`.
  - `insert_equipment(conn, *, name: str, **fields) -> int`, `update_equipment_fields`, `get_equipment`, `list_equipment(conn, *, active_only=True)`
  - `link_consumable(conn, *, equipment_id, product_id, role, **fields) -> int`, `unlink_consumable(conn, consumable_id) -> None`, `list_consumables(conn, equipment_id: int | None = None)`
  - `warranty_rows(conn) -> list[dict]` — `name`, `purchased_on`, `warranty_months`, `warranty_ends_on` **calculé en Python**, jamais stocké ; trié par échéance croissante, les lignes sans date d'achat ou sans durée exclues.

**Décision de plan — `spare_stock` ne recalcule rien.** Le stock restant d'un produit est déjà exprimé par `stock_rows` ; `spare_stock` en est un filtre sur des `product_id`, pas une seconde formule. Deux formules pour un même nombre se mettent à diverger le jour où l'une gagne une correction — et c'est ce nombre qui décide si la tâche dit « aucune en stock ».

- [x] **Step 1: Écrire les tests**

Créer `tests/storage/test_repositories_equipment.py`, sur le modèle de `tests/storage/test_repositories_journal.py` (reprendre son helper d'ouverture d'une base migrée plutôt que d'en écrire un autre) :

```python
def test_a_battery_round_trips_with_its_defaults(conn):
    battery_id = insert_battery(conn, label="Velux (CH)", kind="primary")
    row = get_battery(conn, battery_id)
    assert row["cell_count"] == 1
    assert row["low_percent"] == 20.0 and row["keep_percent"] == 25.0
    assert row["tracked"] is None          # découvert, pas décidé
    assert row["active"] == 1


def test_list_batteries_carries_the_spare_label_and_its_stock(conn):
    product_id = insert_product(conn, name="CR2032", base_unit="piece", edible=0)
    _seed_batch(conn, product_id, quantity=3)
    insert_battery(conn, label="Velux (CH)", kind="primary", product_id=product_id)
    row = list_batteries(conn)[0]
    assert row["spare_label"] == "CR2032"
    assert spare_stock(conn, [product_id])[product_id] == 3.0


def test_spare_stock_is_zero_not_missing_for_a_product_without_a_batch(conn):
    """« aucune en stock » et « on ne sait pas » ne sont pas la même phrase, et
    c'est la première que la tâche doit dire."""
    product_id = insert_product(conn, name="9 V", base_unit="piece", edible=0)
    assert spare_stock(conn, [product_id]) == {product_id: 0.0}


def test_set_battery_reading_writes_both_columns(conn):
    battery_id = insert_battery(conn, label="X", kind="primary")
    set_battery_reading(conn, battery_id, percent=18.0, at="2026-08-21T06:00:00")
    row = get_battery(conn, battery_id)
    assert row["last_percent"] == 18.0
    assert row["last_reading_at"] == "2026-08-21T06:00:00"


def test_battery_by_anchor_finds_nothing_for_an_unknown_uuid(conn):
    assert battery_by_anchor(conn, "9c03f558eabb5b7691b37e0a43558e9f") is None


def test_battery_events_come_back_newest_first(conn):
    battery_id = insert_battery(conn, label="X", kind="primary")
    insert_battery_event(conn, battery_id=battery_id, occurred_at="2026-01-01T00:00:00",
                         kind="install")
    insert_battery_event(conn, battery_id=battery_id, occurred_at="2026-06-01T00:00:00",
                         kind="replacement")
    assert [e["kind"] for e in list_battery_events(conn, battery_id)] == \
        ["replacement", "install"]


def test_an_event_key_is_unique(conn):
    battery_id = insert_battery(conn, label="X", kind="primary")
    insert_battery_event(conn, battery_id=battery_id, occurred_at="2026-01-01T00:00:00",
                         kind="install", idempotency_key="k")
    with pytest.raises(sqlite3.IntegrityError):
        insert_battery_event(conn, battery_id=battery_id,
                             occurred_at="2026-01-02T00:00:00",
                             kind="install", idempotency_key="k")


def test_warranty_rows_computes_the_end_date_and_never_stores_it(conn):
    insert_equipment(conn, name="Purificateur", purchased_on="2024-03-15",
                     warranty_months=24)
    row = warranty_rows(conn)[0]
    assert row["warranty_ends_on"] == "2026-03-15"
    assert "warranty_ends_on" not in {c["name"] for c in
                                      conn.execute("PRAGMA table_info(equipment)")}


def test_warranty_rows_handles_the_end_of_month(conn):
    """31 janvier + 1 mois n'existe pas. La réponse retenue est le dernier jour
    du mois d'arrivée — jamais un débordement sur mars."""
    insert_equipment(conn, name="A", purchased_on="2024-01-31", warranty_months=1)
    assert warranty_rows(conn)[0]["warranty_ends_on"] == "2024-02-29"


def test_warranty_rows_skips_what_it_cannot_compute(conn):
    insert_equipment(conn, name="Poêle")                       # ni date ni durée
    insert_equipment(conn, name="B", purchased_on="2024-01-01")  # pas de durée
    assert warranty_rows(conn) == []


def test_a_consumable_link_carries_its_thresholds(conn):
    equipment_id = insert_equipment(conn, name="Purificateur")
    product_id = insert_product(conn, name="Filtre HEPA MB4", base_unit="piece", edible=0)
    link_consumable(conn, equipment_id=equipment_id, product_id=product_id,
                    role="filter", label="filtre HEPA", low_value=15.0,
                    keep_value=20.0, unit="percent")
    row = list_consumables(conn, equipment_id)[0]
    assert row["role"] == "filter" and row["unit"] == "percent"
    assert row["product_name"] == "Filtre HEPA MB4"
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/storage/test_repositories_equipment.py -q`
Expected: FAIL — `ImportError`

- [x] **Step 3: Écrire les dépôts**

En fin de `repositories.py`. `warranty_ends_on` est calculé en Python (`date` + mois, en bornant au dernier jour du mois d'arrivée) : c'est la seule arithmétique du fichier qui ne soit pas du SQL, et son commentaire doit dire pourquoi elle n'est pas une colonne.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage/test_repositories_equipment.py -q`
Expected: PASS

---

## Task 6: `application.py` — déclarer, corriger, relever

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_application_batteries.py` (nouveau)

**Interfaces:**
- Produit, **en fin de la classe `StockManager`** :
  - `declare_battery(*, label, kind, entity_registry_id=None, device_id=None, equipment_id=None, product_id=None, cell_count=1, tracked=None, exclusion_reason=None, low_percent=DEFAULT_LOW_PERCENT, keep_percent=DEFAULT_KEEP_PERCENT, installed_on=None, expected_life_days=None, note=None, external_ref=None, idempotency_key=None) -> int`
  - `update_battery(battery_id: int, fields: dict) -> None`
  - `list_batteries(*, include_untracked: bool = True) -> list[dict]` — chaque ligne au format que `domain/maintenance.battery_plan` attend, **moins** `state` et `entity_id`, que seul le coordinateur sait résoudre.
  - `record_reading(battery_id: int, *, percent: float, at: str) -> None`
  - `maintenance_plan(*, now, extra_items=None, extra_keep=None, readings: Mapping[int, dict]) -> dict` — assemble, appelle `battery_plan` puis `merge_plan`, et pose `complete`.

**Décisions de plan :**

1. **`declare_battery` valide avant d'écrire**, en appelant `check_battery_fields` — même si les deux surfaces l'ont déjà appelée. Une troisième porte existe : l'import (tâche 13). Une règle vérifiée seulement aux surfaces est une règle qu'un import peut contourner, et c'est précisément l'import qui écrit 14 lignes d'un coup.
2. **`update_battery` refuse un champ inconnu**, comme `update_article_fields` le fait déjà. Une faute de frappe dans un nom de colonne doit être un refus, pas un silence.
3. **`maintenance_plan` ne lève jamais** vers l'appelant : elle attrape, journalise, et rend `complete: False`. C'est le contrat de la tâche 15 : un plan incomplet a le droit d'ajouter et de rafraîchir, jamais de fermer.

- [x] **Step 1: Écrire les tests**

Créer `tests/test_application_batteries.py`, sur le modèle de `tests/test_application.py` :

```python
def test_declaring_a_battery_returns_its_id_and_stores_the_label(manager):
    battery_id = manager.declare_battery(label="Velux (CH)", kind="primary")
    assert manager.list_batteries()[0]["label"] == "Velux (CH)"


def test_declaring_is_idempotent_on_its_key(manager):
    first = manager.declare_battery(label="X", kind="primary", idempotency_key="k")
    second = manager.declare_battery(label="X", kind="primary", idempotency_key="k")
    assert first == second
    assert len(manager.list_batteries()) == 1


def test_declaring_twice_on_the_same_anchor_is_refused(manager):
    manager.declare_battery(label="A", kind="primary", entity_registry_id="abc")
    with pytest.raises(sqlite3.IntegrityError):
        manager.declare_battery(label="B", kind="primary", entity_registry_id="abc")


def test_the_application_refuses_what_the_surfaces_refuse(manager):
    """Troisième porte : l'import. Une règle vérifiée seulement aux surfaces
    est une règle qu'un import de 14 lignes contourne."""
    with pytest.raises(vol.Invalid):
        manager.declare_battery(label="X", kind="primary",
                                low_percent=20.0, keep_percent=10.0)
    with pytest.raises(vol.Invalid):
        manager.declare_battery(label="X", kind="built_in", product_id=1)
    with pytest.raises(vol.Invalid):
        manager.declare_battery(label="X", kind="primary", tracked=False)


def test_updating_an_unknown_field_is_refused(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    with pytest.raises(ValueError):
        manager.update_battery(battery_id, {"labell": "faute de frappe"})


def test_updating_an_unknown_battery_says_so(manager):
    with pytest.raises(ValueError, match="unknown battery 999"):
        manager.update_battery(999, {"label": "X"})


def test_record_reading_stores_the_percent_and_the_moment(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    manager.record_reading(battery_id, percent=18.0, at="2026-08-21T06:00:00")
    row = manager.list_batteries()[0]
    assert row["last_percent"] == 18.0 and row["last_reading_at"] == "2026-08-21T06:00:00"


def test_list_batteries_gives_the_domain_exactly_what_it_expects(manager):
    """Le contrat entre `application` et `domain/maintenance` : si une clé
    manque, `battery_plan` la lira à None et la pile deviendra silencieusement
    « jamais relevée » — le genre de panne qui ne lève rien."""
    manager.declare_battery(label="X", kind="primary", tracked=True)
    row = manager.list_batteries()[0]
    assert {"id", "label", "kind", "tracked", "active", "last_percent",
            "last_reading_at", "low_percent", "keep_percent", "spare"} <= set(row)


def test_maintenance_plan_marks_itself_complete(manager):
    manager.declare_battery(label="X", kind="primary", tracked=True)
    plan = manager.maintenance_plan(now=NOW, readings={})
    assert plan["complete"] is True
    assert set(plan) == {"items", "keep", "complete"}


def test_maintenance_plan_reports_incomplete_instead_of_raising(manager, monkeypatch):
    """Le risque n°1 du lot : un plan qui lève ferait disparaître les items de
    pile de `items` ET de `keep`, et une seule synchro à 5 h 05 refermerait les
    14 tâches. Le refus doit être une donnée, pas une exception qui se perd."""
    monkeypatch.setattr(manager, "list_batteries",
                        lambda **kw: (_ for _ in ()).throw(sqlite3.OperationalError("boom")))
    plan = manager.maintenance_plan(now=NOW, readings={})
    assert plan["complete"] is False
    assert plan["items"] == [] and plan["keep"] == []
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_application_batteries.py -q`
Expected: FAIL — `AttributeError: 'StockManager' object has no attribute 'declare_battery'`

- [x] **Step 3: Écrire les méthodes**

En fin de `StockManager`, chacune dans **un seul** `db.write()` ou `db.read()`, jamais imbriqués.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_application_batteries.py -q`
Expected: PASS

---

## Task 7: `record_battery_event` et la rechange qui sort du placard

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_application_batteries.py`

**Interfaces:**
- Consomme : `_namespaced_key('battery_event', key)` — l'utilitaire existe déjà ; `consume`/`consume_batch` et leur chemin FIFO du lot 0 ; `check_battery_event` (tâche 4).
- Produit : `record_battery_event(battery_id: int, *, kind: str, occurred_at: str | None = None, consume_spare: bool | None = None, note: str | None = None, idempotency_key: str | None = None) -> dict` → `{"event_id": int, "movement_id": int | None, "spare_refused": str | None}`.

**Décisions de plan, chacune testée ci-dessous :**

1. **Une transaction, jamais deux.** L'événement et le mouvement s'écrivent dans **le même** `db.write()`. `Database._lock` n'est pas réentrant : appeler `self.consume(...)` depuis l'intérieur d'un `db.write()` **bloque le processus pour toujours**. Après le merge avec le lot 3, utiliser son helper `_consume_within(conn, …)` s'il existe ; sinon extraire le corps de `consume` de la même façon.
2. **L'idempotence traverse les deux tables.** La clé du mouvement est `_namespaced_key('battery_event', key)` : un rejeu depuis la file hors-ligne ne peut ni créer deux événements, ni décrémenter deux fois le placard. Un rejeu rend **le même `event_id`**.
3. **`rechargeable_cell` ne consomme rien par défaut.** Les quatre LADDA tournent entre le tiroir et trois capteurs ; compter chaque rotation viderait le stock en un an alors que les quatre cellules sont toujours dans la maison, et déclencherait une rupture mensongère — donc une ligne de courses pour des piles qu'on possède. `consume_spare: true` reste disponible pour le jour où une cellule meurt.
4. **Le défaut de `consume_spare` dépend de `kind`** : `True` pour `primary` **si** un `product_id` existe, `False` pour `rechargeable_cell`, jamais applicable pour `built_in`. `consume_spare` passé explicitement gagne toujours.
5. **Stock insuffisant : l'événement s'écrit quand même, et le refus est visible.** On ne perd pas l'information « la pile a été changée » parce que le placard n'était pas à jour. Le refus revient dans `spare_refused` (phrase française) et remonte jusqu'au panneau.
6. **`installed_on` prend la date de l'événement, `last_percent` et `last_reading_at` repassent à `NULL`** après un `replacement` ou un `install` : on ne sait rien de la nouvelle pile tant que l'appareil n'a pas parlé. C'est aussi ce qui empêche un « Pile HS ? » immédiat.

- [x] **Step 1: Écrire les tests**

Ajouter à `tests/test_application_batteries.py` :

```python
def test_replacing_a_primary_consumes_one_spare(manager):
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="Velux (CH)", kind="primary",
                                         product_id=product_id, cell_count=1)
    result = manager.record_battery_event(battery_id, kind="replacement")
    assert result["movement_id"] is not None
    assert _stock_of(manager, product_id) == 2.0


def test_a_two_cell_device_consumes_two(manager):
    product_id = _seed_spare(manager, name="AAA", quantity=4)
    battery_id = manager.declare_battery(label="Interrupteur cuisine", kind="primary",
                                         product_id=product_id, cell_count=2)
    manager.record_battery_event(battery_id, kind="replacement")
    assert _stock_of(manager, product_id) == 2.0


def test_the_movement_is_a_plain_consumption(manager):
    """Aucun motif `battery` : ajouter un motif aurait obligé à repasser sur
    CONSUME_REASONS, totals_between, journal_entries et les onze capteurs du
    lot 2, pour une distinction qui se lit déjà dans `product.edible = 0`."""
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="X", kind="primary", product_id=product_id)
    movement_id = manager.record_battery_event(battery_id, kind="replacement")["movement_id"]
    row = _movement(manager, movement_id)
    assert row["reason"] == "consumption"
    assert row["kcal"] is None              # aucune table nutritionnelle : NULL, pas 0.0


def test_a_rechargeable_cell_consumes_nothing_by_default(manager):
    product_id = _seed_spare(manager, name="LADDA AAA", quantity=4)
    battery_id = manager.declare_battery(label="Capteur", kind="rechargeable_cell",
                                         product_id=product_id)
    result = manager.record_battery_event(battery_id, kind="charge")
    assert result["movement_id"] is None
    assert _stock_of(manager, product_id) == 4.0


def test_a_rechargeable_cell_consumes_when_asked_explicitly(manager):
    product_id = _seed_spare(manager, name="LADDA AAA", quantity=4)
    battery_id = manager.declare_battery(label="Capteur", kind="rechargeable_cell",
                                         product_id=product_id)
    manager.record_battery_event(battery_id, kind="replacement", consume_spare=True)
    assert _stock_of(manager, product_id) == 3.0


def test_a_built_in_battery_never_consumes(manager):
    battery_id = manager.declare_battery(label="Rideau cuisine", kind="built_in")
    assert manager.record_battery_event(battery_id, kind="charge")["movement_id"] is None
    with pytest.raises(vol.Invalid):
        manager.record_battery_event(battery_id, kind="replacement")


def test_a_primary_cannot_be_charged(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    with pytest.raises(vol.Invalid):
        manager.record_battery_event(battery_id, kind="charge")


def test_replaying_the_key_writes_neither_a_second_event_nor_a_second_decrement(manager):
    product_id = _seed_spare(manager, name="CR2032", quantity=3)
    battery_id = manager.declare_battery(label="X", kind="primary", product_id=product_id)
    first = manager.record_battery_event(battery_id, kind="replacement",
                                         idempotency_key="k")
    second = manager.record_battery_event(battery_id, kind="replacement",
                                          idempotency_key="k")
    assert first["event_id"] == second["event_id"]
    assert first["movement_id"] == second["movement_id"]
    assert _stock_of(manager, product_id) == 2.0
    assert len(manager.list_battery_events(battery_id)) == 1


def test_an_empty_cupboard_still_records_the_replacement(manager):
    """On ne perd pas « la pile a été changée » parce que le placard n'était
    pas à jour. Le refus est une donnée rendue, pas une exception avalée."""
    product_id = _seed_spare(manager, name="CR2032", quantity=0)
    battery_id = manager.declare_battery(label="X", kind="primary", product_id=product_id)
    result = manager.record_battery_event(battery_id, kind="replacement")
    assert result["movement_id"] is None
    assert "Stock insuffisant" in result["spare_refused"]
    assert len(manager.list_battery_events(battery_id)) == 1


def test_a_replacement_forgets_the_old_reading(manager):
    battery_id = manager.declare_battery(label="X", kind="primary")
    manager.record_reading(battery_id, percent=4.0, at="2026-08-20T00:00:00")
    manager.record_battery_event(battery_id, kind="replacement",
                                 occurred_at="2026-08-21T10:00:00")
    row = manager.list_batteries()[0]
    assert row["last_percent"] is None and row["last_reading_at"] is None
    assert row["installed_on"] == "2026-08-21"


def test_a_fresh_replacement_produces_no_task_at_all(manager):
    """Le corollaire du test précédent, vu depuis le plan : une pile qu'on
    vient de changer ne doit produire ni item de niveau ni « Pile HS ? »."""
    battery_id = manager.declare_battery(label="X", kind="primary", tracked=True)
    manager.record_reading(battery_id, percent=4.0, at="2026-08-20T00:00:00")
    manager.record_battery_event(battery_id, kind="replacement")
    plan = manager.maintenance_plan(now=NOW, readings={})
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — X"]


def test_a_charge_on_an_unknown_battery_says_so(manager):
    with pytest.raises(ValueError, match="unknown battery 999"):
        manager.record_battery_event(999, kind="charge")
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_application_batteries.py -q`
Expected: FAIL — `AttributeError: … 'record_battery_event'`

- [x] **Step 3: Écrire `record_battery_event`**

Une seule transaction. Ordre : relire la pile ; `check_battery_event` ; si la clé existe déjà, rendre l'événement existant sans rien écrire ; sinon écrire l'événement, puis tenter la consommation dans la **même** connexion, en attrapant l'erreur de stock pour la traduire en `spare_refused` et laisser l'événement en place.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_application_batteries.py -q`
Expected: PASS

- [x] **Step 5: Prouver l'absence d'interblocage**

Run: `./scripts/test.sh tests/test_application_batteries.py -q --timeout=60`
Expected: PASS, sans expiration. Un `db.write()` imbriqué se manifeste ici par un test qui ne rend jamais la main — pas par une exception.

---

## Task 8: Les équipements, leur garantie et leurs consommables

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_application_equipment.py` (nouveau)

**Interfaces:**
- Produit, **en fin de la classe `StockManager`** :
  - `create_equipment(*, name, device_id=None, location_id=None, brand=None, model=None, serial=None, purchased_on=None, purchase_price=None, warranty_months=None, manual_url=None, manual_media_id=None, receipt_media_id=None, note=None, external_ref=None, idempotency_key=None) -> int`
  - `update_equipment(equipment_id: int, fields: dict) -> None`
  - `list_equipment() -> list[dict]` — nom, emplacement, garantie calculée et jours restants, nombre de consommables.
  - `get_equipment(equipment_id: int) -> dict` — la fiche, plus ses consommables (usure, stock de rechange) et ses piles.
  - `link_consumable(...) -> int`, `unlink_consumable(consumable_id: int) -> None`
  - `warranties(*, today: date) -> list[dict]` — les échéances **à venir**, triées, avec `days_left`.

**Décisions de plan :**

1. **`purchase_price` n'écrit aucun mouvement.** C'est une donnée de fiche. Un test le prouve en comptant les mouvements avant et après — c'est le genre de règle qui se perd au premier « pendant qu'on y est ».
2. **`warranty_months` et `purchased_on` vont ensemble ou pas du tout** : une durée sans date d'achat n'est pas calculable, et la ligne est simplement absente des échéances plutôt que rendue avec un `None` que quelqu'un finira par afficher.
3. **`manual_media_id` est un chemin relatif sous `media/`, jamais absolu, jamais sous `www/`.** Un chemin qui remonte (`..`) est refusé à l'écriture. Un fichier absent n'est **pas** une erreur : le lien est signalé introuvable, et aucune entité ne devient indisponible pour autant.
4. **Une échéance dépassée n'est plus une échéance à venir** : elle sort de `warranties()`, et donc du capteur. C'est cohérent avec « la garantie ne produit jamais de tâche » : ce qui est fini ne se regarde plus.

- [x] **Step 1: Écrire les tests**

Créer `tests/test_application_equipment.py` :

```python
def test_creating_an_equipment_writes_no_movement(manager):
    """Une télévision à 900 € dans un journal dont `cost_today` alimente la
    dépense alimentaire du jour rendrait ce capteur inutilisable pour toujours
    — et le journal est en ajout seul, donc la faute ne serait pas corrigible."""
    avant = len(manager.export_journal())
    manager.create_equipment(name="Télévision", purchase_price=900.0,
                             purchased_on="2024-05-02", warranty_months=24)
    assert len(manager.export_journal()) == avant


def test_an_equipment_without_a_device_is_perfectly_normal(manager):
    """Une poêle n'a pas de `device_id`. Exiger un appareil reviendrait à ne
    suivre que ce qui est connecté, ce qui exclut la moitié de la cuisine."""
    equipment_id = manager.create_equipment(name="Poêle 28 cm")
    assert manager.get_equipment(equipment_id)["device_id"] is None


def test_the_name_is_unique(manager):
    manager.create_equipment(name="Purificateur")
    with pytest.raises(sqlite3.IntegrityError):
        manager.create_equipment(name="Purificateur")


def test_warranties_are_computed_sorted_and_forward_looking(manager):
    manager.create_equipment(name="A", purchased_on="2025-01-01", warranty_months=24)
    manager.create_equipment(name="B", purchased_on="2024-01-01", warranty_months=24)
    manager.create_equipment(name="C", purchased_on="2020-01-01", warranty_months=24)
    noms = [w["name"] for w in manager.warranties(today=date(2026, 8, 21))]
    assert noms == ["A"]          # B a expiré en janvier 2026, C en 2022
    assert manager.warranties(today=date(2026, 8, 21))[0]["days_left"] == 133


def test_a_duration_without_a_purchase_date_is_simply_absent(manager):
    manager.create_equipment(name="A", warranty_months=24)
    assert manager.warranties(today=date(2026, 8, 21)) == []


def test_a_bad_purchase_date_is_refused_before_it_can_break_the_coordinator(manager):
    """`iso_date` existe pour ça : une date mal formée devient un ValueError à
    CHAQUE rafraîchissement du coordinateur, et toutes les entités partent en
    `unavailable` — dans une table qu'un design en ajout seul ne répare pas."""
    for mauvais in ("02/05/2024", "2024-13-01", "pas une date", 20240502):
        with pytest.raises(vol.Invalid):
            manager.create_equipment(name=f"X{mauvais}", purchased_on=mauvais)


def test_a_manual_path_that_escapes_media_is_refused(manager):
    for mauvais in ("../config/secrets.yaml", "/etc/passwd", "www/notice.pdf"):
        with pytest.raises(vol.Invalid):
            manager.create_equipment(name=f"Y{mauvais}", manual_media_id=mauvais)
    manager.create_equipment(name="OK", manual_media_id="notices/purificateur.pdf")


def test_linking_a_consumable_uses_the_catalogue_and_nothing_else(manager):
    equipment_id = manager.create_equipment(name="Purificateur")
    product_id = _seed_spare(manager, name="Filtre HEPA MB4", quantity=1)
    manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                            role="filter", label="filtre HEPA",
                            low_value=15.0, keep_value=20.0, unit="percent")
    fiche = manager.get_equipment(equipment_id)
    assert fiche["consumables"][0]["product_name"] == "Filtre HEPA MB4"
    assert fiche["consumables"][0]["in_stock"] == 1.0


def test_the_same_product_can_be_two_roles_but_not_twice_the_same(manager):
    equipment_id = manager.create_equipment(name="Aspirateur")
    product_id = _seed_spare(manager, name="Brosse", quantity=2)
    manager.link_consumable(equipment_id=equipment_id, product_id=product_id, role="brush")
    manager.link_consumable(equipment_id=equipment_id, product_id=product_id, role="other")
    with pytest.raises(sqlite3.IntegrityError):
        manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                                role="brush")


def test_unlinking_leaves_the_product_alone(manager):
    """Délier n'efface pas un produit : le filtre reste au catalogue, avec son
    stock et son historique de prix."""
    equipment_id = manager.create_equipment(name="Purificateur")
    product_id = _seed_spare(manager, name="Filtre", quantity=1)
    link_id = manager.link_consumable(equipment_id=equipment_id, product_id=product_id,
                                      role="filter")
    manager.unlink_consumable(link_id)
    assert manager.get_equipment(equipment_id)["consumables"] == []
    assert _stock_of(manager, product_id) == 1.0
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_application_equipment.py -q`
Expected: FAIL — `AttributeError: … 'create_equipment'`

- [x] **Step 3: Écrire les méthodes et le garde-fou de chemin**

Le contrôle de `manual_media_id`/`receipt_media_id` va dans `validators.py` (`media_path(value)`) pour être appelable par les deux surfaces : chemin relatif, sans `..`, sans préfixe `www/`, sans début par `/`.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_application_equipment.py -q`
Expected: PASS

---

## Task 9: Le coordinateur — les ancres, les relevés, et `last_reading_at`

**Files:**
- Modify: `custom_components/home_stock/coordinator.py`
- Test: `tests/test_coordinator_batteries.py` (nouveau)

**Interfaces:**
- Consomme : `homeassistant.helpers.entity_registry.async_get(hass)` et `device_registry.async_get(hass)` ; `manager.list_batteries()`, `manager.record_reading()`, `manager.warranties()`.
- Produit :
  - `resolve_battery_anchors(hass, rows) -> list[dict]` — pour chaque ligne, ajoute `entity_id` (résolu depuis `entity_registry_id`, sinon `None`), `device_name`, `model`, `orphaned: bool`. **Fonction module-level**, pour être testable sans coordinateur.
  - `undeclared_battery_sensors(hass, known_registry_ids) -> list[dict]` — les entités `device_class: battery` du registre sans ligne `battery`, avec leur `entity_id`, leur nom d'appareil et leur modèle.
  - Dans `coordinator.data` : deux clés de plus, `"batteries"` et `"warranties"`.

**Décisions de plan :**

1. **L'`entity_id` n'est jamais stocké, il est résolu à chaque rafraîchissement.** Renommer une entité en deux clics ne casse plus rien — le défaut exact que CLAUDE.md reproche au raccord Grocy actuel. Le `unique_id` n'est gardé nulle part comme clé : il n'est unique que par plate-forme.
2. **`last_reading_at` n'est écrit que sur un relevé numérique.** `unavailable`, `unknown`, une chaîne non numérique, une entité absente : aucune écriture. Sinon la date dirait « on a regardé », alors qu'elle doit dire « l'appareil a parlé » — et le seuil de 26 h ne mesurerait plus rien.
3. **L'écriture est parcimonieuse** : si la valeur relevée est identique à `last_percent`, on met quand même `last_reading_at` à jour (l'appareil a bien parlé) mais en un seul `UPDATE` groupé pour toutes les piles, pas un par pile. 14 `UPDATE` toutes les 15 minutes dans une base à écrivain unique, c'est 1 344 transactions par jour pour rien.
4. **`orphaned` n'est pas `tracked = 0`.** Une pile orpheline reste suivie : elle alimente `keep`, elle est comptée en attribut de `batteries_low`, et **sa tâche n'est jamais fermée**. Une migration d'intégration (ZHA → Z2M, le 2026-07-14) en frappe plusieurs d'un coup ; c'est le jour où fermer serait le plus faux.
5. **Un capteur de pile inconnu ne crée aucune ligne.** Le coordinateur ne déclare rien tout seul : il compte. La déclaration est un geste, au panneau ou par l'import.

- [x] **Step 1: Écrire les tests**

Créer `tests/test_coordinator_batteries.py`, sur le modèle de `tests/test_coordinator_foodday.py` :

```python
async def test_a_numeric_reading_is_written_to_the_database(hass, integration):
    _register_battery_sensor(hass, entity_id="sensor.velux_ch_batterie",
                             registry_id="uuid-1", state="18")
    battery_id = _declare(integration, label="Velux (CH)", registry_id="uuid-1")
    await _refresh(hass, integration)
    row = integration.manager.list_batteries()[0]
    assert row["last_percent"] == 18.0
    assert row["last_reading_at"] is not None


async def test_an_unavailable_state_writes_nothing(hass, integration):
    """La date doit dire « l'appareil a parlé », pas « on a regardé ». La
    confondre avec la seconde vide le seuil de 26 h de tout son sens."""
    _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                             registry_id="uuid-1", state="18")
    _declare(integration, label="X", registry_id="uuid-1")
    await _refresh(hass, integration)
    avant = integration.manager.list_batteries()[0]["last_reading_at"]
    hass.states.async_set("sensor.x_batterie", "unavailable")
    await _refresh(hass, integration)
    assert integration.manager.list_batteries()[0]["last_reading_at"] == avant


async def test_a_non_numeric_state_writes_nothing(hass, integration):
    for state in ("unknown", "faible", ""):
        ...  # même forme que ci-dessus


async def test_the_reading_survives_a_restart(hass, integration):
    """LE test de l'amélioration : `last_changed` repart au démarrage de HA,
    `last_reading_at` non. C'est ce qui autorise à remonter le seuil « Pile
    HS ? » de 1 h à 26 h sans re-créer le trou de 9 jours d'août."""
    _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                             registry_id="uuid-1", state="18")
    _declare(integration, label="X", registry_id="uuid-1")
    await _refresh(hass, integration)
    attendu = integration.manager.list_batteries()[0]["last_reading_at"]
    await _reload_integration(hass, integration)     # helper : décharge + recharge
    assert integration.manager.list_batteries()[0]["last_reading_at"] == attendu


async def test_renaming_the_entity_changes_nothing(hass, integration):
    """L'ancre est l'`id` du registre, un UUID que l'interface n'expose même
    pas. C'est tout l'intérêt du choix."""
    entry = _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                                     registry_id="uuid-1", state="18")
    _declare(integration, label="X", registry_id="uuid-1")
    _rename(hass, entry, "sensor.completement_autre_chose")
    hass.states.async_set("sensor.completement_autre_chose", "12")
    await _refresh(hass, integration)
    assert integration.manager.list_batteries()[0]["last_percent"] == 12.0


async def test_a_vanished_registry_entry_makes_the_battery_orphaned(hass, integration):
    _declare(integration, label="X", registry_id="uuid-disparu")
    await _refresh(hass, integration)
    ligne = hass.data_battery_rows(integration)[0]   # helper de lecture de coordinator.data
    assert ligne["orphaned"] is True
    assert ligne["entity_id"] is None


async def test_an_orphaned_battery_never_closes_its_task(hass, integration):
    _declare(integration, label="X", registry_id="uuid-disparu", tracked=True)
    await _refresh(hass, integration)
    plan = await _plan(hass, integration)
    assert plan["items"] == []
    assert "Pile à changer — X" in plan["keep"]


async def test_undeclared_sensors_are_counted_not_created(hass, integration):
    _register_battery_sensor(hass, entity_id="sensor.nouveau_batterie",
                             registry_id="uuid-neuf", state="12")
    await _refresh(hass, integration)
    assert integration.manager.list_batteries() == []
    assert _undeclared(integration) == ["sensor.nouveau_batterie"]


async def test_a_declared_but_undecided_battery_counts_as_undeclared(hass, integration):
    """`tracked = NULL` veut dire « découvert, pas décidé » : la pile est
    silencieuse dans todo.maintenance, mais visible dans le compteur. C'est
    exactement ce qui tient la règle « rien n'échoue silencieusement »."""
    _register_battery_sensor(hass, entity_id="sensor.x_batterie",
                             registry_id="uuid-1", state="12")
    _declare(integration, label="X", registry_id="uuid-1", tracked=None)
    await _refresh(hass, integration)
    assert _undeclared(integration) == ["sensor.x_batterie"]


async def test_the_device_name_comes_from_the_device_registry(hass, integration):
    """Le `device_id` porte le NOM VIVANT — c'est ce qui remplace la chaîne de
    replace() du macro, qui suivait la langue de l'intégration d'origine."""
    ...


async def test_a_refresh_without_any_battery_costs_no_write(hass, integration):
    """14 UPDATE toutes les 15 minutes dans une base à écrivain unique, c'est
    1 344 transactions par jour pour rien."""
    ...
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_coordinator_batteries.py -q`
Expected: FAIL — `ImportError: cannot import name 'resolve_battery_anchors'`

- [x] **Step 3: Écrire la résolution et les relevés**

Insérer la lecture dans `_async_update_data` **sans réécrire** ce qui y est déjà (le lot 3 y insère `"meals"`). Un seul travail d'exécuteur pour l'écriture groupée des relevés.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_coordinator_batteries.py -q`
Expected: PASS

- [x] **Step 5: La suite entière**

Run: `./scripts/test.sh -q`
Expected: PASS. Aucun test du lot 2 (coordinateur, journée de 4 h) ne doit avoir bougé.

---

## Task 10: Les trois capteurs, les noms français, et la rupture qui existe déjà

**Files:**
- Modify: `custom_components/home_stock/sensor.py`
- Modify: `custom_components/home_stock/translations/fr.json`
- Test: `tests/test_entities.py`

**Interfaces:**
- Produit, **en fin de `sensor.py`** :
  - `BatteriesLowSensor` → `sensor.home_stock_batteries_low`. Valeur : le nombre de piles suivies sous leur seuil. Attributs : `batteries` (liste de `{label, percent, verb, spare_label, spare_in_stock, entity_id}`, triée par niveau croissant), `orphaned` (le nombre), `mute` (le nombre).
  - `BatteriesUndeclaredSensor` → `sensor.home_stock_batteries_undeclared`. Valeur : le nombre de capteurs `device_class: battery` sans ligne `battery`, **plus** les lignes `tracked IS NULL`. Attributs : `entities` (les `entity_id`), `never_declared` / `undecided` (les deux nombres, séparés).
  - `WarrantyNextSensor` → `sensor.home_stock_warranty_next`. Valeur : le nombre de jours jusqu'à la prochaine fin de garantie, `None` s'il n'y en a aucune. Unité `d`, pas de `state_class`. Attributs : `warranties` (les échéances à venir, avec `name` et `warranty_ends_on`).
- Les trois sont **activés d'office** : chacun peut valoir zéro, et un zéro est une information.

**Décisions de plan :**

1. **Trois capteurs, pas quatorze.** Le lot 0 § 8 tient : le détail d'une pile demande un formulaire, donc le panneau.
2. **Aucune entité `event` nouvelle, aucun blueprint.** L'annonce existe déjà et fonctionne : la réconciliation horaire pousse les nouvelles tâches vers Bleuenn par `personas_home.send_event`. Un second canal annoncerait deux fois la même pile faible, et CLAUDE.md est explicite : « Bleuenn n'annonce que les nouvelles tâches. Ne pas rajouter de rappel périodique. »
3. **Aucun `binary_sensor.home_stock_spares_missing`.** Une rechange sous son `min_quantity` est un produit sous son seuil : elle remonte dans `binary_sensor.home_stock_shortages` **sans une ligne de code**. Deux entités pour la même donnée, sur la même tablette, sous deux noms, c'est exactement la « donnée en double » que les contraintes du foyer interdisent. Un test le prouve.

- [x] **Step 1: Écrire les tests**

Dans `tests/test_entities.py`, **en fin de fichier** :

```python
async def test_the_three_sensors_exist_and_are_enabled(hass, integration):
    for entity_id in ("sensor.home_stock_batteries_low",
                      "sensor.home_stock_batteries_undeclared",
                      "sensor.home_stock_warranty_next"):
        assert hass.states.get(entity_id) is not None


async def test_batteries_low_publishes_the_list_lowest_first(hass, integration):
    ...
    state = hass.states.get("sensor.home_stock_batteries_low")
    assert state.state == "2"
    assert [b["label"] for b in state.attributes["batteries"]] == ["B", "A"]
    assert state.attributes["batteries"][0]["verb"] == "Pile à changer"


async def test_batteries_low_says_whether_the_spare_is_there(hass, integration):
    """« 12 %, aucune en stock » est la phrase qui change ce qu'on fait le soir
    même. Elle doit être une donnée, pas une reconstruction dans une carte."""
    ...
    assert state.attributes["batteries"][0]["spare_label"] == "CR2032"
    assert state.attributes["batteries"][0]["spare_in_stock"] == 0.0


async def test_batteries_low_counts_the_orphans_separately(hass, integration):
    ...
    assert state.attributes["orphaned"] == 1


async def test_a_zero_is_a_state_not_an_unavailable(hass, integration):
    """Aucune pile faible se dit « 0 ». `unknown` ferait croire à une panne."""
    state = hass.states.get("sensor.home_stock_batteries_low")
    assert state.state == "0"


async def test_undeclared_counts_a_brand_new_battery_sensor(hass, integration):
    ...
    assert hass.states.get("sensor.home_stock_batteries_undeclared").state == "1"


async def test_undeclared_separates_never_seen_from_undecided(hass, integration):
    ...
    assert state.attributes["never_declared"] == 1
    assert state.attributes["undecided"] == 1


async def test_warranty_next_is_none_when_there_is_nothing_to_watch(hass, integration):
    assert hass.states.get("sensor.home_stock_warranty_next").state in ("unknown", "None")


async def test_warranty_next_counts_days_and_lists_the_deadlines(hass, integration):
    ...


async def test_a_non_edible_spare_shows_up_in_shortages(hass, integration):
    """La rupture existe déjà : c'est pour ça qu'aucun capteur de rechange
    manquante n'est créé. Ce test est ce qui rend cette absence défendable —
    sans lui, « ça marche déjà » est une supposition."""
    product_id = _seed_spare(integration, name="CR2032", quantity=0, min_quantity=2)
    await _refresh(hass, integration)
    state = hass.states.get("binary_sensor.home_stock_shortages")
    assert state.state == "on"
    assert "CR2032" in state.attributes["products"]


async def test_the_three_sensors_are_named_in_french(hass, integration):
    for entity_id, nom in (
        ("sensor.home_stock_batteries_low", "Piles faibles"),
        ("sensor.home_stock_batteries_undeclared", "Piles à déclarer"),
        ("sensor.home_stock_warranty_next", "Prochaine fin de garantie"),
    ):
        assert hass.states.get(entity_id).attributes["friendly_name"].endswith(nom)
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_entities.py -q`
Expected: FAIL — les trois entités n'existent pas.

- [x] **Step 3: Écrire les trois capteurs et les traductions**

Classes en fin de `sensor.py`, instances **en fin** de la liste passée à `async_add_entities`. Dans `translations/fr.json`, à l'intérieur de `entity.sensor`, **après** les clés existantes :

```json
"batteries_low": { "name": "Piles faibles" },
"batteries_undeclared": { "name": "Piles à déclarer" },
"warranty_next": { "name": "Prochaine fin de garantie" }
```

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_entities.py -q`
Expected: PASS

---

## Task 11: Les trois services, dont `maintenance_plan`

**Files:**
- Modify: `custom_components/home_stock/services.py`
- Modify: `custom_components/home_stock/services.yaml`
- Test: `tests/test_services_batteries.py` (nouveau)

**Interfaces:**
- Produit trois services :

| Service | Réponse | Champs |
|---|---|---|
| `home_stock.maintenance_plan` | `ONLY` | `extra_items?` (liste), `extra_keep?` (liste) → `{items, keep, complete}` |
| `home_stock.record_battery_event` | non | `battery_id`, `kind`, `occurred_at?`, `consume_spare?`, `note?`, `idempotency_key?` |
| `home_stock.import_grocy_equipment` | `ONLY` | `database_path`, `apply?` (défaut `false`) → le rapport (tâche 13) |

**Décisions de plan :**

1. **`maintenance_plan` valide ses entrées comme n'importe quelle écriture**, mais **ne refuse jamais un item qu'il ne comprend pas** : il le recopie. La validation porte sur la **forme du conteneur** (`extra_items` doit être une liste, `extra_keep` aussi), pas sur le contenu de chaque item. Un service qui refuserait un item malformé ferait disparaître la tâche du purificateur au premier changement de macro.
2. **`maintenance_plan` ne lève pas quand la base tousse** : elle rend `complete: false`. La seule chose qui la fait lever, c'est un argument de mauvaise **forme** — parce que ça, c'est le raccord qui est cassé, et le raccord doit alors désarmer la fermeture, ce que `continue_on_error: true` + `stock` non défini font déjà.
3. **`record_battery_event` accepte une `idempotency_key`** comme toute écriture, et son `occurred_at` passe par `iso_date` sur la partie date.

- [x] **Step 1: Écrire les tests**

Créer `tests/test_services_batteries.py`, sur le modèle de `tests/test_services.py` :

```python
async def test_maintenance_plan_called_bare_returns_the_batteries_alone(hass, integration):
    reponse = await hass.services.async_call(
        DOMAIN, "maintenance_plan", {}, blocking=True, return_response=True)
    assert set(reponse) == {"items", "keep", "complete"}
    assert reponse["complete"] is True


async def test_maintenance_plan_merges_the_macro_plan(hass, integration):
    reponse = await hass.services.async_call(
        DOMAIN, "maintenance_plan",
        {"extra_items": [{"summary": "Arroser Plante", "description": "18 %",
                          "entity": "sensor.plante_humidite"}],
         "extra_keep": ["Arroser Plante"]},
        blocking=True, return_response=True)
    assert [i["summary"] for i in reponse["items"]][0] == "Arroser Plante"


async def test_maintenance_plan_copies_what_it_does_not_understand(hass, integration):
    reponse = await hass.services.async_call(
        DOMAIN, "maintenance_plan",
        {"extra_items": [{"summary": "Vider la poubelle"}, {"forme": "inconnue"}],
         "extra_keep": ["Vider la poubelle"]},
        blocking=True, return_response=True)
    assert {"forme": "inconnue"} in reponse["items"]


async def test_maintenance_plan_refuses_a_container_that_is_not_a_list(hass, integration):
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "maintenance_plan", {"extra_items": "pas une liste"},
            blocking=True, return_response=True)


async def test_record_battery_event_refuses_a_charge_on_a_primary(hass, integration):
    """La règle du lot 2 : ce que le websocket refuse, le service le refuse.
    Le message est en français, parce qu'un service est aussi une réponse
    vocale."""
    battery_id = _declare(integration, label="X", kind="primary")
    with pytest.raises(HomeAssistantError, match="ne se recharge pas"):
        await hass.services.async_call(
            DOMAIN, "record_battery_event",
            {"battery_id": battery_id, "kind": "charge"}, blocking=True)


async def test_record_battery_event_refuses_an_unknown_kind(hass, integration):
    ...


async def test_record_battery_event_is_idempotent(hass, integration):
    ...


async def test_import_grocy_equipment_is_a_dry_run_by_default(hass, integration):
    reponse = await hass.services.async_call(
        DOMAIN, "import_grocy_equipment", {"database_path": str(COPIE)},
        blocking=True, return_response=True)
    assert reponse["applied"] is False
    assert integration.manager.list_batteries() == []
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_services_batteries.py -q`
Expected: FAIL — `ServiceNotFound`

- [x] **Step 3: Écrire les services et leur description**

Handlers en closures **en fin** de `async_register_services`, `async_register` **en fin** du bloc, schémas module-level **après** `RESYNC_SCHEMA`. Blocs `services.yaml` **en fin de fichier**, en français, avec des `selector` — et pour `maintenance_plan`, une description qui dit à quoi il sert et **qui l'appelle** (l'automation `maintenance_sync_taches`), parce que c'est un service que personne n'appellera jamais à la main.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_services_batteries.py -q`
Expected: PASS

---

## Task 12: Les onze commandes websocket, dans leur propre module

**Files:**
- Create: `custom_components/home_stock/websocket_batteries.py`
- Modify: `custom_components/home_stock/websocket_api.py` (deux lignes)
- Modify: `tests/test_offline_queue_contract.py`
- Test: `tests/test_websocket_batteries.py` (nouveau)

**Décision de plan — un module neuf, pas 400 lignes de plus dans `websocket_api.py`.** Ce fichier fait déjà 1 240 lignes et le lot 3 y ajoute quatorze commandes. Deux lots qui l'allongent en parallèle, c'est un conflit de fusion sur presque chaque hunk. Le lot 5 ajoute donc **exactement deux lignes** à `websocket_api.py` : l'import de `async_register_battery_commands` et son appel en fin de `async_register_websocket`. Les helpers partagés (`_runtime`, `_read`, `_send_domain_error`, `_send_integrity_error`, `_validate_fields`, `_non_empty_text`, `_strict_boolean`) sont **importés** depuis `websocket_api`, jamais recopiés : deux copies d'un traducteur d'erreur, c'est deux vocabulaires au bout de six mois.

**Interfaces — les onze commandes :**

| Commande | Effet |
|---|---|
| `home_stock/batteries/list` | Les piles déclarées : relevé, verbe, seuils, rechange et son stock, état de l'ancre |
| `home_stock/batteries/discover` | Les capteurs `device_class: battery` sans ligne `battery`. **N'écrit rien** |
| `home_stock/battery/declare` | Déclaration ; accepte `tracked: false` + `exclusion_reason` (le bouton « ignorer ») |
| `home_stock/battery/update` | Correction : libellé, nature, seuils, rechange, note, suivi |
| `home_stock/battery/event` | Recharge ou remplacement |
| `home_stock/equipment/list` · `get` · `create` · `update` | Fiche d'équipement |
| `home_stock/equipment/consumable/link` · `unlink` | Rattache un produit à un équipement |

- [x] **Step 1: Écrire les tests, dont le test croisé des deux surfaces**

Créer `tests/test_websocket_batteries.py`, sur le modèle de `tests/test_websocket_write.py` :

```python
async def test_discover_writes_nothing(hass, ws_client, integration):
    """Une commande qui s'appelle « découvrir » ne doit rien créer : sinon le
    seul fait d'ouvrir l'écran Piles peuplerait la base de 28 lignes."""
    _register_battery_sensor(hass, entity_id="sensor.x_batterie", registry_id="u1")
    reponse = await _appel(ws_client, {"type": "home_stock/batteries/discover"})
    assert reponse["success"] and len(reponse["result"]["sensors"]) == 1
    assert integration.manager.list_batteries() == []


async def test_declare_then_list_round_trips(hass, ws_client, integration):
    ...


async def test_ignoring_a_battery_without_a_reason_is_refused(hass, ws_client):
    """Le bouton « ignorer » du panneau : la colonne exige un motif, donc le
    panneau doit en demander un, donc le serveur doit refuser sans."""
    reponse = await _appel(ws_client, {"type": "home_stock/battery/declare",
                                       "label": "Tablette", "kind": "primary",
                                       "tracked": False})
    assert not reponse["success"]
    assert "motif" in reponse["error"]["message"]


@pytest.mark.parametrize("charge,attendu", [
    ({"kind": "built_in", "product_id": 1}, "batterie intégrée"),
    ({"kind": "primary", "low_percent": 20, "keep_percent": 10}, "seuil de maintien"),
    ({"kind": "primary", "cell_count": 0}, None),
    ({"kind": "nimh"}, None),
    ({"kind": "primary", "low_percent": 120}, None),
    ({"kind": "primary", "installed_on": "02/05/2024"}, None),
])
async def test_neither_surface_is_weaker_than_the_other(hass, ws_client, integration,
                                                        charge, attendu):
    """Le contrôle croisé du lot 2, appliqué à chaque contrainte du § 12.2 :
    la même charge doit être refusée PAR LES DEUX. Un `parametrize` plutôt que
    deux fichiers, parce que c'est la divergence qu'on cherche à empêcher, pas
    la couverture."""
    reponse = await _appel(ws_client, {"type": "home_stock/battery/declare",
                                       "label": "X", **charge})
    assert not reponse["success"]
    with pytest.raises((HomeAssistantError, vol.Invalid)):
        await hass.services.async_call(DOMAIN, "record_battery_event", ...)  # équivalent service


async def test_every_write_command_accepts_an_idempotency_key(hass, ws_client):
    """Le contrat du lot 1. `tests/test_offline_queue_contract.py` le fait
    respecter tout seul en DÉCOUVRANT les types dans les sources TypeScript —
    ce test-ci est sa version explicite, pour que l'échec dise laquelle."""
    for type_ in ("home_stock/battery/declare", "home_stock/battery/update",
                  "home_stock/battery/event", "home_stock/equipment/create",
                  "home_stock/equipment/update",
                  "home_stock/equipment/consumable/link",
                  "home_stock/equipment/consumable/unlink"):
        ...


async def test_an_event_replayed_from_the_queue_decrements_once(hass, ws_client, integration):
    ...


async def test_equipment_get_carries_its_consumables_and_its_batteries(hass, ws_client):
    ...


async def test_a_manual_path_under_www_is_refused(hass, ws_client):
    ...


async def test_commands_answer_not_loaded_when_the_entry_is_gone(hass, ws_client):
    """Le comportement du lot 1 pour toutes les commandes : `_send_not_loaded`,
    pas une exception. C'est aussi ce qui fait que le panneau met en file au
    lieu de perdre l'écriture."""
    ...
```

Puis, dans `tests/test_offline_queue_contract.py`, ajouter les sept types d'écriture **en fin** de `EXPECTED_QUEUED_COMMAND_TYPES`.

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_websocket_batteries.py tests/test_offline_queue_contract.py -q`
Expected: FAIL — `unknown_command`

- [x] **Step 3: Écrire `websocket_batteries.py`**

Onze commandes, chacune décorée `@websocket_api.websocket_command` + `@websocket_api.async_response`, toutes les écritures passant par `check_battery_fields` / `check_battery_event`. Puis les **deux** lignes dans `websocket_api.py`.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_websocket_batteries.py tests/test_offline_queue_contract.py -q`
Expected: PASS

- [x] **Step 5: La suite entière**

Run: `./scripts/test.sh -q`
Expected: PASS.

---

## Task 13: L'import Grocy, le libellé semé, et le contrôle « 0 écart de résumés »

**Files:**
- Create: `custom_components/home_stock/import_grocy_equipment.py`
- Create: `tests/fixtures/grocy/equipment.sql`
- Test: `tests/test_import_grocy_equipment.py` (nouveau)

**Interfaces:**
- Produit :
  - `EquipmentImportReport` — `products`, `batteries`, `equipment`, `discovered`, `pre_excluded`, `skipped`, `anomalies: list[str]`, `summary_diff: list[str]`, `ok: bool`, `as_dict()`. Même forme que `ImportReport` du lot 0.
  - `import_grocy_equipment(db, grocy_path, *, hass_states, registry_rows, apply: bool = False) -> EquipmentImportReport`.

**Ce que l'import fait, dans l'ordre :**

1. **18 lignes de rechange → 5 produits.** Regroupées par format (LADDA AAA, 9 V, CR2032, C/LR14, AA), chacune devient un `product` `edible = 0`, `base_unit = 'piece'`, rayon « Entretien et maison » (créé au lot 1), avec son article générique (lot 0 § 6.3) et un `batch` de 4, 5, 3, 4 et 2 unités, **sans prix**. `min_quantity` proposé à 2.
2. **5 lignes avec `entity_id` → 5 lignes `battery`.** Format lu dans la description (`1x CR2032`, `2x AAA rechargeable`), `cell_count` lu dans le `Nx`, `kind` déduit de la présence du mot « rechargeable ».
3. **3 lignes d'appareils retirés → rapportées, non importées.** Leurs descriptions le disent (« appareil retiré, plus aucune entité HA, vérifié 2026-07-31 ») ; les importer créerait trois piles orphelines dès le premier jour.
4. **34 lignes `equipment` → 34 lignes.** `name` et `note` repris, `device_id` **laissé vide**. Rien n'est deviné : ni date d'achat, ni garantie, ni notice (elles n'existent pas dans Grocy), et **aucun appariement automatique du nom vers le `device_registry`** — trois appareils s'appellent « Télévision » dans ce registre.
5. **Balayage du registre.** Chaque `sensor` `device_class: battery` sans ligne obtient `tracked = NULL` ; les 14 que le macro écarte aujourd'hui sont **proposées** en `tracked = 0` avec leur motif en clair. C'est la seule information que le macro possède et qu'il faut sauver avant de le raccourcir.

**Décision de plan n°1 — le libellé semé est celui rendu AUJOURD'HUI, pas le libellé correct.** L'import applique **une fois**, à la déclaration, la chaîne de `replace()` du macro (`'Batterie '`, `' Batterie'`, `' Battery level'`, `trim`) sur le nom de l'entité, et le motif `rideau|lock` pour choisir entre `built_in` et `primary`. C'est contre-intuitif — tout le lot 5 existe pour retirer cette heuristique — et c'est exactement ce qui rend le déploiement neutre : la première synchronisation après bascule produit **les mêmes résumés au caractère près**, donc n'ouvre ni ne ferme rien. Corriger un libellé ensuite est une **décision**, avec sa churn d'une tâche, prise en connaissance de cause depuis l'écran Piles. L'heuristique est utilisée **une fois puis jamais** ; elle vit dans ce fichier d'import et nulle part ailleurs.

**Décision de plan n°2 — le lot 5 ne tranche pas le piège des deux tags BLE.** L'inventaire de CLAUDE.md dit que la clé de la e208 est un MiTag ; le registre d'appareils dit « Sac » pour le MiTag. Aucune donnée du système ne tranche. L'import sème les deux libellés tels que le macro les rend aujourd'hui, les rapporte tous les deux dans `anomalies` avec leur `entity_id`, leur `device_id`, leur nom d'appareil et leur modèle, et l'écran Piles les montre côte à côte. Trancher à la place du propriétaire, sur la foi d'un nom, serait reproduire l'erreur qu'on est en train de retirer.

**Décision de plan n°3 — le contrôle de sortie est obligatoire, et il en a un de plus que la spec.** L'import n'est réputé réussi que si le rapport contient : 0 pile sans libellé ; 0 pile `tracked = 1` sans `kind` ; 0 pile `built_in` avec un `product_id` ; 0 `entity_registry_id` en double ; 0 `keep_percent < low_percent` ; **0 écart entre les résumés que produirait le nouveau plan et ceux qu'aurait produits le bloc 3 sur le même état** ; et **0 pile importée dont l'ancre ne résout aucune entité** (une ancre morte le jour de l'import est une faute de saisie, pas un orphelin légitime).

- [x] **Step 1: Fabriquer la fixture, une fois**

Depuis une **copie** de `grocy.db` (jamais celle en production), extraire les tables `batteries` et `equipment` vers `tests/fixtures/grocy/equipment.sql`. Anonymiser ce qui n'a rien à faire dans un dépôt. Cette lecture se fait **une fois** ; les tests ne lisent plus jamais Grocy ensuite.

```bash
cp /chemin/vers/grocy.db /tmp/grocy-copie.db
sqlite3 /tmp/grocy-copie.db ".dump batteries" ".dump equipment" \
  > tests/fixtures/grocy/equipment.sql
```

- [x] **Step 2: Écrire les tests**

Créer `tests/test_import_grocy_equipment.py`, sur le modèle de `tests/test_import_grocy.py` :

```python
def test_a_dry_run_writes_nothing_but_reports_everything(manager, grocy):
    rapport = import_grocy_equipment(manager.db, grocy, hass_states=ETATS,
                                     registry_rows=REGISTRE, apply=False)
    assert rapport.batteries == 5 and rapport.products == 5 and rapport.equipment == 34
    assert manager.list_batteries() == []


def test_the_eighteen_spare_cells_become_five_products(manager, grocy):
    """18 lignes Grocy pour 18 cellules, c'est un inventaire par objet. Ce
    qu'on veut savoir, c'est « combien de CR2032 au placard »."""
    _import(manager, grocy, apply=True)
    noms = sorted(p["name"] for p in manager.list_products() if not p["edible"])
    assert len(noms) == 5
    assert _stock_of_named(manager, "CR2032") == 3.0


def test_the_spares_are_not_edible_and_have_no_nutrition(manager, grocy):
    ...


def test_the_three_removed_devices_are_reported_not_imported(manager, grocy):
    """Les importer créerait trois piles orphelines dès le premier jour."""
    rapport = _import(manager, grocy, apply=True)
    assert rapport.skipped == 3
    assert any("appareil retiré" in a for a in rapport.anomalies)
    assert len(manager.list_batteries()) == 5 + len(REGISTRE_SANS_LIGNE)


def test_the_cell_count_is_read_from_the_description(manager, grocy):
    _import(manager, grocy, apply=True)
    pile = _battery_named(manager, "Interrupteur cuisine")
    assert pile["cell_count"] == 2 and pile["spare_label"] == "AAA"


def test_rechargeable_in_the_description_gives_the_right_kind(manager, grocy):
    ...


def test_running_it_twice_changes_nothing(manager, grocy):
    """`external_ref` garde l'id Grocy des deux côtés : le rejeu est sûr, et le
    lot 7 devient une jointure au lieu d'un appariement de noms — qui a créé
    35 doublons en avril 2026."""
    _import(manager, grocy, apply=True)
    avant = _snapshot(manager)
    _import(manager, grocy, apply=True)
    assert _snapshot(manager) == avant


def test_the_sweep_declares_nothing_it_was_not_asked_to(manager, grocy):
    """Un capteur inconnu devient `tracked = NULL` : compté, listé, SILENCIEUX
    dans todo.maintenance. Pas une tâche approximative de plus."""
    _import(manager, grocy, apply=True)
    inconnues = [b for b in manager.list_batteries() if b["tracked"] is None]
    assert inconnues and all(b["exclusion_reason"] is None for b in inconnues)


def test_the_fourteen_exclusions_are_saved_before_the_macro_is_shortened(manager, grocy):
    """La seule information que le macro possède et qu'on perdrait en le
    raccourcissant : QUI est exclu, et POURQUOI."""
    _import(manager, grocy, apply=True)
    exclues = [b for b in manager.list_batteries() if b["tracked"] is False]
    assert len(exclues) == 14
    assert all(b["exclusion_reason"] for b in exclues)
    motifs = {b["label"]: b["exclusion_reason"] for b in exclues}
    assert "secteur" in motifs["Tablette Salon"]


def test_the_two_e208_batteries_are_excluded_but_not_the_key_tag(manager, grocy):
    """CLAUDE.md avertit qu'un motif `peugeot|e208` écarterait aussi le tag BLE
    du trousseau, qui est une CR2032 légitimement suivie. Sans motif,
    l'avertissement n'a plus d'objet : deux lignes disent 0, une troisième 1,
    et aucune ne dépend de l'orthographe d'une autre."""
    _import(manager, grocy, apply=True)
    assert _battery_for(manager, "sensor.peugeot_e208_batterie_niveau")["tracked"] is False
    assert _battery_for(manager, "sensor.cle_de_la_peugeot_e208_batterie_ble")["tracked"] is None


def test_the_two_swapped_ble_tags_are_reported_and_not_arbitrated(manager, grocy):
    rapport = _import(manager, grocy, apply=True)
    assert sum("BLE" in a for a in rapport.anomalies) == 2
    # Le lot 5 ne renomme rien : il rend la question posable une fois pour toutes.


def test_the_seeded_label_is_the_one_the_macro_renders_today(manager, grocy):
    """Contre-intuitif et volontaire : c'est ce qui rend la bascule neutre.
    « Batterie Velux (CH) » devient « Velux (CH) », exactement comme la chaîne
    de replace() du macro le fait aujourd'hui."""
    _import(manager, grocy, apply=True)
    assert _battery_for(manager, "sensor.velux_ch_batterie")["label"] == "Velux (CH)"


def test_the_seeded_kind_reproduces_todays_verb(manager, grocy):
    _import(manager, grocy, apply=True)
    assert _battery_for(manager, "sensor.rideau_cuisine_batterie")["kind"] == "built_in"
    assert _battery_for(manager, "sensor.serrure_batterie")["kind"] == "built_in"
    assert _battery_for(manager, "sensor.velux_ch_batterie")["kind"] == "primary"


def test_the_report_proves_zero_summary_drift(manager, grocy):
    """LE contrôle qui garantit le déploiement neutre. S'il n'est pas vide, la
    bascule fermerait des tâches et en rouvrirait d'autres, et Bleuenn
    annoncerait la maison entière."""
    rapport = _import(manager, grocy, apply=True)
    assert rapport.summary_diff == []
    assert rapport.ok is True


def test_the_report_refuses_a_dead_anchor(manager, grocy):
    """Une ancre qui ne résout rien LE JOUR de l'import est une faute de
    saisie, pas un orphelin légitime."""
    rapport = import_grocy_equipment(manager.db, grocy, hass_states=ETATS,
                                     registry_rows=[], apply=False)
    assert rapport.ok is False
    assert any("ancre" in a for a in rapport.anomalies)


def test_the_report_refuses_a_keep_below_a_low(manager, grocy):
    ...
```

- [x] **Step 3: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_import_grocy_equipment.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [x] **Step 4: Écrire l'import**

Comme `import_grocy.py` : la simulation **parcourt tout et rapporte tout**, seules les écritures sont sautées. C'est le point d'un `apply: false` — prouver les mêmes anomalies qu'un vrai passage.

- [x] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_import_grocy_equipment.py -q`
Expected: PASS

---

## Task 14: `docs/raccord/maintenance.jinja` — le bloc 3 retiré, prouvé sans dégât

**Files:**
- Create: `docs/raccord/maintenance.jinja`
- Create: `docs/raccord/README.md`
- Create: `tests/fixtures/maintenance/etats.json`
- Create: `tests/fixtures/maintenance/avant.jinja`
- Test: `tests/test_raccord_maintenance.py` (nouveau)

**Le diff attendu, écrit ici et jamais appliqué :**

- **Supprimé — la totalité du bloc 3 « Piles », lignes 57 à 110** de `config/custom_templates/maintenance.jinja`, en-tête de commentaire compris, ainsi que les variables `piles_exclues` et `motifs_exclus`. Le macro perd 54 lignes et **ne parcourt plus `states.sensor`**.
- **Inchangé —** les blocs 1 (consommables aspirateurs), 2 (filtres air et eau), 4 (plantes) et 5 (mises à jour manuelles), avec leurs seuils, leur hystérésis et leurs branches « capteur muet ». Le contrat de sortie ne change pas : `{"items": [...], "keep": [...]}`, chaque item portant `summary`, `description` et `entity`.
- **Ajouté — rien.** Le macro ne connaît pas `home_stock` ; c'est l'automation qui appelle le service (tâche 15). Un macro Jinja ne peut pas appeler un service, et lui faire lire un attribut d'entité aurait ramené la donnée dans le `recorder` pour rien.
- **La regex du bloc 5 n'est pas touchée** — `firmware|micrologiciel|system_apt|docker_homeassistant` reste — mais elle est désormais **verrouillée** par un test (Step 4), qui la compare à celle de l'automation. CLAUDE.md rappelle que les deux copies doivent rester identiques, sinon une mise à jour est soit installée d'office, soit réclamée à vie ; c'est gratuit puisqu'on écrit déjà ces fichiers, et ça ferme une dette ouverte depuis le 2026-07-31.

**La méthode de test, et sa contrainte.** On teste un fichier qui vit dans `/opt/nivuus/HomeAssistant/config/` depuis un dépôt qui n'a le droit ni d'y écrire, ni de redémarrer quoi que ce soit. Le test **écrit la copie de référence dans `hass.config.path('custom_templates/')`** — un répertoire temporaire d'un Home Assistant de test, jamais celui de la maison — puis peuple `hass` depuis une fixture versionnée et rend le macro par `homeassistant.helpers.template.Template`.

- [x] **Step 1: Capturer les fixtures, une fois**

Depuis `ha_sync/entities/sensor.json` (lecture seule), extraire les 28 capteurs de pile, les capteurs de filtre, les plantes et les entités `update`, vers `tests/fixtures/maintenance/etats.json` — `entity_id`, `state`, `attributes` utiles, `last_changed`. Copier l'actuel `config/custom_templates/maintenance.jinja` vers `tests/fixtures/maintenance/avant.jinja`, **sans le modifier**.

- [x] **Step 2: Écrire les tests**

Créer `tests/test_raccord_maintenance.py` :

```python
"""Le raccord, testé sans jamais toucher l'instance vivante.

Les copies de référence sont dans le dépôt ; le test les monte dans un Home
Assistant DE TEST, dont `config/` est un répertoire temporaire. Rien d'autre
n'est autorisé : pas de `docker compose`, pas de rechargement, pas de lecture
de jeton, aucune écriture dans le `config/` de la maison.
"""

async def test_the_new_macro_still_returns_items_and_keep(hass):
    rendu = await _rendre(hass, RACCORD)
    plan = json.loads(rendu)
    assert set(plan) == {"items", "keep"}
    assert all({"summary", "description", "entity"} <= set(i) for i in plan["items"])


async def test_the_word_grocy_has_disappeared(hass):
    """Le livrable vérifiable du lot, littéralement."""
    assert "grocy" not in RACCORD.read_text().lower()


async def test_the_battery_block_is_gone(hass):
    texte = RACCORD.read_text()
    for disparu in ("piles_exclues", "motifs_exclus", "device_class", "states.sensor",
                    "Pile à changer", "Pile HS ?", "Battery level"):
        assert disparu not in texte, disparu


async def test_the_new_macro_is_fifty_four_lines_shorter(hass):
    avant = len(AVANT.read_text().splitlines())
    apres = len(RACCORD.read_text().splitlines())
    assert avant - apres == 54


async def test_blocks_one_two_four_and_five_are_untouched(hass):
    """Ce test est la seule preuve que la suppression n'a rien emporté
    d'autre : on rend l'AVANT et l'APRÈS sur les mêmes états, et on vérifie
    que la différence est exactement l'ensemble des tâches de pile."""
    avant = json.loads(await _rendre(hass, AVANT))
    apres = json.loads(await _rendre(hass, RACCORD))
    partis = {i["summary"] for i in avant["items"]} - {i["summary"] for i in apres["items"]}
    assert all(p.startswith(("Pile à changer — ", "Recharger — ", "Pile HS ? — "))
               for p in partis)
    assert {i["summary"] for i in apres["items"]} <= {i["summary"] for i in avant["items"]}
    # et rien n'a changé de description côté aspirateurs, filtres et plantes
    assert _hors_piles(avant) == _hors_piles(apres)


async def test_the_new_macro_never_walks_states_sensor(hass):
    """Le macro parcourait 28 capteurs à chaque appel. Il n'en parcourt plus
    aucun — les seuils des blocs 1, 2 et 4 nomment leurs entités."""
    ...


async def test_the_manual_update_regex_is_identical_in_both_reference_files(hass):
    """Dette ouverte depuis le 2026-07-31 : la regex est dupliquée dans le
    macro et dans l'automation « Système - Mises à jour automatiques ». Les
    deux doivent rester identiques, sinon une MAJ est soit installée d'office,
    soit réclamée à vie dans la liste."""
    assert _extraire_regex(RACCORD) == _extraire_regex(SYNC_YAML) != ""


async def test_the_render_is_valid_json_on_the_real_snapshot(hass):
    """Un macro qui rend du JSON invalide fait échouer la variable `plan` de
    l'automation, donc toute la réconciliation, en silence côté tablettes."""
    _peupler(hass, ETATS)
    json.loads(await _rendre(hass, RACCORD))
```

- [x] **Step 3: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_raccord_maintenance.py -q`
Expected: FAIL — `FileNotFoundError: docs/raccord/maintenance.jinja`

- [x] **Step 4: Écrire la copie de référence et son mode d'emploi**

Copier `tests/fixtures/maintenance/avant.jinja` vers `docs/raccord/maintenance.jinja`, **retirer les lignes 57 à 110**, rien d'autre. Écrire `docs/raccord/README.md` : ce que sont ces fichiers, pourquoi ils ne sont pas installés, et la procédure à la main dans l'ordre (sauvegarder, poser, `homeassistant.reload_custom_templates`, rendre le macro dans Outils de développement → Modèle, comparer, puis seulement ensuite l'automation).

- [x] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_raccord_maintenance.py -q`
Expected: PASS

- [x] **Step 6: Vérifier qu'aucune écriture n'a fui**

```bash
git -C /opt/nivuus/HomeAssistant/config status --porcelain custom_templates/ automations.yaml
```
Expected: **vide**. Si ce n'est pas vide, la tâche a violé la contrainte la plus importante du plan.

---

## Task 15: `peut_fermer` — le drapeau qui empêche de refermer 14 tâches

**Files:**
- Create: `docs/raccord/maintenance_sync.yaml`
- Create: `tests/fixtures/maintenance/automation_avant.yaml`
- Test: `tests/test_raccord_sync.py` (nouveau)

**Le risque, en une phrase.** Il n'existe pas aujourd'hui : Grocy arrêté ne coûte qu'un suffixe. Demain, `home_stock` absent ferait disparaître les items de pile de `items` **et** de `keep` — `a_fermer` les contiendrait toutes, et **une seule synchronisation à 5 h 05 refermerait les 14 tâches de pile de la maison**, chacune se rouvrant à la synchro suivante avec une annonce de Bleuenn. C'est le risque n°1 du lot, et il a sa tâche.

**Le diff attendu sur l'automation `maintenance_sync_taches` :**

- **Supprimé —** l'action `todo.get_items` sur `todo.grocy_batteries` avec son `continue_on_error` et son `response_variable: grocy` ; et la totalité du template `voulu`, qui cherchait l'`entity_id` d'un item dans les descriptions Grocy pour en dériver un suffixe par `g.description.split(' - ')[0]`.
- **Ajouté —** à la place :

```yaml
    - action: home_stock.maintenance_plan
      continue_on_error: true
      data:
        extra_items: "{{ plan['items'] }}"
        extra_keep: "{{ plan['keep'] }}"
      response_variable: stock
    - variables:
        # Service injoignable (intégration déchargée, HA qui démarre) ou plan
        # incomplet (base illisible) : on retombe sur le plan du macro seul, et
        # on DÉSARME la fermeture. Quand le plan est incomplet, on a le droit
        # d'ajouter et de rafraîchir, JAMAIS de fermer — c'est la règle « on ne
        # ferme une tâche que sur une mesure qui prouve que la condition a
        # disparu », appliquée au plan entier.
        fusionne: "{{ stock | default(none, true) }}"
        voulu: "{{ fusionne.items if fusionne else plan['items'] }}"
        garde: "{{ fusionne.keep if fusionne else plan['keep'] }}"
        peut_fermer: "{{ fusionne is not none and fusionne.get('complete', false) }}"
```

- **Modifié —** `a_fermer` lit `garde` au lieu de `plan['keep']`, et la boucle de fermeture (`repeat` + `todo.remove_completed_items`) est enveloppée dans un `if` sur `peut_fermer`.
- **Inchangé —** le déclencheur (`time_pattern` minutes `"5"` + `homeassistant: start`), la lecture de `todo.maintenance`, les boucles d'ajout et de rafraîchissement, et l'annonce à Bleuenn sur `a_ajouter | count > 0`.

**Décision de plan — `peut_fermer` regarde `complete`, pas seulement la présence de la réponse.** La spec proposait `fusionne is not none`. C'est insuffisant : l'intégration peut être chargée et répondre alors que sa base est illisible (verrou WAL, disque plein). `maintenance_plan` rend alors `complete: false` (tâche 6), et le drapeau doit le voir. Le `get('complete', false)` par défaut **désarme** aussi le jour où une vieille version du service ne rend pas la clé — le défaut d'un garde-fou doit être « prudent », jamais « permissif ».

- [x] **Step 1: Capturer l'automation actuelle, une fois**

Extraire de `config/automations.yaml` (lecture seule) le bloc `- id: maintenance_sync_taches` en entier vers `tests/fixtures/maintenance/automation_avant.yaml`, **sans le modifier**.

- [x] **Step 2: Écrire les tests**

Créer `tests/test_raccord_sync.py` :

```python
async def test_the_new_automation_is_valid_yaml_and_keeps_its_id(hass):
    bloc = yaml.safe_load(SYNC_YAML.read_text())
    assert bloc[0]["id"] == "maintenance_sync_taches"
    assert bloc[0]["mode"] == "single"


async def test_grocy_is_gone_from_the_automation(hass):
    assert "grocy" not in SYNC_YAML.read_text().lower()


async def test_the_trigger_and_the_announcement_are_untouched(hass):
    """Les tablettes ne doivent demander aucune modification : c'est un
    OBJECTIF du raccord, pas un heureux hasard. `todo.maintenance` reste
    l'entité, son compte reste le compte, et `pieces.ts` ne bouge pas."""
    avant, apres = yaml.safe_load(AVANT_YAML.read_text()), yaml.safe_load(SYNC_YAML.read_text())
    assert avant[0]["triggers"] == apres[0]["triggers"]
    assert _annonce(avant) == _annonce(apres)


async def test_a_reachable_and_complete_plan_arms_the_closing(hass, integration):
    """Le cas nominal : le service répond, `complete` est vrai, on ferme ce qui
    doit être fermé."""
    resultat = await _executer(hass, SYNC_YAML, service_repond=PLAN_COMPLET)
    assert resultat["peut_fermer"] is True
    assert resultat["a_fermer"] == ["Pile à changer — Ancienne"]


async def test_an_unreachable_service_closes_nothing_at_all(hass):
    """LE test du lot. Sans lui, une indisponibilité de home_stock refermerait
    les 14 tâches de pile en une synchronisation, à 5 h 05, sans que personne
    ne le voie avant le lendemain."""
    resultat = await _executer(hass, SYNC_YAML, service_repond=None)
    assert resultat["peut_fermer"] is False
    assert resultat["a_fermer"] == []
    assert _appels_de_fermeture(hass) == []


async def test_an_incomplete_plan_closes_nothing_either(hass):
    """L'intégration répond mais sa base est illisible : `complete: false`.
    `fusionne is not none` ne suffit pas — c'est pourquoi le drapeau regarde
    `complete`."""
    resultat = await _executer(hass, SYNC_YAML,
                              service_repond={"items": [], "keep": [], "complete": False})
    assert resultat["peut_fermer"] is False
    assert _appels_de_fermeture(hass) == []


async def test_a_response_without_the_complete_key_disarms(hass):
    """Le défaut d'un garde-fou doit être « prudent », jamais « permissif »."""
    resultat = await _executer(hass, SYNC_YAML, service_repond={"items": [], "keep": []})
    assert resultat["peut_fermer"] is False


async def test_a_disarmed_run_still_adds_and_refreshes(hass):
    """« Quand le plan est incomplet, on a le droit d'ajouter et de rafraîchir,
    jamais de fermer. » Désarmer la fermeture ne doit pas geler la liste."""
    resultat = await _executer(hass, SYNC_YAML, service_repond=None,
                               plan_macro=PLAN_AVEC_UNE_NOUVELLE_TACHE)
    assert resultat["a_ajouter"] != []
    assert resultat["a_fermer"] == []


async def test_the_mute_component_never_removes_completed_items(hass):
    """`todo.remove_completed_items` purge la liste : le laisser tourner sur
    une liste qu'on vient de cocher à tort effacerait les 14 tâches pour de
    bon. Il est DANS le `if`, pas après."""
    await _executer(hass, SYNC_YAML, service_repond=None)
    assert "remove_completed_items" not in _services_appeles(hass)


async def test_the_full_chain_on_the_real_snapshot_is_neutral(hass, integration):
    """Déploiement neutre, bout en bout : sur les états de la fixture, et avec
    les 14 piles importées, l'ensemble des `summary` du plan fusionné est ÉGAL
    à celui du macro d'AVANT. C'est le test qui empêche les 14 tâches de se
    fermer et de se rouvrir le jour du basculement."""
    _peupler(hass, ETATS)
    _importer_les_piles(integration)
    avant = {i["summary"] for i in json.loads(await _rendre(hass, AVANT))["items"]}
    apres = await _executer(hass, SYNC_YAML, service_reel=True)
    assert {i["summary"] for i in apres["voulu"]} == avant
    assert set(apres["garde"]) == set(json.loads(await _rendre(hass, AVANT))["keep"])
    assert apres["a_ajouter"] == [] and apres["a_fermer"] == []
```

- [x] **Step 3: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_raccord_sync.py -q`
Expected: FAIL — `FileNotFoundError: docs/raccord/maintenance_sync.yaml`

- [x] **Step 4: Écrire la copie de référence de l'automation**

Partir de `tests/fixtures/maintenance/automation_avant.yaml`, appliquer **exactement** le diff décrit plus haut, et compléter `docs/raccord/README.md` avec l'ordre d'application : le `.jinja` **d'abord** (le macro sans bloc 3 reste correct même avec l'ancienne automation — il produit juste moins de tâches), l'automation **ensuite**. L'inverse laisserait une fenêtre où l'automation appelle un service en doublon du bloc 3.

- [x] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_raccord_sync.py -q`
Expected: PASS

- [x] **Step 6: Vérifier, encore, qu'aucune écriture n'a fui**

```bash
git -C /opt/nivuus/HomeAssistant/config status --porcelain custom_templates/ automations.yaml
```
Expected: **vide**.

---

## Task 16: L'écran « Piles »

**Files:**
- Create: `frontend/src/ecrans/piles.ts`
- Create: `frontend/tests/piles.test.ts`

**Interfaces:**
- Consomme : `Connexion.appeler(type, charge)` (la méthode s'appelle bien `appeler`, pas `envoyer`) ; `FileAttente` pour **toute** écriture ; `formaterNombre` de `../nombres`.
- Produit : l'élément `<home-stock-piles>`, propriétés `connexion` et `file`.

**Ce que l'écran montre :**

1. **Les piles suivies, triées par niveau croissant** : libellé, pourcentage, verbe, format de rechange et son stock. Une pile muette et une pile orpheline apparaissent dans la liste, avec leur état dit en clair, jamais un `0 %` inventé.
2. **Un appui ouvre la fiche** : seuils, nature, rechange, historique des événements, et le bouton « je viens de la changer » / « … de la recharger » **selon `kind`**.
3. **En tête, quand il y en a, le bloc « à déclarer »** : libellé proposé (le nom de l'appareil), modèle, `entity_id`, et deux boutons « suivre » / « ignorer ». Ignorer **demande un motif**, puisque la colonne l'exige.

**Décisions de plan :**

1. **« Je viens de la changer » est destructif** (il écrit un mouvement et décrémente le placard) : **deux appuis**, armement puis confirmation, par le geste de `cochage.ts` de l'app tablette — ici réimplémenté localement, le panneau n'en dépend pas.
2. **Le refus de stock est visible, pas avalé.** Quand `spare_refused` revient rempli, la fiche affiche la phrase française du serveur sous le bouton, et l'événement reste marqué comme enregistré. Perdre ce refus, c'est laisser croire qu'il reste une CR2032.
3. **Aucune couleur ne porte seule l'information.** Un niveau bas se lit au chiffre et au mot, pas à la teinte : contraste ≥ 4,5:1 vérifié, et le vérificateur ne mesure pas la sémantique.
4. **Le bloc « à déclarer » ne se remplit jamais tout seul.** Il liste ce que `home_stock/batteries/discover` rend, sans écrire ; c'est le bouton qui déclare.

- [x] **Step 1: Écrire les tests**

Créer `frontend/tests/piles.test.ts`, sur le modèle de `frontend/tests/journal.test.ts` :

```ts
it('trie les piles par niveau croissant', async () => { ... });
it('affiche les trois verbes selon la nature', async () => { ... });
it('dit « aucune en stock » quand la rechange manque', async () => { ... });
it('dit « jamais relevée » plutôt que 0 %', async () => { ... });
it('montre une pile orpheline sans inventer de niveau', async () => { ... });
it('liste le bloc « à déclarer » en tête quand discover rend des capteurs', async () => { ... });
it('n’écrit rien à l’ouverture de l’écran', async () => { ... });
it('refuse d’ignorer une pile sans motif', async () => { ... });
it('ignore une pile avec son motif, par la file d’attente', async () => { ... });
it('demande deux appuis avant « je viens de la changer »', async () => { ... });
it('n’écrit rien au premier appui', async () => { ... });
it('propose « recharger » et non « changer » sur une batterie intégrée', async () => { ... });
it('affiche le refus de stock renvoyé par le serveur', async () => { ... });
it('passe toutes les écritures par la file, jamais par appeler()', async () => { ... });
it('affiche l’historique des événements de la fiche, plus récent d’abord', async () => { ... });
```

Le dernier test de la liste est celui qui compte le plus : il monte l'écran avec une `Connexion` dont `appeler` est un espion, et vérifie qu'**aucune** des sept commandes d'écriture n'y passe — elles doivent toutes traverser `FileAttente`, sinon une écriture faite dans un couloir sans Wi-Fi est perdue.

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test -- piles`
Expected: FAIL — élément inconnu.

- [x] **Step 3: Écrire l'écran**

Identifiants et commentaires **en français**, comme le reste du front.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test -- piles`
Expected: PASS

- [x] **Step 5: La suite front**

Run (depuis `frontend/`) : `npm test`
Expected: PASS, ≥ 247 tests. **Pas de `npm run build`.**

---

## Task 17: L'écran « Équipements » et la navigation

**Files:**
- Create: `frontend/src/ecrans/equipements.ts`
- Create: `frontend/tests/equipements.test.ts`
- Modify: `frontend/src/panneau.ts`
- Test: `frontend/tests/panneau.test.ts`

**Ce que l'écran montre :** la liste par emplacement ; la fiche porte marque, modèle, numéro de série, date d'achat, garantie **avec les jours restants**, lien vers la notice, et les consommables rattachés avec leur usure et leur stock.

**Décisions de plan :**

1. **Trois états de garantie, trois phrases distinctes** : à venir (« garantie jusqu'au 15/03/2026 — 133 jours »), expirée (« garantie terminée depuis le … »), absente (« garantie non renseignée »). Jamais une case vide : une case vide se lit « bug ».
2. **Une notice introuvable est signalée, pas masquée.** Le lien reste, avec la mention « fichier introuvable » ; et rien ne devient indisponible pour autant.
3. **Aucun bouton de téléversement**, nulle part. Déposer un fichier dans `media/` est une copie faite une ou deux fois par an ; le § 4.3 de la spec mesure que 0 des 34 équipements Grocy a une notice alors que la colonne existait.
4. **`Ecran` gagne `'piles'` et `'equipements'` en fin d'union**, et le garde-fou du lot 1 (quitter le rangement avec des lignes en attente demande une confirmation) s'applique à ces cibles **comme aux autres** — c'est `demanderNavigation` qui le porte, donc c'est gratuit, et c'est un test qui le prouve plutôt qu'un raisonnement.

- [x] **Step 1: Écrire les tests**

`frontend/tests/equipements.test.ts` :

```ts
it('groupe les équipements par emplacement', async () => { ... });
it('affiche une garantie à venir avec ses jours restants', async () => { ... });
it('dit qu’une garantie est terminée plutôt que de la masquer', async () => { ... });
it('dit « garantie non renseignée » plutôt que de laisser vide', async () => { ... });
it('signale une notice introuvable sans casser la fiche', async () => { ... });
it('n’offre aucun bouton de téléversement', async () => { ... });
it('affiche un consommable avec son usure et son stock', async () => { ... });
it('dit « aucun en stock » pour un consommable en rupture', async () => { ... });
it('délie un consommable en deux appuis', async () => { ... });
it('affiche les piles rattachées à l’équipement', async () => { ... });
```

Puis, dans `frontend/tests/panneau.test.ts`, **en fin de fichier** :

```ts
it('expose les deux nouveaux écrans dans la navigation', async () => { ... });
it('demande confirmation avant de quitter le rangement vers Piles', async () => { ... });
it('demande confirmation avant de quitter le rangement vers Équipements', async () => { ... });
it('ne change pas de hauteur en passant sur les nouveaux écrans', async () => { ... });
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test -- equipements panneau`
Expected: FAIL

- [x] **Step 3: Écrire l'écran et brancher la navigation**

Dans `panneau.ts` : `import './ecrans/piles'` et `import './ecrans/equipements'` **en fin** de la liste d'imports ; `'piles' | 'equipements'` **en fin** de l'union `Ecran` ; deux branches dans `rendreEcran()` **avant** le `return` du scanner ; deux boutons **en fin** de la barre de navigation.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test`
Expected: PASS.

---

## Task 18: Vérification de rendu, documentation, et construction du bundle

**Files:**
- Modify: `frontend/outils/verifier-rendu.mjs`
- Modify: `docs/exploitation.md`
- Modify: `custom_components/home_stock/panel/home-stock-panel.js` (produit par le build)

**C'est la seule tâche autorisée à construire.** `custom_components/home_stock/` est bind-monté dans le conteneur : `npm run build` **est** un déploiement. Toutes les tâches précédentes se sont arrêtées à `npm test` et au vérificateur en mémoire.

- [x] **Step 1: Ajouter les deux scénarios de rendu**

En fin du tableau `SCENARIOS` de `frontend/outils/verifier-rendu.mjs`, avec `ecranAttendu` renseigné — un scénario qui n'atteint jamais son écran passe au vert sans rien avoir mesuré, et le vérificateur sait déjà le dire :

```js
{
  nom: 'Piles (quatorze suivies, trois à déclarer, une orpheline)',
  fixture: { /* 14 piles, dont une muette et une orpheline, + 3 découvertes */ },
  actions: [ /* navigation vers Piles, puis ouverture d'une fiche */ ],
  ecranAttendu: 'home-stock-piles',
},
{
  nom: 'Équipements (fiche chargée : garantie, notice, trois consommables)',
  fixture: { /* 34 équipements sur 4 emplacements, une fiche ouverte */ },
  actions: [ /* navigation vers Équipements, puis ouverture d'une fiche */ ],
  ecranAttendu: 'home-stock-equipements',
},
```

Les fixtures doivent être **les pires cas réels** : un libellé long (« Interrupteur salle de bain »), un stock à zéro, une garantie expirée, une notice introuvable. Un écran qui ne déborde que sur les cas faciles n'a pas été vérifié.

- [x] **Step 2: Lancer le vérificateur, en mémoire**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs`
Expected: tous les scénarios verts, aux **deux** formats (412 × 915 et 1280 × 800). Aucun débordement, aucune cible < 48 px, aucun contraste < 4,5:1, aucun texte tronqué, aucun écran manquant. **Ne jamais désactiver un contrôle pour faire passer un écran.**

- [x] **Step 3: Documenter dans `docs/exploitation.md`**

Une section `## Lot 5 — équipements, piles et consommables`, **à la fin du fichier**, sans retoucher les précédentes. Elle doit contenir, dans cet ordre :

1. **La procédure d'import**, en deux temps : `home_stock.import_grocy_equipment` avec `apply: false` d'abord, lecture du rapport, **vérification que `summary_diff` est vide** et que `ok` est vrai, puis `apply: true`. Le rapport est le seul contrôle avant une bascule irréversible côté tâches.
2. **L'application du raccord, à la main**, dans l'ordre : sauvegarder `custom_templates/maintenance.jinja` et le bloc `maintenance_sync_taches` ; poser `docs/raccord/maintenance.jinja` ; `homeassistant.reload_custom_templates` ; rendre le macro dans Outils de développement → Modèle et comparer les `summary` à ceux d'avant ; **seulement ensuite** remplacer le bloc d'automation ; recharger les automations ; vérifier `repairs/list_issues` à 0.
3. **Ce qu'il faut regarder l'heure suivante** : `todo.maintenance` doit avoir **exactement le même nombre de tâches** qu'avant, et Bleuenn ne doit **rien** annoncer. Une annonce à la première synchro est le signal que le déploiement n'a pas été neutre — le retour arrière est de reposer les deux fichiers sauvegardés, l'intégration n'ayant rien écrit dans `config/`.
4. **Ce que le lot 5 ne change pas côté tablettes** : `todo.maintenance` reste l'entité, son compte reste le compte, `tools/wallpanel-app/src/pieces.ts` **ne bouge pas**, aucun déploiement de `wallpanel-app` n'est nécessaire. C'était un objectif du raccord, pas un heureux hasard.
5. **Les trois capteurs** et ce que portent leurs attributs, plus la carte `entities` à ajouter à `config/lovelace_garde_manger.yaml` — **livrée en texte dans la doc**, comme le reste : le lot 5 n'écrit pas dans `config/`.

- [x] **Step 4: Construire le bundle**

Run (depuis `frontend/`) : `npm run build`

Puis vérifier ce qui a été écrit :

```bash
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain custom_components/home_stock/panel/
```

Un seul fichier doit avoir changé.

- [x] **Step 5: Vérifier le bundle réellement en place**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs --deploye`
Expected: mêmes scénarios verts, cette fois sur le bundle construit.

- [x] **Step 6: Les deux suites, une dernière fois**

```bash
./scripts/test.sh -q
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert, Python ≥ 623 tests et front ≥ 247.

- [x] **Step 7: Vérifier une dernière fois que la maison n'a pas été touchée**

```bash
git -C /opt/nivuus/HomeAssistant/config status --porcelain
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'homeassistant|grocy'
```
Expected: aucune modification dans `config/` imputable à ce lot, et les conteneurs avec le **même uptime** qu'au début — aucun redémarrage.

- [x] **Step 8: Commit**

```bash
git add frontend/outils/verifier-rendu.mjs docs/exploitation.md \
        custom_components/home_stock/panel/home-stock-panel.js
git commit -m "chore: render checks for the battery and equipment screens, docs, and the built panel"
```

---

## Ce que ce plan ne fait pas

Rappel, pour qu'aucune tâche n'aille les chercher :

- **Appliquer le raccord.** `docs/raccord/maintenance.jinja` et `maintenance_sync.yaml` sont **livrés et testés**, jamais installés. Poser les deux fichiers dans `/opt/nivuus/HomeAssistant/config/`, recharger les modèles et les automations, et contrôler la première synchronisation restent les gestes du propriétaire. L'intégration livre, elle n'installe pas.
- **Trancher le piège des deux tags BLE.** L'inventaire dit MiTag, le registre dit « Sac ». Aucune donnée du système ne tranche ; le lot 5 rend la question **posable une fois pour toutes** depuis l'écran Piles, et s'arrête là.
- **Les 6 *chores* Grocy** (litière, fontaine, croquettes, poubelles). Ce sont des tâches **périodiques**, pas conditionnelles, et `todo.maintenance` est piloté par des conditions. C'est un **trou de la feuille de route du lot 0**, pas un choix : à poser au lot 7, avant l'extinction de Grocy. Soit elles meurent avec lui, soit elles deviennent une `local_todo` et une automation horaire.
- **Une identité par cellule physique**, ni compteur de cycles par pile. Grocy l'a modélisé et `battery_charge_cycles` contient **0 ligne** après six mois. Les événements par place suffisent.
- **Le téléversement d'une notice ou d'un ticket** depuis le panneau. 0 des 34 équipements Grocy a une notice alors que la colonne existait.
- **Déduire le format d'une pile depuis le modèle de l'appareil.** Aucune source fiable ; une devinette produirait une liste de courses fausse.
- **Rattacher automatiquement un équipement à un `device_registry`** par son nom. Trois appareils s'appellent « Télévision » dans ce registre.
- **Déplacer les seuils des blocs 1, 2 et 4** de `maintenance.jinja` vers `home_stock`. Frontière de responsabilité : `home_stock` sait ce qu'il y a dans le placard, pas comment va l'aspirateur. Le lot n'apporte à ces blocs qu'**une** chose — la réponse à « en as-tu une d'avance ? ».
- **Amortissement, valeur résiduelle, assurance.** Aucun usage identifié dans le foyer.
- **Toucher aux tablettes murales et au vocal** — lot 6. La ligne de synthèse ne bouge pas ; « Il me reste des CR2032 ? » se répondra par `home_stock.query_stock`, qui existe depuis le lot 0 et fonctionne sur un produit de rechange sans une ligne de plus.
- **La reprise du stock alimentaire et l'arrêt de Grocy** — lot 7.
- **Modifier les blocs 1, 2, 4 et 5 de `maintenance.jinja`** autrement que par l'enrichissement de leurs descriptions.
- **Déployer.** Redémarrer Home Assistant, lancer l'import et appliquer le raccord restent le geste du propriétaire.


---

## Écarts au plan, constatés à l'exécution

Le plan n'est pas sacré ; la suite de tests l'est. Ce qui suit a été corrigé
au contact du code, et chaque correction est justifiée dans le message du
commit qui la porte.

1. **Tâche 1 — test de contiguïté relâché.** Le lot 3 prend `m004` dans un
   worktree parallèle : ici les `VERSION` valent `[1, 2, 3, 5]` et la forme
   stricte ne peut pas passer. Le test vérifie unicité, croissance stricte,
   première version à 1 et `CURRENT_VERSION == max`, et porte en commentaire
   la forme stricte à rétablir **au merge du lot 3**. `m005` n'a pas été
   renuméroté.
2. **Tâche 11 — `import_grocy_equipment` déplacé en tâche 13.** Le plan
   enregistrait et testait ce service deux tâches avant que son module et sa
   fixture Grocy n'existent.
3. **Tâches 12, 16, 17 — `EXPECTED_QUEUED_COMMAND_TYPES` déplacé.** Le
   contrat hors-ligne compare cet ensemble à ce que le scanner TROUVE dans
   les sources TypeScript : l'inscrire à la tâche 12 rendait toute la suite
   rouge jusqu'à la tâche 17. Les trois types rejoignent la liste avec les
   écrans qui les appellent.
4. **Tâche 14 — capture de l'automation avancée.** Le test de regex dupliquée
   comparait le macro à un fichier que la tâche 15 crée. La copie témoin de
   « Système - Mises à jour automatiques » (celle qui porte réellement la
   regex, et non `maintenance_sync_taches`) est capturée en tâche 14.
5. **Tâche 15 — `continue_on_error` ne suffisait pas.** Mesuré : Home
   Assistant traite « service introuvable » comme une faute de configuration
   et interrompt le script, `continue_on_error` ou non. La réconciliation
   entière s'arrêtait donc dès que `home_stock` était déchargé — sans rien
   fermer, mais sans plus rien ajouter ni rafraîchir. L'appel est gardé par
   l'état de `sensor.home_stock_batteries_low`.
6. **Tâche 16 — `FileAttente` gagne une promesse `reponse`.** La file ne
   rendait que le sort de l'action et jetait la réponse du serveur, donc
   `spare_refused` ne pouvait pas remonter au panneau. Ajout purement
   additif.
7. **Tâche 16 — une douzième commande websocket**, `home_stock/battery/events`
   (lecture seule) : la fiche d'une pile montre son historique, et aucune des
   onze ne savait le rendre.
8. **Tâches 14, 15, 18 — contrôle « rien n'a fui ».** `/opt/nivuus/HomeAssistant/config`
   n'est pas un dépôt git : le `git status` prévu par le plan n'imprimait
   qu'une erreur fatale. Remplacé par une comparaison md5 contre une
   empreinte prise avant la tâche 1.
9. **Correctif hors périmètre, assumé** : `tests/conftest.py` ne drainait pas
   le rafraîchissement débouncé de `setup_entry`, ce qui rendait
   `tests/test_event_expiration.py` rouge environ une fois sur cinq, sur un
   test différent à chaque fois. Sans ce correctif, aucune des dix-huit
   portes « la suite complète est verte » n'était fiable.
