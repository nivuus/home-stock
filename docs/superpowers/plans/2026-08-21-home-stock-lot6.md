# home_stock — Lot 6 : les quatre surfaces — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire sortir `home_stock` de son panneau. Trois surfaces s'ajoutent à celle qui existe : la tablette murale de la cuisine, sept phrases dites à Bleuenn, et le panneau qui cesse d'être étroit au-delà de 1000 px. Aucune fonction métier nouvelle — **le lot porte des fonctions existantes là où la maison les regarde vraiment.**

**Architecture:** Deux dépôts. Côté `meal`, le composant ne gagne qu'un attribut (`meal_id` sur `sensor.home_stock_next_meal`) et un champ de service optionnel (`slot_key` sur `query_meals`) ; le front du panneau apprend une mise en page large sur sept écrans sur dix-sept ; le vocal est **livré, jamais installé**, comme les blueprints des lots 2 et 2bis. Côté `tools/wallpanel-app`, c'est une **migration** : la tablette a déjà une surface garde-manger, câblée sur Grocy — le lot change sa source, pas sa forme. Le bloc central `repas` et le mode `recette` sont **resourcés**, pas recréés ; `src/grocy.ts` disparaît. Zéro pixel ajouté au cadre de 343 × 585 px.

**Tech Stack:** Python 3.13 / Home Assistant 2026.8.2 / SQLite (WAL, écrivain unique) / `pytest-homeassistant-custom-component` — TypeScript / `lit` / rollup / vitest / playwright-core (deux fois : `meal/frontend` et `wallpanel-app`).

**Spec:** `docs/superpowers/specs/2026-08-21-home-stock-lot6-design.md`

## Global Constraints

Ces règles lient **toutes** les tâches. Elles sont recopiées de la spec et de `CLAUDE.md`.

### Les deux dépôts

- **`meal`** : `/opt/nivuus/HomeAssistant/data/meal`, son `.git`, ses 1877 tests Python et ses 499 tests front.
- **`wallpanel-app`** : `/opt/nivuus/HomeAssistant/data/tools/wallpanel-app`, **son propre `.git`**, son `package.json`, ses **40 fichiers `tests/*.test.ts`** (le `README.md` en annonce 33 : chiffre périmé, rafraîchi par ce lot) et son propre vérificateur de rendu.
- **Deux commits, deux dépôts, deux historiques.** Rien ne les lie. Chaque tâche dit **dans quel dépôt** elle se déroule ; toutes ses commandes se lancent depuis la racine de ce dépôt-là (pour `wallpanel-app`, **jamais** depuis la racine de `data/`).
- La partie `meal` est **rétro-compatible à chaque étape** : un attribut ajouté et un champ de service optionnel ne dérangent pas le bundle de tablette actuellement déployé, qui ne les lit simplement pas.

### Les deux constructions, et rien d'autre qui touche la maison

- **`npm run build` depuis `meal/frontend` écrit dans `custom_components/home_stock/panel/`**, bind-monté dans le conteneur Home Assistant. Règle du lot 1, jamais assouplie : **une seule construction, dans la dernière tâche**, quand tout le reste est vert.
- **`npm run build` depuis `wallpanel-app` DÉPLOIE SUR LES TROIS TABLETTES DE LA MAISON.** Il écrit dans `config/www/wallpanel/` et incrémente le `?v=` des trois pages. Il n'y a **aucune étape de validation entre ce build et les écrans**, et la tablette de la cuisine sert d'horloge 24 h sur 24. Il est lancé **une seule fois, dans l'avant-dernière tâche**, et cette tâche ne fait que ça.
- **Un plan qui place ce build ailleurs qu'en avant-dernière position est un plan à refuser** (spec § 14.4). Jamais « pour voir ». Jamais deux fois.
- **Les vérificateurs ne déploient pas** : `node outils/verifier-rendu.mjs` des deux dépôts construit **en mémoire** depuis `src/`, et `mesurer-salve.mjs` / `mesurer-rendus.mjs` de `wallpanel-app` non plus. Tout ce qui peut être vérifié avant le build **doit** l'être avant le build.
- **`--deploye` est le seul mode qui lit le bundle en place** : il ne s'utilise **qu'après** un build, jamais à sa place.

### Rien d'autre ne touche l'instance vivante

- Aucun `docker compose`, aucun redémarrage de Home Assistant, aucun rechargement de l'intégration, aucun appel MCP d'écriture, aucune écriture dans `/opt/nivuus/HomeAssistant/config/` en dehors des deux constructions ci-dessus.
- **Grocy est en lecture seule jusqu'au lot 7** : ni le conteneur, ni ses données, ni `/local/grocy-scanner.html`, ni `/local/grocy-recipes.html`. Le lot 6 débranche les *surfaces*, pas les *données*.
- Le vérificateur de `wallpanel-app` ouvre les pages **contre l'instance Home Assistant réelle**, avec la session du navigateur. C'est une **lecture**, elle est déjà ce que fait cet outil aujourd'hui, et elle reste la seule autorisée. Aucune tâche ne lit le jeton de `.mcp.json` à la main.
- **Aucun test ne sort sur le réseau.** Ni Open Food Facts, ni Grocy, ni Home Assistant : tout se joue sur des doublures et sur les points d'injection déjà présents dans les deux vérificateurs.

### Nommage

- **Python** : code, schéma, identifiants, noms d'intents, listes et slots **en anglais** (`HomeStockQueryStock`, `{product}`, `slot_key`, `meal_id`). **Textes affichés et phrases en français.**
- **Le front de `meal` ET celui de `wallpanel-app` gardent leurs identifiants et leurs commentaires en français** (`rendreRepasSuivant`, `listesTachesExtra`, `garde-manger.ts`). Cette règle vaut aussi pour le code neuf : on n'introduit pas d'anglais dans deux bases écrites en français depuis le premier jour.

### Les contraintes de dalle (`wallpanel-app`) — obligatoires

- **Cadre 343 × 585 px, marge nulle.** La hauteur totale **ne bouge pas** selon qu'une alerte ou un média est actif : **on remplace un bloc, on n'en ajoute jamais un.**
- **Objectif chiffré du lot : zéro pixel ajouté.** Si `verifier-rendu.mjs` échoue, la réponse est de **retirer** quelque chose, jamais d'agrandir le cadre ni de relâcher un seuil.
- **Cibles tactiles ≥ 62 px**, **contraste texte/fond ≥ 5:1** — vérifiés automatiquement.
- **Aucun geste de navigation** : tout au bouton. **Pas d'appui long.** Une action destructive demande **deux appuis** (armement puis confirmation), et **un seul emplacement armé à la fois**.
- **Pas de donnée en double sur la MÊME tablette.** La répétition entre tablettes est permise (c'est ce qui autorise la ligne DLC au salon).
- **Jetons Material 3 Expressive** (`npm run jetons` → `src/styles/jetons.css`), **jamais de hex en dur** dans un composant.
- **Moteur des Fire = Chrome 100** : pas de `dvh`, pas de syntaxe CSS postérieure. jsdom (vitest) ne calcule **aucune** mise en page — seul `verifier-rendu.mjs` prouve que ça tient.

### Les contraintes du panneau (`meal/frontend`)

- Seuils **WCAG AA** : cible 48 px, contraste 4,5:1 — le panneau se tient en main ou se pilote à la souris ; ce sont **d'autres** seuils que ceux du mur, et ils ne se confondent jamais.
- **`large` est mesuré, jamais déduit** : `window.innerWidth >= 1000`, mis à jour sur `resize`. Aucune détection d'agent utilisateur.
- **Un écran qui n'a rien à gagner à la largeur ne change rien.** Une mise en page conditionnelle est une seconde mise en page à tester : dix écrans sur dix-sept restent inchangés, et c'est une décision, pas un oubli.
- Toute écriture du panneau passe par la **file hors-ligne** (`file-attente.ts`) et son `idempotency_key`. La vue dense n'ouvre **aucun** second chemin d'écriture.

### La validation, aux deux surfaces

- **Aucune des deux surfaces n'a le droit d'être la plus faible** : ce que le websocket refuse, le service le refuse, et réciproquement (`tests/test_surface_parity.py`).
- Le lot 6 introduit **une** asymétrie, et une seule : `slot_key` existe sur le service `query_meals` et **pas** sur `home_stock/meals/list`. Elle est **inscrite explicitement** dans `test_surface_parity.py` — un choix relu, pas un oubli découvert.

### Le vocal et les blueprints : livrés, jamais installés

- `custom_sentences/fr/home_stock.yaml` et `packages/home_stock_intents.yaml` sont **livrés dans le dépôt et jamais copiés par l'intégration**. `intent_script` est une clé de `configuration.yaml`, un fichier que le propriétaire tient à la main. **`home_stock` ne modifie jamais la configuration de la maison.**
- Même contrat pour `blueprints/automation/home_stock/courses_bleuenn.yaml`, comme `dlc_bleuenn.yaml` (lot 2) et `objectifs_bleuenn.yaml` (lot 2bis).

### Pièges du dépôt `meal`, à ne pas repayer

- **`Database._lock` n'est PAS réentrant** : deux `db.write()` imbriqués **figent le processus sans exception**. Réutiliser `_consume_within` / `_add_stock_within` de `application.py`, jamais un second `with self.db.write()`.
- **`SELECT b.*` est interdit dans tout `custom_components/`** — un test l'épingle par un scan **littéral**. N'aliaser aucune table en `b`.
- **`NULL` reste distinct de `0.0`**, et un état d'entité vide n'est jamais `0`.

### Commandes de test, par dépôt

| Dépôt | Commande | Depuis | État de référence |
|---|---|---|---|
| `meal` | `./scripts/test.sh` | racine du dépôt | **1877 tests**, vert |
| `meal` | `npm test` | `frontend/` | **499 tests**, vert |
| `meal` | `node outils/verifier-rendu.mjs` | `frontend/` | **47 exécutions**, vert |
| `wallpanel-app` | `npm test` | `tools/wallpanel-app/` | **40 fichiers**, vert |
| `wallpanel-app` | `node outils/verifier-rendu.mjs` | `tools/wallpanel-app/` | vert |

> **Le vérificateur du panneau compte des EXÉCUTIONS, pas des scénarios.** 47 = 22 scénarios × 2 formats + 3 scénarios sur bundle minifié. Passer à trois formats donne 22 × 3 + 3 = **69** sans qu'un seul scénario ait été écrit, et le scénario propre à la vue dense (lancé **en 1920 × 1080 seulement**) porte le total à **70**. Un lot qui laisse ce nombre à 47 n'a pas ajouté de format.

---

## Structure des fichiers

### `meal` — Python

**Créés**

| Fichier | Responsabilité |
|---|---|
| `custom_sentences/fr/home_stock.yaml` | Les sept phrases françaises et leurs listes de slots. Livré, jamais copié par l'intégration. |
| `packages/home_stock_intents.yaml` | Les sept blocs `intent_script` : l'appel de service et sa mise en phrase. À coller dans `configuration.yaml` ou à charger en paquet. Livré, jamais installé. |
| `blueprints/automation/home_stock/courses_bleuenn.yaml` | Le rappel de la liste de courses à heure fixe, groupé par rayon. Livré, jamais installé. |
| `tests/test_voice_package.py` | Le contrat de forme des deux fichiers vocaux et du blueprint : YAML valide, intents appariés, services et champs réellement déclarés dans `services.yaml`. |

**Modifiés**

| Fichier | Ce qui change |
|---|---|
| `sensor.py` | `NextMealSensor` publie l'attribut `meal_id` (`None` quand aucun repas, jamais `0`) |
| `services.py` | `QUERY_MEALS_SCHEMA` gagne `vol.Optional("slot_key"): vol.In(MEAL_SLOT_KEYS)` ; `query_meals` filtre |
| `services.yaml` | Le champ `slot_key` de `query_meals`, avec son sélecteur et sa description française |
| `translations/fr.json` | Rien de neuf à nommer ; relu pour que `next_meal` reste juste |
| `const.py` | Aucune constante nouvelle attendue — `MEAL_SLOT_KEYS` existe déjà (ligne 82) |
| `docs/exploitation.md` | Section « Lot 6 — les quatre surfaces » : installation du vocal, ce que la tablette montre et ne montre pas, procédure de déploiement, retour arrière, amendements aux specs 0/4/5 |

### `meal` — Front du panneau

**Modifiés**

| Fichier | Ce qui change |
|---|---|
| `frontend/src/panneau.ts` | `large` propagé aux sept écrans adaptés ; `narrow` de l'hôte pris en compte |
| `frontend/src/ecrans/catalogue.ts` | Tableau à colonnes et édition en ligne au-delà de 1000 px |
| `frontend/src/ecrans/journal.ts` | Barres mensuelles et détail du jour **côte à côte** |
| `frontend/src/ecrans/liste.ts` | Rayons en colonnes plutôt qu'empilés |
| `frontend/src/ecrans/reglages.ts` | Rayons, emplacements et magasins en trois colonnes |
| `frontend/src/ecrans/ticket.ts` | Photo à gauche, lignes rapprochées à droite |
| `frontend/src/ecrans/equipements.ts`, `frontend/src/ecrans/piles.ts` | Tableau |
| `frontend/outils/verifier-rendu.mjs` | Troisième format 1920 × 1080 + un scénario dense exécuté dans ce seul format → **70 exécutions** |

**Inchangés, et c'est une décision** : `scanner`, `fiche`, `panier`, `rangement`, `session` (écrans de magasin, une main), `recettes`, `recette`, `validation`, `consommation` (vues debout), `planning` (déjà `large`).

### `wallpanel-app`

**Créés**

| Fichier | Responsabilité |
|---|---|
| `src/garde-manger.ts` | La lecture de `home_stock` **depuis les états d'entité** : repas suivant, étiquette, ouvrabilité, compte de DLC. **Pur** — aucun réseau, aucune horloge lue, `Etat` reçu en argument. Remplace `src/grocy.ts` en beaucoup plus petit. |
| `tests/garde-manger.test.ts` | Sa preuve, y compris l'entité `unavailable` et l'attribut absent. |

**Modifiés**

| Fichier | Ce qui change |
|---|---|
| `src/pieces.ts` | Ligne de synthèse DLC (cuisine + salon), `listesTachesExtra` → `todo.home_stock_shopping`, commandes « Courses » (+ `vue: '#taches'`) et « Recette », `extrasMaison` → `/home-stock`, champ `horsTaches` sur `EntreeSynthese` |
| `src/cochage.ts` | `LIBELLES_LISTE` connaît `todo.home_stock_shopping` et `todo.home_stock_expirations` ; `listesTachesPiece` honore `horsTaches` |
| `src/repas.ts` | Réduit à l'**étiquette** (« Dîner », « Demain midi ») ; le parcours du plan et les issues `ok`/`absente`/`muette` disparaissent avec Grocy |
| `src/recette.ts` | `decouperPages` conservé, alimenté aussi par les **étapes structurées** de `home_stock/recipe/get` |
| `src/rendu/defaut.ts` | `rendreRepasSuivant` alimenté par l'attribut d'un capteur ; gabarit `.mode-bloc` **inchangé** |
| `src/rendu/recette.ts` | Panneau d'ingrédients **en lecture seule** ; « Terminer » porte son libellé explicite |
| `src/demarrage.ts` | Plus aucun `chargerPlan`/`chargerRecette`/`chargerIngredients` Grocy, plus aucun `appelerService('grocy', …)` ; `recipe/get`, `meal/preview` et `meal/validate` par `envoyerCommande` |
| `src/rendu/maison.ts`, `src/rendu/corps.ts`, `src/geste.ts`, `src/interaction.ts`, `src/recette-en-cours.ts`, `src/styles/base.css` | Reliquats textuels « Grocy » dans les commentaires et les classes — nettoyés |
| `README.md` | Le nombre de fichiers de tests, et la disparition de Grocy |
| `outils/verifier-rendu.mjs` | Points d'injection renommés : le contrôle mesure le **pire cas** sans dépendre de l'état réel de l'installation |

**Supprimés**

| Fichier | Pourquoi |
|---|---|
| `src/grocy.ts` | Sa source est morte. 8,3 ko, deux bases d'URL selon le protocole, un chemin de panne à trois issues |
| `tests/grocy.test.ts` | Idem |

**Inchangé, et c'est la preuve du § 7.3 de la spec** : `src/connexion.ts` et `tests/connexion.test.ts`. `envoyerCommande` accepte déjà n'importe quel `type` websocket et apparie par `id`. **Le canal n'a pas eu besoin d'évoluer.**

---

## Task 1: `meal_id` sur le capteur du repas suivant

**Dépôt : `meal`.** Première tâche du lot, et l'ordre n'est pas négociable : le vérificateur de rendu de `wallpanel-app` ouvre les pages **contre l'instance réelle**. Si l'attribut n'existe pas côté composant, il mesure un écran vide et déclare que tout va bien.

**Files:**
- Modify: `custom_components/home_stock/sensor.py`
- Test: `tests/test_meal_sensors.py`, `tests/test_entities.py`

**Interfaces:**
- Consomme : `NextMealSensor._meal`, qui tient déjà le dictionnaire complet du repas (`repo.next_meal`).
- Produit : `sensor.home_stock_next_meal` publie désormais **cinq** attributs — `day`, `slot`, `recipe_id`, `missing_ingredients`, **`meal_id`**.

**Pourquoi cet attribut.** La tablette affiche le repas suivant, puis doit pouvoir le **valider** (`home_stock/meal/validate`, qui exige un `meal_id`). Sans lui, elle devrait rappeler `home_stock/meals/list` juste pour retrouver l'identifiant de ce qu'elle affiche déjà — un aller-retour pour une donnée qu'elle a sous les yeux. Le vocal a le même besoin. L'attribut est **déjà calculé** : c'est une ligne.

- [x] **Step 1: Écrire les tests**

Dans `tests/test_meal_sensors.py`, à la suite des tests existants du capteur. Lire d'abord le haut du fichier pour reprendre ses fixtures (planification d'un repas, rafraîchissement du coordinateur) plutôt que d'en écrire d'autres.

```python
async def test_next_meal_publishes_its_meal_id(hass, ...):
    """Ce que la tablette et le vocal ont besoin de savoir pour VALIDER ce
    qu'ils viennent d'annoncer, sans un second aller-retour."""
    meal_id = await _plan_a_dinner(hass, ...)          # helper déjà présent
    state = hass.states.get("sensor.home_stock_next_meal")
    assert state.attributes["meal_id"] == meal_id


async def test_next_meal_without_a_meal_has_a_none_meal_id(hass, ...):
    """`None`, JAMAIS `0`. Un zéro ici se lirait comme le repas numéro zéro,
    exactement l'argument qui a déjà fait choisir l'état vide plutôt que `0`
    pour le nom du plat."""
    state = hass.states.get("sensor.home_stock_next_meal")
    assert state.state in (None, "", "unknown")
    assert state.attributes["meal_id"] is None
    # La clé EXISTE quand même : un template qui teste `is not none` doit
    # pouvoir le faire sans que l'attribut apparaisse et disparaisse.
    assert "meal_id" in state.attributes


async def test_next_meal_keeps_its_four_older_attributes(hass, ...):
    """Garde-fou de non-régression : la tablette lira `day`, `slot` et
    `recipe_id` DANS LA MÊME lecture. Un renommage silencieux les casserait
    toutes les trois d'un coup."""
    await _plan_a_dinner(hass, ...)
    attrs = hass.states.get("sensor.home_stock_next_meal").attributes
    assert set(attrs) >= {"day", "slot", "recipe_id", "missing_ingredients", "meal_id"}
```

Dans `tests/test_entities.py`, deux tests de plus. Ils épinglent une propriété **aujourd'hui implicite** dont dépend toute la ligne de synthèse de la tablette (§ 8.3 de la spec) :

```python
async def test_the_two_todo_states_are_counts(hass, ...):
    """L'état d'une entité `todo` est le nombre d'éléments NON COCHÉS.

    `wallpanel-app` compte dessus : sa ligne de synthèse affiche
    « {etat} produit{s} à consommer », et un `binary_sensor` ne pourrait
    produire qu'un texte sans compte — or le compte est ce qu'on lit de loin.
    Rien ne garantissait cette forme jusqu'ici ; ce test la tient."""
    await _seed_two_expiring_batches(hass, ...)
    assert hass.states.get("todo.home_stock_expirations").state == "2"
    assert hass.states.get("todo.home_stock_shopping").state == "0"


async def test_a_ticked_shopping_line_leaves_the_count(hass, ...):
    """Cocher décrémente l'état — sinon la ligne de synthèse mentirait juste
    après le geste qui vient de la corriger."""
    ...
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_meal_sensors.py tests/test_entities.py -q`
Expected: FAIL — `KeyError: 'meal_id'`, puis l'échec des deux tests d'état `todo` s'ils ne décrivent pas la réalité (dans ce cas, **corriger le test, pas le composant** : la forme actuelle est celle dont la tablette dépend).

- [x] **Step 3: Publier l'attribut**

Dans `custom_components/home_stock/sensor.py`, `NextMealSensor.extra_state_attributes` — les deux branches, jamais une seule :

```python
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meal = self._meal
        if meal is None:
            return {"day": None, "slot": None, "recipe_id": None,
                    "missing_ingredients": 0, "meal_id": None}
        missing = (self.coordinator.data.get("meals") or {}).get("missing", [])
        return {
            "day": meal["day"],
            "slot": meal["slot_key"],
            "recipe_id": meal["recipe_id"],
            "missing_ingredients": len(missing),
            # Lot 6 : ce que la tablette et le vocal doivent VALIDER après
            # l'avoir annoncé. `None` et non `0` quand il n'y a pas de repas :
            # zéro est un identifiant possible dans un monde où les clés
            # commencent à 0, et cette entité n'a pas à laisser le doute.
            "meal_id": meal["id"],
        }
```

Vérifier le nom exact de la colonne rendue par `repo.next_meal` avant d'écrire `meal["id"]` — c'est le seul point de cette tâche qui peut se tromper en silence.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_meal_sensors.py tests/test_entities.py -q`
Expected: PASS

- [x] **Step 5: Vérifier que le test a des dents**

Remplacer `"meal_id": None` par `"meal_id": 0` dans la branche « aucun repas ». `test_next_meal_without_a_meal_has_a_none_meal_id` doit tomber. Remettre le code correct.

- [x] **Step 6: Suite complète**

Run: `./scripts/test.sh -q`
Expected: PASS — **1877 + 5 tests**, aucun échec.

- [x] **Step 7: Commit**

```bash
git add custom_components/home_stock/sensor.py tests/test_meal_sensors.py tests/test_entities.py
git commit -m "feat: next_meal publishes meal_id, and todo states are pinned as counts"
```

---

## Task 2: `slot_key` optionnel sur `query_meals`

**Dépôt : `meal`.** « Qu'est-ce qu'on mange **ce soir** ? » suppose de savoir quel créneau est « ce soir ». `MEAL_SLOT_KEYS` vit dans `const.py` (ligne 82) ; refaire ce filtre en Jinja dans un `intent_script` mettrait la même règle à deux endroits — exactement le défaut que `maintenance.jinja` a déjà payé avec sa regex dupliquée (cf. `CLAUDE.md`).

**Files:**
- Modify: `custom_components/home_stock/services.py`, `custom_components/home_stock/services.yaml`
- Test: `tests/test_services_meals.py`, `tests/test_surface_parity.py`

**Interfaces:**
- Consomme : `const.MEAL_SLOT_KEYS = ("breakfast", "lunch", "dinner", "snack")`, `manager.list_meals(start, end)`.
- Produit : `home_stock.query_meals` accepte `vol.Optional("slot_key"): vol.In(MEAL_SLOT_KEYS)`. Absent → comportement d'avant, à l'octet près.

**Le filtrage se fait dans le service, pas dans le dépôt.** `list_meals` rend déjà la plage ; filtrer une liste de quelques dizaines d'entrées en Python coûte moins qu'une variante de requête SQL, et surtout **n'ouvre pas une seconde façon de lire un planning**.

- [x] **Step 1: Écrire les tests**

Dans `tests/test_services_meals.py` :

```python
async def test_query_meals_without_slot_key_is_unchanged(hass, ...):
    """Le contrat d'avant le lot 6, tenu par un test : les six autres phrases
    vocales et le panneau appellent ce service SANS `slot_key`."""
    response = await _call_query_meals(hass, start="2026-08-21", end="2026-08-21")
    assert len(response["meals"]) == 3       # les trois repas planifiés du jour


async def test_query_meals_filters_on_a_slot(hass, ...):
    response = await _call_query_meals(hass, start="2026-08-21", end="2026-08-21",
                                       slot_key="dinner")
    assert [m["slot_key"] for m in response["meals"]] == ["dinner"]


async def test_query_meals_refuses_an_unknown_slot(hass, ...):
    """« goûter » n'est pas un créneau de ce modèle. Le refus vient de
    `vol.In(MEAL_SLOT_KEYS)`, la MÊME source que le websocket `meal/plan` —
    jamais d'une liste recopiée dans le service."""
    with pytest.raises(vol.Invalid):
        await _call_query_meals(hass, start="2026-08-21", end="2026-08-21",
                                slot_key="gouter")


async def test_query_meals_on_an_empty_slot_answers_an_empty_list(hass, ...):
    """PAS une erreur. « Rien n'est prévu ce soir » est une réponse, et
    l'intent doit pouvoir la mettre en phrase — le silence est une panne
    (spec § 9.2)."""
    response = await _call_query_meals(hass, start="2026-08-21", end="2026-08-21",
                                       slot_key="breakfast")
    assert response["meals"] == []


async def test_query_meals_keeps_the_range_when_a_slot_is_given(hass, ...):
    """Le filtre est un ET, pas un OU : trois jours × un créneau rendent trois
    repas au plus, un par jour. Se tromper ici rendrait « qu'est-ce qui est
    prévu demain midi ? » bavard de trois jours de dîners."""
    response = await _call_query_meals(hass, start="2026-08-21", end="2026-08-23",
                                       slot_key="dinner")
    assert {m["day"] for m in response["meals"]} == {"2026-08-21", "2026-08-22", "2026-08-23"}
    assert {m["slot_key"] for m in response["meals"]} == {"dinner"}
```

Dans `tests/test_surface_parity.py`, **l'asymétrie s'inscrit** — elle ne se découvre pas :

```python
# --- lot 6 : la SEULE asymétrie assumée du lot -----------------------------
#
# `slot_key` existe sur le service `query_meals` et PAS sur la commande
# websocket `home_stock/meals/list`. Ce n'est pas un oubli : `meals/list` rend
# la plage complète et le panneau la découpe lui-même, tandis que le filtrage
# par créneau est une commodité pour le VOCAL, qui n'a pas de tableau où
# chercher. Ajouter le filtre au websocket serait ajouter du code que personne
# n'exerce — et du code jamais exercé est du code faux qui s'ignore.
#
# Ce que la parité continue d'exiger : le REFUS d'une valeur hors
# `MEAL_SLOT_KEYS` doit être identique partout où ce champ existe, donc entre
# `query_meals` et `home_stock/meal/plan`, qui le porte depuis le lot 3.

async def test_slot_key_asymmetry_is_a_documented_choice(hass, ...):
    """`meals/list` n'a pas de `slot_key`, et l'accepterait-il en silence que
    ce test tomberait — un champ ignoré est pire qu'un champ refusé."""
    verdict = await _websocket_verdict(
        hass, client, 1, "home_stock/meals/list",
        {"start": "2026-08-21", "end": "2026-08-21", "slot_key": "dinner"})
    assert verdict == "refusé"        # `websocket_command` refuse les clés inconnues


async def test_the_slot_vocabulary_is_the_same_on_both_surfaces(hass, ...):
    """`query_meals` et `home_stock/meal/plan` refusent le même mot."""
    ...
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_services_meals.py tests/test_surface_parity.py -q`
Expected: FAIL — `vol.Invalid: extra keys not allowed @ data['slot_key']`

- [x] **Step 3: Écrire le schéma et le filtre**

Dans `services.py` :

```python
QUERY_MEALS_SCHEMA = vol.Schema({
    vol.Required("start"): _meal_day,
    vol.Required("end"): _meal_day,
    # Lot 6 : la porte du vocal. `vol.In(MEAL_SLOT_KEYS)` et non une liste
    # recopiée — le vocabulaire des créneaux a UN seul propriétaire, `const.py`.
    vol.Optional("slot_key"): vol.In(MEAL_SLOT_KEYS),
})
```

et dans `query_meals`, après l'appel à `list_meals` :

```python
        slot = call.data.get("slot_key")
        if slot is not None:
            meals = [m for m in meals if m["slot_key"] == slot]
        return {"meals": meals}
```

Dans `services.yaml`, sous `query_meals.fields`, en **français** :

```yaml
    slot_key:
      name: Créneau
      description: >-
        Ne rend que ce créneau-là : petit-déjeuner, déjeuner, dîner ou
        collation. Absent, la réponse porte tous les repas de la plage.
      required: false
      selector:
        select:
          options:
            - { value: breakfast, label: Petit-déjeuner }
            - { value: lunch, label: Déjeuner }
            - { value: dinner, label: Dîner }
            - { value: snack, label: Collation }
```

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_services_meals.py tests/test_surface_parity.py -q`
Expected: PASS

- [x] **Step 5: Vérifier que le test a des dents**

Remplacer `vol.In(MEAL_SLOT_KEYS)` par `str`. `test_query_meals_refuses_an_unknown_slot` doit tomber. Puis remplacer le filtre par `m["slot_key"] == slot or True` : `test_query_meals_filters_on_a_slot` doit tomber. Remettre le code correct.

- [x] **Step 6: Suite complète**

Run: `./scripts/test.sh -q`
Expected: PASS

- [x] **Step 7: Commit**

```bash
git add custom_components/home_stock/services.py custom_components/home_stock/services.yaml \
        tests/test_services_meals.py tests/test_surface_parity.py
git commit -m "feat: query_meals takes an optional slot_key, and the asymmetry is written down"
```

---

## Task 3: Les sept phrases — `custom_sentences/fr/home_stock.yaml`

**Dépôt : `meal`.** Livré dans le dépôt, **jamais copié par l'intégration**. `docs/exploitation.md` (Task 19) explique le geste : copier le fichier dans `config/custom_sentences/fr/`, coller le paquet d'intents, recharger.

**Pourquoi des intents natifs plutôt que des outils exposés au LLM.** Un agent conversationnel HA essaie d'abord les intents locaux et ne passe au LLM que s'il n'en reconnaît aucun. Trois conséquences : « Il me reste des œufs ? » répond **hors ligne**, en quelques dizaines de millisecondes, sans qu'un modèle puisse halluciner un stock ; une phrase d'écriture est **déterministe** — un LLM qui choisit ses outils pourrait un jour appeler `add_stock` au lieu de `add_to_shopping_list`, inacceptable sur un service qui écrit ; et les phrases restent **en français, dans un fichier lisible et versionné**. Le LLM garde tout ce que les sept intents ne reconnaissent pas : **c'est un repli, pas le mécanisme.**

**Files:**
- Create: `custom_sentences/fr/home_stock.yaml`
- Test: `tests/test_voice_package.py`

**Interfaces:**
- Produit sept noms d'intents, **en anglais** comme tout identifiant du composant : `HomeStockQueryStock`, `HomeStockQueryMeals`, `HomeStockQueryShoppingList`, `HomeStockAddToShoppingList`, `HomeStockQueryExpirations`, `HomeStockValidateMeal`, `HomeStockQueryToday`.
- Trois listes de slots : `product` (`wildcard: true`), `quantity` (`wildcard: true`), `slot` (valeurs → `breakfast`/`lunch`/`dinner`/`snack`).

- [x] **Step 1: Écrire les tests**

Créer `tests/test_voice_package.py`. **Ce fichier ne démarre pas Home Assistant et ne sort pas sur le réseau** : il lit deux fichiers YAML livrés et vérifie qu'ils tiennent ensemble.

```python
"""Le paquet vocal est LIVRÉ, jamais installé — donc jamais chargé par un
test d'intégration. Ce qui reste vérifiable, et qui casse en silence sinon,
c'est sa COHÉRENCE : un intent nommé dans les phrases mais absent du
`intent_script` produit un agent qui reconnaît la phrase et ne répond rien.
C'est la panne la plus difficile à diagnostiquer de tout le lot, parce qu'elle
ressemble à « Bleuenn n'a pas compris »."""

SEPT_INTENTS = {
    "HomeStockQueryStock", "HomeStockQueryMeals", "HomeStockQueryShoppingList",
    "HomeStockAddToShoppingList", "HomeStockQueryExpirations",
    "HomeStockValidateMeal", "HomeStockQueryToday",
}


def test_the_sentences_file_declares_exactly_the_seven_intents():
    document = _load("custom_sentences/fr/home_stock.yaml")
    assert document["language"] == "fr"
    assert set(document["intents"]) == SEPT_INTENTS


def test_every_intent_has_at_least_two_ways_of_being_said():
    """Une seule formulation par intent, c'est un intent qui ne marchera que
    pour la personne qui l'a écrite. La spec en promet des variantes ; ce test
    les exige."""
    document = _load("custom_sentences/fr/home_stock.yaml")
    for nom, corps in document["intents"].items():
        phrases = [p for bloc in corps["data"] for p in bloc["sentences"]]
        assert len(phrases) >= 2, nom


def test_every_slot_used_in_a_sentence_is_declared_as_a_list():
    """`{product}` dans une phrase sans `lists: product:` fait échouer le
    chargement de tout le dossier `custom_sentences` — pas seulement de cette
    phrase-là. Une faute de frappe ici coûte les sept intents."""
    document = _load("custom_sentences/fr/home_stock.yaml")
    declarees = set(document.get("lists", {}))
    utilisees = set()
    for corps in document["intents"].values():
        for bloc in corps["data"]:
            for phrase in bloc["sentences"]:
                utilisees |= set(re.findall(r"\{(\w+)\}", phrase))
    assert utilisees <= declarees, utilisees - declarees


def test_the_slot_list_uses_the_component_vocabulary():
    """Les valeurs rendues par la liste `slot` sont EXACTEMENT
    `MEAL_SLOT_KEYS`. Le vocabulaire des créneaux a un seul propriétaire ;
    « gouter » écrit ici serait refusé par `query_meals` (Task 2) au moment
    précis où quelqu'un parle."""
    from custom_components.home_stock.const import MEAL_SLOT_KEYS
    document = _load("custom_sentences/fr/home_stock.yaml")
    valeurs = {v["out"] for v in document["lists"]["slot"]["values"]}
    assert valeurs == set(MEAL_SLOT_KEYS)


def test_the_two_writing_intents_are_the_only_two():
    """La règle du lot : une phrase peut écrire si son effet est BORNÉ et sa
    réparation possible sans urgence. Deux verbes, pas trois. Ce test épingle
    la frontière côté phrases ; `test_no_sentence_asks_to_throw_away` la tient
    côté vocabulaire."""
    ...


def test_no_sentence_asks_to_throw_away_or_to_remove_a_line():
    """`waste` est irréversible ET comptabilisé sur douze mois ; retirer une
    ligne de courses écrit un `removed_at` qui EMPÊCHE la ligne de revenir,
    silencieusement, à chaque réconciliation. Ce sont les deux pires erreurs
    vocales possibles — celles qui se réparent mal parce qu'elles ne se voient
    pas. Aucune phrase ne doit pouvoir les déclencher."""
    document = _load("custom_sentences/fr/home_stock.yaml")
    texte = json.dumps(document, ensure_ascii=False).lower()
    for interdit in ("jette", "jeter", "poubelle", "enlève de la liste",
                     "retire de la liste", "supprime"):
        assert interdit not in texte, interdit
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_voice_package.py -q`
Expected: FAIL — `FileNotFoundError: custom_sentences/fr/home_stock.yaml`

- [x] **Step 3: Écrire le fichier de phrases**

Créer `custom_sentences/fr/home_stock.yaml`. Forme, sur l'exemple 1 :

```yaml
# Les sept phrases du garde-manger, pour l'agent conversationnel de la maison.
#
# LIVRÉ, JAMAIS INSTALLÉ : copier ce fichier dans config/custom_sentences/fr/.
# `home_stock` ne modifie jamais la configuration de la maison — même contrat
# que les blueprints des lots 2 et 2bis.
#
# Identifiants d'intents, listes et slots EN ANGLAIS, comme tout le code depuis
# le lot 0 ; seules les phrases et les réponses sont en français.
language: fr
intents:
  HomeStockQueryStock:
    data:
      - sentences:
          - "(il me reste|est-ce qu'il (me )?reste|il y a) (du|de la|des|de l') {product}"
          - "combien (il me reste|il reste|j'ai) (de|du|de la|des|d') {product}"
  HomeStockQueryMeals:
    data:
      - sentences:
          - "qu'est-ce qu'on mange {slot}"
          - "c'est quoi le {slot}"
      - sentences:
          - "qu'est-ce qui est prévu (à manger|au menu)"
        # Sans slot : la journée entière. L'intent_script s'en accommode.
  ...
lists:
  product:
    wildcard: true
  quantity:
    wildcard: true
  slot:
    values:
      - in: "(ce soir|le dîner|au dîner|le diner)"
        out: "dinner"
      - in: "(ce midi|le déjeuner|au déjeuner)"
        out: "lunch"
      - in: "(ce matin|le petit-déjeuner|au petit déjeuner)"
        out: "breakfast"
      - in: "(le goûter|la collation)"
        out: "snack"
```

Les sept intents sont écrits en entier, avec au moins deux variantes chacun, en reprenant mot pour mot le tableau du § 9.1 de la spec.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_voice_package.py -q`
Expected: PASS (les tests qui portent sur le paquet `intent_script` restent rouges — ils sont l'objet de la Task 4 ; les écrire maintenant et les laisser rouges est **interdit** : ne les ajouter qu'en Task 4.)

- [x] **Step 5: Commit**

```bash
git add custom_sentences/fr/home_stock.yaml tests/test_voice_package.py
git commit -m "feat: the seven French sentences of the pantry, delivered never installed"
```

---

## Task 4: Le paquet `intent_script` et sa confirmation à deux tours

**Dépôt : `meal`.** Le corps de chaque intent : l'appel du service à réponse, et sa mise en phrase.

**Files:**
- Create: `packages/home_stock_intents.yaml`
- Modify: `tests/test_voice_package.py`
- Modify: `docs/exploitation.md` *(la liste des sept phrases seulement ; le reste de la section vient en Task 19)*

**Interfaces:**
- Consomme : `home_stock.query_stock`, `query_meals` (**avec `slot_key`, Task 2**), `query_shopping_list`, `add_to_shopping_list`, `validate_meal`, et les attributs `batches` de `binary_sensor.home_stock_expirations`, `meal_id` de `sensor.home_stock_next_meal` (**Task 1**).
- Produit : sept clés sous `intent_script:`, prêtes à coller dans `configuration.yaml` ou à charger comme paquet.

**Deux règles de rédaction, reprises de `dlc_bleuenn.yaml`** :
1. **Jamais une liste brute.** « Il te reste six œufs et un litre de lait », avec l'accord de nombre en Jinja — pas « œufs: 6, lait: 1 ».
2. **Une phrase quand il n'y a rien.** « Il ne reste plus d'œufs » est une réponse ; **le silence est une panne.**

**La confirmation de « j'ai mangé le dîner », concrètement.** `home_stock.validate_meal` simule par défaut (`dry_run: true`, décision du lot 3). L'intent l'exploite tel quel, sans une ligne de composant :
1. premier tour — `validate_meal` avec `dry_run: true` → Bleuenn énonce le plan de décrément (« je retire 200 g de pommes de terre, 150 g de crème et deux œufs, je confirme ? ») ;
2. second tour — sur « oui », `validate_meal` avec `dry_run: false`.

C'est le « deux appuis » de la tablette, transposé à l'oral. **Le `dry_run` par défaut du lot 3 vient de payer une seconde fois.**

- [x] **Step 1: Écrire les tests**

Dans `tests/test_voice_package.py`, à la suite. Le patron est **exactement** celui de `test_event_expiration.py` (validation d'un blueprint livré) : charger le YAML, puis le passer dans les schémas de Home Assistant eux-mêmes — un YAML qui « a l'air bon » n'est pas un YAML que HA accepte.

```python
def test_the_package_defines_exactly_the_seven_intents():
    document = _load("packages/home_stock_intents.yaml")
    assert set(document["intent_script"]) == SEPT_INTENTS


def test_every_sentence_intent_has_a_script_and_the_reverse():
    """L'appariement, le seul contrôle qui attrape la panne « Bleuenn a
    compris et n'a rien dit »."""
    phrases = set(_load("custom_sentences/fr/home_stock.yaml")["intents"])
    scripts = set(_load("packages/home_stock_intents.yaml")["intent_script"])
    assert phrases == scripts


def test_every_action_validates_through_home_assistant():
    """`cv.SCRIPT_SCHEMA`, pas un simple `isinstance(dict)` : la faute
    classique est d'écrire `service:` là où HA 2026.8 attend `action:`, et
    seul le schéma du produit la voit."""
    from homeassistant.helpers import config_validation as cv
    for nom, corps in _load("packages/home_stock_intents.yaml")["intent_script"].items():
        cv.SCRIPT_SCHEMA(corps["action"]), nom


def test_every_speech_template_is_valid_jinja(hass):
    """Un template cassé rend l'intent muet à l'exécution, jamais au
    chargement. `ensure_valid` déplace la panne au moment où on peut la voir."""
    from homeassistant.helpers.template import Template
    for nom, corps in _load("packages/home_stock_intents.yaml")["intent_script"].items():
        Template(corps["speech"]["text"], hass).ensure_valid()


def test_every_service_called_exists_with_the_fields_used():
    """Un `slot_key` mal orthographié dans l'intent serait refusé par
    `vol.In` au moment où quelqu'un parle. Ce test compare les champs
    employés à `services.yaml`, la déclaration qui fait foi."""
    ...


def test_the_meal_intent_previews_before_it_writes():
    """LA règle du lot 6 sur l'écriture vocale : le premier tour ne doit RIEN
    décrémenter. Si `dry_run: true` disparaît de la première branche, une
    phrase mal comprise vide un stock sans confirmation — et le journal étant
    en ajout seul, elle ne s'annule pas : elle se contrepasse, depuis le
    panneau."""
    corps = _load("packages/home_stock_intents.yaml")["intent_script"]["HomeStockValidateMeal"]
    rendu = json.dumps(corps, ensure_ascii=False)
    assert "dry_run: true" in rendu or '"dry_run": true' in rendu
    assert "je confirme" in rendu.lower() or "confirme" in rendu.lower()


def test_no_intent_calls_a_writing_service_other_than_the_two_allowed():
    """`add_stock`, `consume`, `waste`, `remove_from_shopping_list`,
    `correct_movement` n'ont RIEN à faire dans un paquet vocal. Deux verbes,
    et ce test est la barrière."""
    interdits = {"home_stock.add_stock", "home_stock.consume", "home_stock.waste",
                 "home_stock.remove_from_shopping_list", "home_stock.correct_movement",
                 "home_stock.correct_meal", "home_stock.plan_meal", "todo.remove_item"}
    rendu = json.dumps(_load("packages/home_stock_intents.yaml"), ensure_ascii=False)
    for service in interdits:
        assert service not in rendu, service


def test_every_intent_answers_something_when_there_is_nothing():
    """« Il ne reste plus d'œufs » est une réponse ; le silence est une panne.
    Chaque `speech.text` doit porter un `{% if %}…{% else %}…` — un template
    qui rend la chaîne vide sur une liste vide est un intent qui a l'air
    cassé."""
    for nom, corps in _load("packages/home_stock_intents.yaml")["intent_script"].items():
        assert "{% else %}" in corps["speech"]["text"], nom
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/test_voice_package.py -q`
Expected: FAIL — `FileNotFoundError: packages/home_stock_intents.yaml`

- [x] **Step 3: Écrire le paquet**

Créer `packages/home_stock_intents.yaml`. Extrait, sur l'exemple 1 et l'exemple 6 :

```yaml
# LIVRÉ, JAMAIS INSTALLÉ. Coller ce bloc dans configuration.yaml, ou charger
# ce fichier comme paquet (`homeassistant: packages: !include_dir_named packages`).
# `intent_script` est une clé de configuration.yaml, un fichier que le
# propriétaire tient à la main : l'intégration n'y touche jamais.
intent_script:
  HomeStockQueryStock:
    action:
      - action: home_stock.query_stock
        data:
          query: "{{ product }}"
        response_variable: reponse
    speech:
      text: >-
        {% set lignes = reponse.items | default([]) %}
        {% if lignes %}
          Il te reste {{ lignes | map(attribute='label') | join(', ') }}.
        {% else %}
          Il ne reste plus de {{ product }}.
        {% endif %}

  HomeStockValidateMeal:
    # DEUX TOURS. Le premier ne décrémente rien (`dry_run: true`, défaut du
    # lot 3) et énonce le plan ; le second, déclenché par « oui », écrit.
    # Un service qui décrémente un stock ne doit pas le faire au premier appel
    # exploratoire — et une phrase mal comprise ne s'annule pas, elle se
    # contrepasse depuis le panneau.
    action:
      - action: home_stock.validate_meal
        data:
          meal_id: "{{ state_attr('sensor.home_stock_next_meal', 'meal_id') }}"
          dry_run: true
        response_variable: apercu
    speech:
      text: >-
        {% if apercu.lines | default([]) %}
          Je retire {{ … }}. Je confirme ?
        {% else %}
          Il n'y a rien à retirer pour ce repas.
        {% endif %}
```

Les sept sont écrits en entier. Le second tour de `HomeStockValidateMeal` est porté par une phrase de confirmation déclarée en Task 3 et par une seconde clé d'intent-script documentée dans le fichier — le mécanisme exact (intent de confirmation dédié) est **écrit dans le fichier, en commentaire, à côté du code qui l'implémente**, pour que le propriétaire puisse le relire.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_voice_package.py -q`
Expected: PASS

- [x] **Step 5: Vérifier que les tests ont des dents**

Retirer `dry_run: true` du premier tour : `test_the_meal_intent_previews_before_it_writes` doit tomber. Remplacer un `action:` par `service:` : `test_every_action_validates_through_home_assistant` doit tomber. Ajouter `home_stock.waste` dans un `action` : `test_no_intent_calls_a_writing_service_other_than_the_two_allowed` doit tomber. Remettre le code correct après chaque mutation.

- [x] **Step 6: Les sept phrases dans `docs/exploitation.md`**

Ajouter la table des sept phrases, avec leurs variantes **et leur réponse attendue** — c'est le document qu'on relit quand une phrase ne marche pas, et il doit être **rejouable à la main en trois minutes**.

- [x] **Step 7: Suite complète et commit**

```bash
./scripts/test.sh -q
git add packages/home_stock_intents.yaml tests/test_voice_package.py docs/exploitation.md
git commit -m "feat: the intent_script package, with a two-turn confirmation before any decrement"
```

---

## Task 5: Le blueprint `courses_bleuenn.yaml`

**Dépôt : `meal`.** Le seul ajout **sortant** du lot. Il ne mérite un blueprint que pour une raison : il n'existe **aucune** autre façon de rappeler la liste au moment où on part.

**Files:**
- Create: `blueprints/automation/home_stock/courses_bleuenn.yaml`
- Modify: `tests/test_voice_package.py`

**Interfaces:**
- Consomme : `sensor.home_stock_shopping_list` et son attribut `items` (id, nom, quantité, rayon, coché) ainsi que `by_aisle`.
- Entrées du blueprint : `heure` (défaut `"18:00:00"`), `agent` (défaut `conversation.personas_studio_home_manager`), `capteur` (défaut `sensor.home_stock_shopping_list`), `detail_max` (défaut `5`).

**Ce qu'il annonce.** Les lignes **non cochées** groupées par rayon, plafonnées à ce qui se retient à l'oreille : « sept articles, dont trois au rayon frais », **avec le détail seulement si la liste est courte** (`detail_max`). Déclencheur **horaire**, jamais un basculement d'état : le coordinateur se rafraîchit parfois à trois heures du matin.

**Refusé, et c'est écrit ici pour que personne n'aille le chercher** : l'alerte de fin de garantie à la voix, que le lot 5 (§ 18) laissait au lot 6. Une fin de garantie se traite **avec une facture sous les yeux**, pas en écoutant une enceinte. Le capteur `sensor.home_stock_warranty_next` reste disponible pour qui veut l'automation.

- [x] **Step 1: Écrire le test**

Dans `tests/test_voice_package.py`, en reprenant **mot pour mot** le patron de `tests/test_event_expiration.py` (chargement, substitution des `!input` par leurs défauts, `cv.CONDITION_SCHEMA` et `cv.SCRIPT_SCHEMA`) :

```python
def test_the_shopping_blueprint_is_a_valid_automation():
    document = _load("blueprints/automation/home_stock/courses_bleuenn.yaml")
    assert document["blueprint"]["domain"] == "automation"
    assert set(document["blueprint"]["input"]) == {"heure", "agent", "capteur", "detail_max"}
    assert document["triggers"][0]["trigger"] == "time"
    ...
    action = cv.SCRIPT_SCHEMA(substitue["actions"])[0]
    assert action["action"] == "conversation.process"


def test_the_shopping_blueprint_passes_its_entity_as_a_variable():
    """Le piège déjà payé par `dlc_bleuenn.yaml` : `!input capteur` ne
    s'interpole PAS dans le Jinja en dessous — il doit passer par une variable
    nommée, sinon le texte que Bleuenn lit ne voit aucune ligne, sans erreur."""
    document = _load("blueprints/automation/home_stock/courses_bleuenn.yaml")
    assert set(document["variables"]) >= {"nom_capteur"}
    assert "nom_capteur" in document["actions"][0]["data"]["text"]


def test_the_shopping_blueprint_only_counts_unticked_lines():
    """Annoncer ce qui est déjà dans le panier est le meilleur moyen de faire
    ignorer l'annonce. Le template filtre sur l'état coché."""
    texte = _load(...)["actions"][0]["data"]["text"]
    assert "checked" in texte


def test_the_shopping_blueprint_says_something_on_an_empty_list_or_nothing_at_all():
    """Soit une condition qui empêche l'annonce, soit une phrase. Jamais une
    annonce vide — c'est la règle de rédaction du § 9.2, et elle vaut aussi
    pour le sens sortant."""
    ...
```

- [x] **Step 2: Lancer le test, vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_voice_package.py -q`
Expected: FAIL — fichier absent

- [x] **Step 3: Écrire le blueprint**

Créer `blueprints/automation/home_stock/courses_bleuenn.yaml`, dans la forme exacte de `dlc_bleuenn.yaml` : bloc `blueprint` avec `name`, `description` (dont la phrase « À importer une fois ; ce fichier n'est jamais installé par l'intégration. »), `domain: automation`, quatre `input`, puis `triggers` / `conditions` / `variables` / `actions`.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/test_voice_package.py -q`
Expected: PASS

- [x] **Step 5: Vérifier que le test a des dents**

Interpoler `!input capteur` directement dans le template au lieu de passer par `nom_capteur` : `test_the_shopping_blueprint_passes_its_entity_as_a_variable` doit tomber. Remettre le code correct.

- [x] **Step 6: Suite complète et commit**

```bash
./scripts/test.sh -q
git add blueprints/automation/home_stock/courses_bleuenn.yaml tests/test_voice_package.py
git commit -m "feat: courses_bleuenn, the third blueprint — delivered, never installed"
```

---

## Task 6: Le socle de la vue dense — `large` propagé, `narrow` écouté

**Dépôt : `meal`, front.** La vue dense est **le panneau existant, au-delà de 1000 px** : pas une page séparée, pas un second bundle, pas un second point d'entrée. Un second frontend doublerait rollup, le vérificateur, la file hors-ligne, la connexion et 26 fichiers de tests **pour zéro fonction nouvelle** — et deux frontends sur un même modèle finissent par diverger sur une règle de validation, l'argument même qui a fait écrire `test_surface_parity.py`.

**Files:**
- Modify: `frontend/src/panneau.ts`
- Test: `frontend/tests/panneau.test.ts`

**Interfaces:**
- Consomme : `@state() large` (`window.innerWidth >= 1000`, ligne 316) et `@property({attribute: false}) narrow` (ligne 70, fourni par le frontend hôte et **inutilisé jusqu'ici**).
- Produit : `.large=${this.large}` passé à **sept** écrans — `catalogue`, `journal`, `liste`, `reglages`, `ticket`, `equipements`, `piles` — en plus de `planning` qui l'a déjà. Les dix autres ne le reçoivent pas, et ne doivent pas le recevoir.

**Décision sur `narrow`.** Le frontend hôte sait s'il est étroit ; on n'a pas à le redécouvrir. **`large` reste la mesure qui décide** (elle vaut aussi hors panneau HA, dans le harnais du vérificateur, qui ne fournit pas `narrow`), mais un hôte qui affirme `narrow === true` **force** `large` à faux : c'est le cas de la barre latérale repliée sur une tablette large, où la place réelle du panneau est bien plus petite que `innerWidth`. Une seule ligne, et elle évite une mise en page dense écrasée dans une colonne de 400 px.

- [x] **Step 1: Écrire les tests**

Dans `frontend/tests/panneau.test.ts` :

```ts
it('bascule large sur resize, dans les deux sens', async () => {
  // Mesuré, jamais déduit d'un agent utilisateur : c'est ce qui rend le
  // seuil testable sans navigateur.
  const p = await monter({ largeurFenetre: 412 });
  expect(p.large).toBe(false);
  redimensionner(1280); await p.updateComplete;
  expect(p.large).toBe(true);
  redimensionner(999); await p.updateComplete;
  expect(p.large).toBe(false);        // le retour compte autant que l'aller
});

it('un hôte qui se dit étroit gagne contre la largeur mesurée', async () => {
  // Barre latérale HA dépliée : innerWidth ment sur la place réelle.
  const p = await monter({ largeurFenetre: 1280, narrow: true });
  expect(p.large).toBe(false);
});

it('passe large aux sept écrans denses et à eux seuls', async () => {
  // Le garde-fou de la décision « dix écrans ne changent pas » : si demain
  // quelqu'un branche `large` sur le scanner, ce test le dit tout de suite.
  for (const ecran of ['catalogue', 'journal', 'liste', 'reglages', 'ticket',
                       'equipements', 'piles', 'planning'] as const) {
    expect(await recoitLarge(ecran)).toBe(true);
  }
  for (const ecran of ['scanner', 'fiche', 'panier', 'rangement', 'session',
                       'recettes', 'recette', 'validation', 'consommation'] as const) {
    expect(await recoitLarge(ecran)).toBe(false);
  }
});

it('ne casse aucun écran étroit', async () => {
  // Chaque écran se monte et se démonte à 412 px, comme avant le lot.
  ...
});
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test -- panneau`
Expected: FAIL — les sept écrans ne reçoivent pas `large`, et `narrow` est ignoré.

- [x] **Step 3: Câbler**

Dans `panneau.ts`, la propriété devient une **dérivation** plutôt qu'un état recopié :

```ts
  /** Vrai au-delà de 1000 px de large — sauf si l'hôte affirme être étroit.
   *  Home Assistant fournit `narrow` au panneau depuis toujours, et ne s'était
   *  jamais servi : la barre latérale dépliée sur une tablette large laisse au
   *  panneau bien moins que `innerWidth`, et une mise en page dense écrasée
   *  dans 400 px est pire que la mise en page étroite qu'elle remplace. */
  @state() private largeMesure = typeof window !== 'undefined' && window.innerWidth >= 1000;

  get large(): boolean { return this.largeMesure && !this.narrow; }
```

puis `.large=${this.large}` sur les sept écrans, à côté de `planning` qui l'a déjà.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test -- panneau`
Expected: PASS

- [x] **Step 5: Les deux suites**

```bash
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: **499 + 4 tests** verts, **47 exécutions** vertes (le format n'a pas encore bougé, et aucun écran n'a encore changé de mise en page — c'est justement ce qu'on veut prouver ici : le câblage seul ne change rien à ce qui se voit).

- [x] **Step 6: Commit**

```bash
git add frontend/src/panneau.ts frontend/tests/panneau.test.ts
git commit -m "feat: large reaches the seven dense screens, and a narrow host wins"
```

---

## Task 7: `catalogue` en tableau, édition en ligne

**Dépôt : `meal`, front.** Le cœur de la vue dense. Son docstring dit déjà *« Pensé pour le PC »* : **la quatrième surface n'est pas à inventer, elle est commencée et jamais finie.**

**Files:**
- Modify: `frontend/src/ecrans/catalogue.ts`
- Test: `frontend/tests/catalogue.test.ts`

**Interfaces:**
- Consomme : `@property({ type: Boolean }) large = false` (même patron que `planning.ts`, ligne 61).
- Produit : au-delà de 1000 px, un `<table>` à colonnes — nom, unité de base, seuil, catégorie, durée de conservation — et l'édition **sans quitter la liste**.

**Ce que la largeur apporte, et que 412 px ne peut pas.** Trouver un doublon parmi trois cents produits suppose de voir trente lignes d'un coup ; corriger trente seuils au pouce est une soirée. **En étroit, rien ne change** : la liste empilée et le formulaire plein écran restent exactement ce qu'ils sont.

**Ce que la vue dense n'ouvre pas.** Ni `base_unit` (seul `home_stock/product/convert_unit` le change, atomiquement), ni la catégorie (aucun `home_stock/categories/list` n'existe côté serveur). Les deux restent en **lecture seule**, comme en étroit — élargir un écran n'élargit pas ses droits.

- [x] **Step 1: Écrire les tests**

Dans `frontend/tests/catalogue.test.ts` :

```ts
it('rend un tableau à colonnes au-delà de 1000 px', async () => {
  const e = await monterCatalogue({ large: true, produits: TROIS_CENTS });
  expect(e.shadowRoot!.querySelector('table')).not.toBeNull();
  expect(entetes(e)).toEqual(['Nom', 'Unité', 'Seuil', 'Catégorie', 'Conservation']);
});

it('reste une liste empilée en étroit', async () => {
  const e = await monterCatalogue({ large: false, produits: TROIS_CENTS });
  expect(e.shadowRoot!.querySelector('table')).toBeNull();
});

it('édite une ligne sans quitter la liste', async () => {
  // C'est TOUT l'intérêt de la largeur : corriger, voir la ligne suivante,
  // corriger. Un formulaire qui remplace la liste annule le gain.
  const e = await monterCatalogue({ large: true, produits: TROIS_CENTS });
  cliquer(ligne(e, 12));
  expect(e.shadowRoot!.querySelectorAll('tbody tr').length).toBe(300);
  saisir(champ(e, 'seuil'), '4');
  cliquer(bouton(e, 'Enregistrer'));
  expect(file.derniere()).toMatchObject({ type: 'home_stock/product/update',
                                          fields: { min_stock: 4 } });
});

it("n'ouvre jamais l'unité de base ni la catégorie, même en large", async () => {
  const e = await monterCatalogue({ large: true, produits: TROIS_CENTS });
  cliquer(ligne(e, 12));
  expect(champ(e, 'base_unit')).toBeNull();
  expect(champ(e, 'category')).toBeNull();
});

it('refuse une virgule décimale plutôt que de deviner, en large aussi', async () => {
  // `Number('1,5')` vaut NaN et NaN sérialisé vaut null : sans ce refus,
  // une virgule EFFACE un seuil en laissant croire à un enregistrement
  // réussi. La règle vient de l'étroit ; elle ne se perd pas en chemin.
  ...
});

it('passe toute écriture par la file hors-ligne', async () => {
  // Aucun second chemin d'écriture : `connexion` directe interdite.
  ...
});
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test -- catalogue`
Expected: FAIL — pas de `<table>`

- [x] **Step 3: Écrire la mise en page dense**

Ajouter `@property({ type: Boolean }) large = false;` et une branche de rendu. **Une seule branche** — pas deux composants, pas deux fichiers : les données, les commandes et les validations sont les mêmes, seule la disposition change.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test -- catalogue`
Expected: PASS

- [x] **Step 5: Les deux suites**

```bash
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert, **toujours 47 exécutions** — le scénario dense arrive en Task 11.

- [x] **Step 6: Commit**

```bash
git add frontend/src/ecrans/catalogue.ts frontend/tests/catalogue.test.ts
git commit -m "feat: the catalogue becomes a table past 1000px, editable in place"
```

---

## Task 8: `journal` — les barres et le jour, côte à côte

**Dépôt : `meal`, front.** Aujourd'hui il faut naviguer entre les deux. Douze barres mensuelles font 30 px chacune sur 412 px ; sur 1280, elles se lisent.

**Files:**
- Modify: `frontend/src/ecrans/journal.ts`
- Test: `frontend/tests/journal.test.ts`

**Interfaces:**
- Consomme : `large`, `home_stock/journal/series` (`MAX_SERIES_COUNT = 60`), `home_stock/journal/day`.
- Produit : deux colonnes au-delà de 1000 px — la série à gauche, le détail du jour sélectionné à droite. **Le panneau dessine ses barres lui-même** (lot 2) : rien de neuf à ce sujet ici.

- [x] **Step 1: Écrire les tests**

```ts
it('affiche la série et le détail en même temps au-delà de 1000 px', async () => {
  const e = await monterJournal({ large: true });
  expect(barres(e).length).toBe(12);
  expect(detailDuJour(e)).not.toBeNull();      // les deux, simultanément
});

it('en étroit, une seule des deux vues à la fois', async () => {
  const e = await monterJournal({ large: false });
  expect(detailDuJour(e)).toBeNull();
});

it('cliquer une barre en large change le détail sans faire disparaître la série', async () => {
  // Le vrai gain : comparer. Si le clic remplace la série, on a juste
  // déplacé la navigation, on ne l'a pas supprimée.
  const e = await monterJournal({ large: true });
  cliquer(barres(e)[3]);
  await e.updateComplete;
  expect(barres(e).length).toBe(12);
  expect(jourAffiche(e)).toBe('2026-05-01');
});

it('ne demande jamais plus de MAX_SERIES_COUNT seaux', async () => {
  // Une vue large ne se donne pas le droit de demander plus au serveur que
  // ce que le serveur borne. Le seuil est côté composant, et il gagne.
  ...
});

it('corrige un mouvement en large, par la file, avec confirmation', async () => {
  // Chercher une ligne, lire sa contrepartie, confirmer : personne ne fait
  // ça debout. Une correction est une CONTREPASSATION, pas une annulation —
  // le journal garde les deux, et l'écran le dit.
  ...
});
```

- [x] **Step 2: Lancer, échouer** — `npm test -- journal`
- [x] **Step 3: Écrire la mise en page dense**
- [x] **Step 4: Lancer, passer** — `npm test -- journal`
- [x] **Step 5: Les deux suites** — `npm test && node outils/verifier-rendu.mjs`, tout vert, 47 exécutions
- [x] **Step 6: Commit**

```bash
git add frontend/src/ecrans/journal.ts frontend/tests/journal.test.ts
git commit -m "feat: twelve monthly bars and the day's detail, side by side"
```

---

## Task 9: `liste` en colonnes de rayons, `reglages` en trois colonnes

**Dépôt : `meal`, front.** Deux écrans, une seule idée : ce qui est **court mais large** ou **listé trois fois** gagne à ne plus être empilé.

**Files:**
- Modify: `frontend/src/ecrans/liste.ts`, `frontend/src/ecrans/reglages.ts`
- Test: `frontend/tests/liste.test.ts`, `frontend/tests/reglages.test.ts`

**Interfaces:**
- `liste` : rayons en colonnes plutôt qu'empilés. Une ligne porte nom, quantité, rayon et origine — courte, mais large.
- `reglages` : rayons, emplacements et magasins en **trois colonnes**. Trois listes réordonnables, aujourd'hui empilées.

**Le piège de `reglages`, et il est réel.** Les trois listes sont **réordonnables**. Un réordonnancement qui marche en colonne unique peut se casser en trois colonnes si la cible de dépôt est calculée sur la position dans le document plutôt que dans sa propre liste. Le test l'exige explicitement.

- [x] **Step 1: Écrire les tests**

```ts
// liste.test.ts
it('range les rayons en colonnes au-delà de 1000 px', async () => { ... });
it('reste empilée en étroit', async () => { ... });
it("n'affiche pas de prix ni d'estimation de plus qu'en étroit", async () => {
  // Élargir n'ajoute pas de donnée : c'est la MÊME liste, mieux disposée.
  ...
});

// reglages.test.ts
it('rend trois colonnes au-delà de 1000 px', async () => { ... });
it('réordonne dans la BONNE liste quand elles sont côte à côte', async () => {
  // Le piège de la tâche : trois listes réordonnables côte à côte. Déplacer
  // « Frais » ne doit jamais réordonner les magasins.
  const e = await monterReglages({ large: true });
  deplacer(e, { liste: 'rayons', de: 2, vers: 0 });
  expect(file.derniere()).toMatchObject({ type: 'home_stock/aisles/reorder' });
  expect(ordre(e, 'magasins')).toEqual(ORDRE_MAGASINS_INITIAL);
});
it('conserve les objectifs nutritionnels et leur validation', async () => { ... });
```

- [x] **Step 2: Lancer, échouer** — `npm test -- liste reglages`
- [x] **Step 3: Écrire les deux mises en page**
- [x] **Step 4: Lancer, passer** — `npm test -- liste reglages`
- [x] **Step 5: Les deux suites**, tout vert, 47 exécutions
- [x] **Step 6: Commit**

```bash
git add frontend/src/ecrans/liste.ts frontend/src/ecrans/reglages.ts \
        frontend/tests/liste.test.ts frontend/tests/reglages.test.ts
git commit -m "feat: aisles in columns, settings in three — reordering stays in its own list"
```

---

## Task 10: `ticket` côte à côte, `equipements` et `piles` en tableau

**Dépôt : `meal`, front.** Le rapprochement d'un ticket se fait **en comparant** ; empilés, on scrolle entre la photo et les lignes.

**Files:**
- Modify: `frontend/src/ecrans/ticket.ts`, `frontend/src/ecrans/equipements.ts`, `frontend/src/ecrans/piles.ts`
- Test: `frontend/tests/ticket.test.ts`, `frontend/tests/equipements.test.ts`, `frontend/tests/piles.test.ts`

**Interfaces:**
- `ticket` : photo à gauche, lignes rapprochées à droite, au-delà de 1000 px.
- `equipements`, `piles` : tableau — même argument que le catalogue, sur moins de lignes.

- [x] **Step 1: Écrire les tests**

```ts
// ticket.test.ts
it('montre la photo et les lignes en même temps au-delà de 1000 px', async () => { ... });
it('garde la photo lisible : elle ne dépasse pas la moitié de la largeur', async () => {
  // Une photo de ticket est haute et étroite. Lui donner la moitié d'un
  // 1920 px la rendrait illisible de loin et écraserait les lignes.
  ...
});
it('rapproche une ligne sans perdre la position de défilement de la photo', async () => { ... });

// equipements.test.ts / piles.test.ts
it('rend un tableau au-delà de 1000 px', async () => { ... });
it('reste une liste de cartes en étroit', async () => { ... });
it('une garantie échue reste signalée dans les deux mises en page', async () => {
  // Une information d'alerte ne disparaît pas en changeant de disposition :
  // c'est exactement le genre de perte silencieuse qu'une seconde mise en
  // page introduit.
  ...
});
```

- [x] **Step 2: Lancer, échouer** — `npm test -- ticket equipements piles`
- [x] **Step 3: Écrire les trois mises en page**
- [x] **Step 4: Lancer, passer** — `npm test -- ticket equipements piles`
- [x] **Step 5: Les deux suites**, tout vert, 47 exécutions
- [x] **Step 6: Commit**

```bash
git add frontend/src/ecrans/ticket.ts frontend/src/ecrans/equipements.ts frontend/src/ecrans/piles.ts \
        frontend/tests/ticket.test.ts frontend/tests/equipements.test.ts frontend/tests/piles.test.ts
git commit -m "feat: receipt side by side, equipment and batteries as tables"
```

---

## Task 11: Le troisième format du vérificateur — 47 → 70 exécutions

**Dépôt : `meal`, front.** La tâche qui prouve que les quatre précédentes tiennent **dans un vrai navigateur**, aux trois largeurs.

**Files:**
- Modify: `frontend/outils/verifier-rendu.mjs`

**Interfaces:**
- Consomme : `FORMATS` (ligne 83), `SCENARIOS` (22, ligne 656), `SCENARIOS_MINIFIES` (3, ligne 1341), `executerScenarios`.
- Produit : un troisième format et une nouvelle liste `SCENARIOS_LARGES`, exécutée **dans le seul 1920 × 1080**.

**Le compte, et il faut le comprendre avant de l'écrire.** Le vérificateur compte des **exécutions**, pas des scénarios :

| | Avant | Après |
|---|---|---|
| `SCENARIOS` × `FORMATS` | 22 × 2 = 44 | 22 × **3** = **66** |
| `SCENARIOS_MINIFIES` | 3 | 3 |
| `SCENARIOS_LARGES` × 1 format | — | **1** |
| **Total** | **47** | **70** |

**Pourquoi une liste à part et non un 23ᵉ scénario dans `SCENARIOS`.** Un scénario ajouté à `SCENARIOS` tournerait dans les trois formats, donc **aussi en 412 px**, où il mesurerait la mise en page étroite en croyant mesurer la dense — un contrôle qui passe sans rien prouver. `SCENARIOS_LARGES` s'exécute dans un seul format et le dit dans son nom.

**Pourquoi 1920 × 1080 et pas seulement 1280 × 800.** Le 1280 × 800 est **à peine au-dessus** du seuil de 1000 px : c'est le cas où la mise en page dense est la plus **serrée**, donc celui qui détecte un débordement. Le 1920 × 1080 est le plus **lâche**, donc celui qui détecte l'inverse — un tableau qui laisse 700 px de vide, un texte qui s'étire sur une ligne illisible. **Les deux défauts existent, et aucun des deux formats actuels ne les voit tous les deux.**

- [x] **Step 1: Ajouter le format et le scénario dense**

```js
const FORMATS = [
  { nom: 'Téléphone (Pixel, 412×915)', width: 412, height: 915 },
  { nom: 'Bureau (PC, 1280×800)', width: 1280, height: 800 },
  // Lot 6 : le 1280 × 800 est à peine au-dessus du seuil `large` (1000 px) —
  // il attrape les débordements. Celui-ci attrape l'inverse : l'étirement,
  // le vide, la ligne de texte trop longue pour être lue. Un seul des deux
  // ne suffit pas, et c'est pour ça qu'on garde les trois.
  { nom: 'Grand écran (bureau, 1920×1080)', width: 1920, height: 1080 },
];

// Exécutés dans le SEUL 1920 × 1080 : en 412 px ils mesureraient la mise en
// page étroite en croyant mesurer la dense, et passeraient sans rien prouver.
const SCENARIOS_LARGES = [
  {
    nom: 'Catalogue large : tableau, édition en ligne, trois cents produits',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/products/list': { products: TROIS_CENTS } } },
    actions: [{ type: 'click-nav', texte: 'Catalogue' },
              { type: 'click-ligne', index: 12 }],
    ecranAttendu: 'home-stock-catalogue',
    elementAttendu: 'table',
  },
];
```

Les six autres écrans adaptés (`journal`, `liste`, `reglages`, `ticket`, `equipements`, `piles`) sont **déjà couverts par des scénarios existants**, qui les mesureront désormais dans **trois** formats — c'est précisément le gain du troisième format, et c'est pourquoi il n'y a qu'un scénario neuf.

- [x] **Step 2: Câbler l'exécution du nouveau lot de scénarios**

Une boucle qui réutilise `monterEtMesurer` et `aDesDefauts` — **pas** une seconde implémentation de la mesure. Le compte `total` doit inclure ces exécutions, sinon le chiffre affiché ment.

- [x] **Step 3: Lancer le vérificateur**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs`
Expected: **70 exécutions**, zéro faute. **Si le chiffre affiché n'est pas monté, le format n'a pas été ajouté** — c'est le contrôle le plus simple de cette tâche et le seul qui ne se triche pas.

- [x] **Step 4: Vérifier que les garde-fous existants tiennent toujours**

Les deux mécanismes restent en vigueur et doivent être relancés tels quels :
1. **l'auto-vérification** — le script casse volontairement cinq choses et vérifie qu'il les détecte ; sans elle, « aucun défaut » ne prouve rien ;
2. **le contrôle d'écran atteint** — chaque scénario doit avoir *atteint* l'écran attendu avant d'être mesuré. Un scénario qui mesure l'écran `scanner` en croyant mesurer `catalogue` est vert et vide.

- [x] **Step 5: Vérifier que le nouveau format a des dents**

Donner au tableau du catalogue une largeur fixe de 2200 px. Le 1920 × 1080 doit signaler un **débordement** ; les deux autres formats ne le voient pas. Remettre le code correct. Puis rendre le libellé d'une colonne de tableau en gris clair (contraste < 4,5:1) : les **trois** formats doivent le signaler.

- [x] **Step 6: Les deux suites**

```bash
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: tests verts, **70 exécutions** vertes.

- [x] **Step 7: Commit**

```bash
git add frontend/outils/verifier-rendu.mjs
git commit -m "chore: a third viewport, 1920x1080 — 47 render runs become 70"
```

---

## Task 12: `src/garde-manger.ts` — lire `home_stock` dans un attribut

**Dépôt : `wallpanel-app`.** ⚠️ **Premier changement dans l'autre base de code.** Toutes les commandes se lancent **depuis `/opt/nivuus/HomeAssistant/data/tools/wallpanel-app`**, jamais depuis la racine de `data/`. **Aucun `npm run build` avant la Task 18.**

**Tâche additive : elle ne câble rien.** Le fichier est écrit et testé, `src/grocy.ts` continue d'alimenter l'écran. **Rien ne bouge sur une dalle**, et c'est voulu : la bascule de source est un geste, pas un chantier.

**Files:**
- Create: `src/garde-manger.ts`, `tests/garde-manger.test.ts`

**Interfaces:**
- Consomme : `Etat` (`etat.ts`) — `lire(id)` rend `{ etat, attributs, changeLe }`, `estUtilisable(id)` masque tout ce qui est `unavailable`/`unknown`. **Passé en argument, jamais importé globalement** : c'est ce qui rend ce module pur et testable sans navigateur, même discipline que `contexte.ts`, `jauge.ts` et `modes.ts`.
- Produit :
  - `type RepasSuivant = { etiquette: string; plat: string; mealId: number | null; recetteId: number | null; manquants: number }`
  - `repasSuivant(etat: Etat, maintenant: Date): RepasSuivant | undefined`
  - `nombreDlc(etat: Etat): number | undefined`

**Pourquoi une lecture d'attribut et pas une commande websocket.** Ce n'est pas de l'élégance, c'est de l'économie. `Etat.notifier` coalesce déjà les redessins et la souscription `state_changed` existe depuis le premier jour ; ajouter une lecture périodique `home_stock/list/items` reproduirait **exactement** le défaut que `src/grocy.ts` a mis trois mois à corriger — 3,8 Mo × 96 par jour sur une dalle à 130 Mo de libre. **La donnée qui tient dans un attribut se lit dans l'attribut.**

**Le gain, chiffré** : −3,8 Mo/jour de trafic HTTP, −1 client HTTP (8,3 ko et ses deux bases d'URL selon le protocole), et **−1 chemin de panne** : « Grocy muet » et sa règle « surtout ne pas passer au repas suivant » disparaissent, remplacés par `Etat.estUtilisable`, le masquage générique déjà en place pour toute entité indisponible.

- [ ] **Step 1: Écrire les tests**

Créer `tests/garde-manger.test.ts` :

```ts
describe('repasSuivant', () => {
  it("lit le plat dans l'ÉTAT et le reste dans les attributs", () => {
    const etat = etatAvec('sensor.home_stock_next_meal', 'Gratin dauphinois', {
      day: '2026-08-21', slot: 'dinner', recipe_id: 12, meal_id: 42,
      missing_ingredients: 0,
    });
    expect(repasSuivant(etat, LE_21_A_18H)).toEqual({
      etiquette: 'Dîner', plat: 'Gratin dauphinois',
      mealId: 42, recetteId: 12, manquants: 0,
    });
  });

  it('rend undefined quand le capteur est indisponible', () => {
    // `Etat.estUtilisable` est le SEUL mécanisme de masquage : le lot ne
    // réintroduit pas de règle propre au garde-manger. Composant non chargé,
    // base verrouillée, HA qui redémarre — même comportement, une seule fois.
    expect(repasSuivant(etatIndisponible('sensor.home_stock_next_meal'), LE_21_A_18H))
      .toBeUndefined();
  });

  it('rend undefined quand aucun repas n\'est prévu', () => {
    // Un plan de repas vide est l'état ORDINAIRE de cette installation.
    // `home_stock` ne le remplira pas par magie : le bloc doit disparaître,
    // et `rendreEntretien` prendre sa place (Task 13).
    expect(repasSuivant(etatAvec('sensor.home_stock_next_meal', '', {
      day: null, slot: null, recipe_id: null, meal_id: null,
      missing_ingredients: 0,
    }), LE_21_A_18H)).toBeUndefined();
  });

  it('étiquette « Demain, déjeuner » quand le jour n\'est pas aujourd\'hui', () => {
    // C'est TOUT ce qui survit de `src/repas.ts` : le choix de l'étiquette
    // reste une décision d'affichage. Le parcours du plan, lui, est mort.
    ...
  });

  it('étiquette chaque créneau en français', () => {
    for (const [slot, attendu] of [['breakfast', 'Petit-déjeuner'], ['lunch', 'Déjeuner'],
                                   ['dinner', 'Dîner'], ['snack', 'Collation']] as const) {
      expect(repasSuivant(etatAvec(..., { slot }), LE_21_A_18H)!.etiquette).toContain(attendu);
    }
  });

  it('survit à un attribut absent sans lever', () => {
    // Un composant plus ancien que le bundle (Task 1 pas encore rechargée
    // dans la maison) ne publie pas `meal_id`. L'écran doit vivre : le bloc
    // s'affiche, il n'est simplement pas validable.
    const r = repasSuivant(etatAvec('sensor.home_stock_next_meal', 'Soupe', { slot: 'dinner' }),
                           LE_21_A_18H);
    expect(r!.mealId).toBeNull();
    expect(r!.recetteId).toBeNull();
  });

  it('ne lève sur AUCUNE forme d\'attribut', () => {
    for (const attributs of [{}, { slot: 42 }, { meal_id: 'douze' }, { day: [] }]) {
      expect(() => repasSuivant(etatAvec('sensor.home_stock_next_meal', 'X', attributs),
                                LE_21_A_18H)).not.toThrow();
    }
  });
});

describe('nombreDlc', () => {
  it('lit le compte dans l\'état de la liste todo', () => {
    // L'état d'une entité `todo` est le nombre d'éléments non cochés — la
    // propriété que `tests/test_entities.py` (Task 1) tient désormais côté
    // composant. Un `binary_sensor` ne pourrait produire qu'un texte sans
    // compte, or le compte est ce qu'on lit de loin.
    expect(nombreDlc(etatAvec('todo.home_stock_expirations', '3', {}))).toBe(3);
  });

  it('rend undefined sur une entité indisponible ou un état illisible', () => {
    // undefined ≠ 0 : zéro fait DISPARAÎTRE la ligne (rien ne périme),
    // undefined la masque aussi mais pour une autre raison. Les confondre
    // n'a pas d'effet visible ici — et c'est justement pourquoi il faut le
    // tester : le jour où la ligne dira « aucun produit à consommer », la
    // différence deviendra visible d'un coup.
    expect(nombreDlc(etatIndisponible('todo.home_stock_expirations'))).toBeUndefined();
    expect(nombreDlc(etatAvec('todo.home_stock_expirations', 'unknown', {}))).toBeUndefined();
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run (depuis `tools/wallpanel-app`) : `npm test -- garde-manger`
Expected: FAIL — `Cannot find module './garde-manger'`

- [ ] **Step 3: Écrire le module**

Créer `src/garde-manger.ts`. **Commentaires et identifiants en français**, comme tout `src/`. En-tête : ce que ce fichier remplace (`src/grocy.ts`), pourquoi il lit des attributs, et le chiffre du trafic économisé — c'est la mémoire de la décision.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run : `npm test -- garde-manger`
Expected: PASS

- [ ] **Step 5: Les deux contrôles du dépôt**

```bash
cd /opt/nivuus/HomeAssistant/data/tools/wallpanel-app && npm test && node outils/verifier-rendu.mjs
```
Expected: **41 fichiers de tests** verts, vérificateur vert. **Rien n'a changé à l'écran** — c'est le résultat attendu d'une tâche purement additive.

- [ ] **Step 6: Commit (dans `wallpanel-app`)**

```bash
git -C /opt/nivuus/HomeAssistant/data/tools/wallpanel-app add src/garde-manger.ts tests/garde-manger.test.ts
git -C /opt/nivuus/HomeAssistant/data/tools/wallpanel-app commit -m "feat: lire le garde-manger dans les attributs d'entités, sans le câbler encore"
```

---

## Task 13: Le bloc central bascule sur `home_stock`

**Dépôt : `wallpanel-app`.** La bascule de source du bloc `repas`. **Aucun mode nouveau** : `blocDefaut: 'repas'` existe, il est mesuré (500 → 574 px, tâche 19 du projet tablette), et il tient le budget de 585 px. On le **resource**.

**Files:**
- Modify: `src/repas.ts`, `src/rendu/defaut.ts`, `src/demarrage.ts`, `outils/verifier-rendu.mjs`
- Test: `tests/repas.test.ts`, `tests/defaut.test.ts`, `tests/demarrage.test.ts`, `tests/orchestration.test.ts`, `tests/pannes.test.ts`

**Interfaces:**
- `src/repas.ts` est **réduit** à ce qui reste une décision d'affichage : l'étiquette. `candidatsRepas`, `resoudreRepasSuivant`, `ResolutionRepas` et ses trois issues `repas`/`aucun`/`muet` **disparaissent avec Grocy** — c'était le parcours d'un plan que la tablette ne parcourt plus.
- `rendreRepasSuivant(r)` garde **exactement** son gabarit : `.mode-bloc` / `.mode-texte` / `.t` / `.v.deux-lignes`, `data-mvt="bloc:repas"`, touchable seulement si une recette est ouvrable. **Effet sur la hauteur : 0.**
- `demarrage.ts` : `chargerPlan` et son `setInterval` de 15 minutes **supprimés**. Le bloc se recalcule depuis `Etat`, donc **au rythme de `subscribe_events`**, gratuitement.

**Ce qui ne change pas, et qu'il ne faut surtout pas « simplifier » au passage.** `rendreEntretien` remplace le bloc repas quand aucun repas n'est planifié — 185 px de fond nu mesurés sur la capture de 21 h 07, parce qu'**un plan de repas vide est l'état ORDINAIRE de cette installation**. `masquerEntretien` continue de retirer la ligne de synthèse correspondante pour ne pas afficher deux fois le même compte. `home_stock` ne remplira pas le planning par magie.

**Le point d'injection du vérificateur.** `verifier-rendu.mjs` de `wallpanel-app` injecte aujourd'hui un `PlanGrocy` complet (`__injecterPlan`) pour mesurer le pire cas **sans dépendre du vrai Grocy**. Le mécanisme est **conservé et renommé** (`__injecterRepas`), et il injecte désormais un repas déjà résolu : le contrôle ne doit pas plus dépendre de l'état réel de `home_stock` qu'il ne dépendait de celui de Grocy. **Sans cela, un planning vide dans la maison ferait passer le contrôle en mesurant un écran sans bloc.**

- [ ] **Step 1: Écrire les tests**

```ts
// defaut.test.ts
it('rend le bloc repas depuis un RepasSuivant de garde-manger', () => { ... });
it("ne rend rien quand le repas est undefined", () => { ... });
it('reste inerte pour un repas sans recette (une note, un produit)', () => {
  // Un bloc qui répond au contact sans rien ouvrir est le bouton mort que
  // ce projet traque partout.
  ...
});
it('garde exactement le gabarit .mode-bloc / .t / .v.deux-lignes', () => {
  // Le contrat de HAUTEUR, tenu par une assertion de structure : c'est ce
  // qui garantit « zéro pixel ajouté » avant même de lancer le navigateur.
  ...
});

// repas.test.ts
it("n'exporte plus resoudreRepasSuivant ni candidatsRepas", () => { ... });
it('choisit l\'étiquette selon le jour et le créneau', () => { ... });

// demarrage.test.ts
it("n'arme plus d'intervalle de 15 minutes pour le plan de repas", () => {
  // La preuve du gain : plus aucune lecture périodique. Si l'intervalle
  // revient un jour, ce test le dit.
  ...
});
it('redessine le bloc quand le capteur change d\'état', () => { ... });

// pannes.test.ts
it('capteur unavailable : l\'écran vit, sans bloc repas', () => {
  // Les lumières, les minuteurs et l'horloge continuent. Mécanisme
  // générique `Etat.estUtilisable`, aucune règle propre au garde-manger.
  ...
});
it('aucun repas planifié : rendreEntretien prend la place, et masquerEntretien retire la ligne', () => {
  ...
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run : `npm test -- repas defaut demarrage pannes`
Expected: FAIL

- [ ] **Step 3: Basculer la source**

Retirer de `demarrage.ts` : `chargerPlan`, `appliquerPlan`, `lireRecetteGrocy` pour le plan, l'intervalle de 15 minutes, `ClientGrocy.chargerPlan`, `recettesInjectees` pour le plan. **`src/grocy.ts` reste sur le disque** — sa suppression est la Task 17, quand plus rien ne l'appelle.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run : `npm test -- repas defaut demarrage pannes`
Expected: PASS

- [ ] **Step 5: Le vérificateur de rendu — la seule preuve qui compte**

Run : `node outils/verifier-rendu.mjs`
Expected: vert, **et aucune constante de mise en page n'a bougé**. jsdom ne calcule aucune mise en page : c'est le seul outil qui dit « ça tient ». En cas d'échec, **retirer quelque chose** — jamais agrandir le cadre.

- [ ] **Step 6: Commit**

```bash
git -C .../wallpanel-app add src/repas.ts src/rendu/defaut.ts src/demarrage.ts outils/verifier-rendu.mjs tests/
git -C .../wallpanel-app commit -m "feat: le bloc repas de la cuisine vient de home_stock, plus de Grocy"
```

---

## Task 14: La vue `#recette` — `recipe/get`, `meal/preview`, `meal/validate`

**Dépôt : `wallpanel-app`.** Le plus gros morceau du raccordement : `src/recette.ts` (4,5 ko), `src/rendu/recette.ts` (34,8 ko), `tests/rendu-recette.test.ts` (33,6 ko).

**Files:**
- Modify: `src/recette.ts`, `src/rendu/recette.ts`, `src/demarrage.ts`, `outils/verifier-rendu.mjs`
- Test: `tests/recette.test.ts`, `tests/rendu-recette.test.ts`, `tests/demarrage.test.ts`

**Interfaces:**
- Deux lectures **ponctuelles**, à l'ouverture de la vue, par `Connexion.envoyerCommande` — **jamais périodiques**, c'est la leçon de `src/grocy.ts` :
  - `home_stock/recipe/get` → `{ recipe, steps, ingredients }`. Les `steps` portent leurs `instructions` déjà imbriquées ; chaque ingrédient porte `display_amount` et `product_name`.
  - `home_stock/meal/preview` → le plan de décrément **et** ce qui bloque (`lines`, `by_hand`, `dish`, `blocking`). **Il n'écrit absolument rien** et tourne sur une connexion en lecture.
- `decouperPages` est **conservé** et gagne une seconde entrée : une liste d'étapes structurées, en plus du HTML découpé en `div.page-recipes`. Le rendu tient le budget de hauteur et il est testé — **seule son entrée change**.
- Les minuteurs `#Nom:secondes` sont **conservés** : ils vivent dans le texte de l'étape et le mécanisme marche.

**Décision : le panneau d'ingrédients devient une LECTURE.** Le geste « retirer cet ingrédient » (`cx.appelerService('grocy', 'consume_product_from_stock', …)`, `demarrage.ts` l. 968) **disparaît et n'est pas remplacé**. La spec ne laisse que **trois gestes** à la tablette (§ 8.7), et celui-là n'en fait pas partie : retirer une quantité est un **choix** (combien, sur quel lot), et tout geste qui demande un choix vit dans le panneau et **seulement** là. `meal/preview` alimente le panneau : chaque ingrédient s'affiche avec sa quantité lisible et, s'il figure dans `blocking`, la mention qu'il manque. **Un bouton en moins, c'est de la hauteur en moins — jamais un problème de budget.**

**« Terminer » : deux appuis, et un libellé qui dit la vérité.** `home_stock/meal/validate` **n'est pas réversible** — le lot 3 l'écrit : *« Cook, then eat. Not reversible at lot 3, and the screen says so. »* Le lot 4 a ajouté `meal/correct`, mais depuis le journal du panneau, pas au mur. Le second appui porte donc **« Terminer — le stock sera décrémenté »**, jamais un « Toucher pour confirmer » générique. Trois défenses en profondeur, toutes déjà écrites : `meal/preview` rend le plan à l'armement **sans rien écrire** ; `envoyerCommande` rend une promesse, donc un refus (`InsufficientStock`) est traduit en français par `messages.py` et **affichable** ; et le garde `estHorsLigne` s'applique comme à toute autre écriture.

**Décision sur le hors-ligne : la tablette n'a pas de file.** Le panneau en a une parce qu'on scanne dans un magasin sans réseau ; une tablette murale est à **trois mètres du routeur, qui est le serveur HA**. Un geste refusé hors ligne est **refusé visiblement**, jamais mis en attente : rejouer une validation de repas une heure plus tard, sans témoin, décrémenterait un stock à l'aveugle. Les commandes portent quand même une `idempotency_key` — toutes l'acceptent — parce qu'une reconnexion websocket peut faire douter d'un envoi.

- [ ] **Step 1: Écrire les tests**

```ts
// recette.test.ts
it('découpe des étapes structurées en pages', () => { ... });
it('découpe toujours un HTML en div.page-recipes', () => {
  // L'ancienne entrée reste supportée : les fixtures de rendu, longues et
  // précieuses, ne se réécrivent pas pour une bascule de source.
  ...
});
it('reconnaît toujours les minuteurs #Nom:secondes dans une étape structurée', () => { ... });
it('une recette sans étape reste une page', () => { ... });

// rendu-recette.test.ts
it('affiche les ingrédients en LECTURE, sans bouton de retrait', () => {
  expect(boutons(vue, 'Retirer')).toHaveLength(0);
});
it('signale un ingrédient manquant à partir de `blocking`', () => { ... });
it('le second appui de « Terminer » porte « le stock sera décrémenté »', () => {
  // Un libellé générique sur un geste irréversible est un piège. Ce test
  // est la seule chose qui empêche qu'il redevienne générique.
  ...
});
it('un seul emplacement armé à la fois', () => { ... });
it('aucun geste : ni swipe, ni appui long', () => { ... });

// demarrage.test.ts
it('ouvre la vue en envoyant recipe/get puis meal/preview, une fois chacun', () => {
  expect(commandesEnvoyees()).toEqual([
    { type: 'home_stock/recipe/get', recipe_id: 12 },
    { type: 'home_stock/meal/preview', meal_id: 42 },
  ]);
});
it('ne relit jamais périodiquement', () => {
  // La leçon de src/grocy.ts, tenue par un test plutôt que par un commentaire.
  avancerHorloge(60 * 60_000);
  expect(commandesEnvoyees()).toHaveLength(2);
});
it('« Terminer » confirmé envoie meal/validate avec une idempotency_key', () => { ... });
it('un refus serveur n\'efface RIEN de l\'écran et affiche le message français', () => {
  // C'est tout l'intérêt d'écrire par websocket plutôt que par
  // `appelerService`, qui est un envoi sans réponse : sur un écran où l'on
  // retire la ligne de façon optimiste, savoir que l'écriture a échoué
  // n'est pas un luxe.
  ...
});
it('hors ligne, « Terminer » est refusé VISIBLEMENT et rien n\'est mis en file', () => { ... });
it("n'appelle plus aucun service grocy", () => {
  expect(servicesAppeles().filter((s) => s.domaine === 'grocy')).toHaveLength(0);
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent** — `npm test -- recette rendu-recette demarrage`
- [ ] **Step 3: Écrire le raccordement**

Si `recipe/get` ne rend pas les étapes sous une forme directement utilisable par `decouperPages`, **c'est la tablette qui s'adapte**. Le lot 6 n'ajoute **aucune** commande websocket dont le seul but serait de pré-mâcher un rendu.

Renommer les points d'injection du vérificateur (`__injecterIngredients` → alimenté par une réponse `meal/preview` de doublure) pour que le contrôle ne touche jamais l'instance réelle sur ce chemin.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent** — `npm test -- recette rendu-recette demarrage`
- [ ] **Step 5: Le vérificateur**

Run : `node outils/verifier-rendu.mjs`
Expected: vert. La vue recette **perd** un bouton par ingrédient : la hauteur baisse, elle ne monte pas.

- [ ] **Step 6: Vérifier que les tests ont des dents**

Remplacer le libellé du second appui par « Toucher pour confirmer » : le test de libellé doit tomber. Rendre `meal/preview` appelé dans un `setInterval` : `ne relit jamais périodiquement` doit tomber. Remettre le code correct.

- [ ] **Step 7: Commit**

```bash
git -C .../wallpanel-app add src/recette.ts src/rendu/recette.ts src/demarrage.ts outils/verifier-rendu.mjs tests/
git -C .../wallpanel-app commit -m "feat: la vue cuisine lit home_stock et valide le repas en deux appuis"
```

---

## Task 15: `pieces.ts` et `cochage.ts` — la ligne DLC, les courses, les commandes

**Dépôt : `wallpanel-app`.** La tâche qui fait apparaître le garde-manger sur l'accueil. **Zéro pixel ajouté** : que des attributs et des remplacements de chaîne.

**Files:**
- Modify: `src/pieces.ts`, `src/cochage.ts`, `src/rendu/maison.ts`
- Test: `tests/pieces.test.ts`, `tests/cochage.test.ts`, `tests/taches.test.ts`, `tests/maison.test.ts`

**Interfaces — cuisine :**

| Élément | Avant | Après |
|---|---|---|
| Commande « Courses » | `todo.grocy_shopping_list`, tuile informative | `todo.home_stock_shopping`, **`vue: '#taches'`** |
| Commande « Recette » | `todo.grocy_meal_plan`, `vue: '#recette'` | `sensor.home_stock_next_meal`, `vue: '#recette'` |
| « Aspirer ici », « Purificateur » | inchangées | inchangées |
| `listesTachesExtra` | `['todo.grocy_shopping_list']` | `['todo.home_stock_shopping']` |
| `synthese` | 4 entrées | **5** — `todo.home_stock_expirations > 0`, « {etat} produit{s} à consommer », `perso: true` |
| `extrasMaison` « Scanner » | `/local/grocy-scanner.html` | `lien: '/home-stock'`, entité `sensor.home_stock_next_meal` |

**Les deux entités changées gardent leur rôle d'indicateur de disponibilité** : muettes, elles font masquer la tuile par le filtre générique de `rendu/corps.ts`. **`vue: '#taches'` est le seul enrichissement fonctionnel** : aujourd'hui la tuile affiche un compte sur lequel on ne peut rien faire, et la vue « Tâches » ne s'atteint qu'en touchant la ligne de synthèse. Ça ne coûte rien (navigation interne, jamais un appel HA) et ça supprime un cul-de-sac.

**Pourquoi `todo.` et pas `binary_sensor.` pour la DLC.** L'état d'une entité `todo` est le **nombre d'éléments non cochés** ; `binary_sensor.home_stock_expirations` ne vaut que `on`/`off` et ne pourrait produire qu'un texte sans compte — or le compte est ce qu'on lit de loin. **Bonus mécanique décisif** : `listesTachesPiece` (`cochage.ts`) collecte automatiquement toute entrée de `synthese` dont l'entité commence par `todo.` Déclarer cette ligne suffit donc à faire apparaître les lots qui périment **dans la vue « Tâches », cochables en deux appuis**, sans une ligne de plus. Et cocher y veut dire **mangé** (`consume_batch`), ce qui est le geste juste devant un frigo.

**Pourquoi pas une alerte.** `alertes.ts` pose un critère d'admission **cumulatif** : *anormale* **et** *traitable en quelques minutes depuis la maison*. Une DLC échoue aux deux — elle dure des jours. Le fichier raconte ce que coûte l'erreur : la batterie de la e208 a « confisqué les trois écrans une journée entière » pour avoir enfreint le second critère. **Le garde-manger ne produit aucune alerte plein écran.**

**Interfaces — salon, et l'arbitrage qu'il impose.** Le salon reçoit **la ligne DLC et rien d'autre** : la tablette du salon est à l'entrée (c'est pour ça que « Porte » y est épinglée), et « 3 produits à consommer » y est utile au moment précis où on part faire les courses. La répétition **entre** tablettes est explicitement permise ; la règle « pas de donnée en double » s'applique **par tablette**.

Mais `listesTachesPiece` collecte **automatiquement** toute entité `todo.` de `synthese` — déclarer la ligne au salon y ferait donc aussi apparaître la liste des DLC dans sa vue « Tâches », ce que la spec refuse (« sa vue Tâches n'a pas à porter une liste qu'on ne coche pas d'un canapé »). **Arbitrage retenu : un champ `horsTaches?: boolean` sur `EntreeSynthese`**, honoré par `listesTachesPiece`, posé **uniquement** sur la ligne DLC du salon. Un champ, un filtre, un test — et la table par pièce de la spec devient littéralement vraie.

**L'ordre des listes de la cuisine devient une décision.** La vue « Tâches » passe de deux listes à trois : **entretien, puis DLC, puis courses**. `listesTachesPiece` respecte l'ordre de `synthese` puis celui de `listesTachesExtra` : déclarer la ligne DLC **après** `todo.maintenance` suffit. **Une DLC passe avant une course** : l'une a une échéance, l'autre non.

- [ ] **Step 1: Écrire les tests**

```ts
// pieces.test.ts
it('la cuisine déclare todo.home_stock_shopping et plus aucune entité grocy', () => { ... });
it('la commande « Courses » ouvre la vue Tâches', () => { ... });
it('« Recette » garde son indicateur de disponibilité', () => {
  // Muette, la tuile se masque par le filtre générique de rendu/corps.ts.
  // Sans entité, elle resterait affichée et ne ferait rien.
  ...
});
it('la cuisine a toujours QUATRE commandes', () => {
  // 574 px sur un budget de 585 : une rangée de plus déborde.
  expect(PIECES.cuisine.commandes).toHaveLength(4);
});
it('« Aspirer ici » reste identique à aspirateurMaison, champ par champ', () => { ... });
it('le salon a la ligne DLC et RIEN d\'autre du garde-manger', () => { ... });
it('le bureau n\'a aucune entité home_stock', () => {
  // Le refus le plus facile du lot, et il faut le tenir : un lot
  // « surfaces » a une pente naturelle vers « mettons-le partout ».
  ...
});

// cochage.test.ts
it('la cuisine rend trois listes, dans l\'ordre entretien, DLC, courses', () => {
  expect(listesTachesPiece(PIECES.cuisine)).toEqual([
    'todo.maintenance', 'todo.home_stock_expirations', 'todo.home_stock_shopping',
  ]);
});
it('le salon ne rend PAS la liste des DLC malgré sa ligne de synthèse', () => {
  expect(listesTachesPiece(PIECES.salon)).toEqual(['todo.maintenance']);
});
it('libelleListe connaît les deux nouvelles listes', () => {
  expect(libelleListe('todo.home_stock_shopping')).toBe('Courses');
  expect(libelleListe('todo.home_stock_expirations')).toBe('À consommer');
});
it('une liste inconnue garde un sous-titre lisible', () => { ... });

// taches.test.ts
it('« +N » apparaît au bon seuil, sans qu\'une tâche disparaisse en silence', () => {
  // `repartirTaches` réserve déjà la dernière ligne : le débordement est
  // structurellement impossible. Mais cette ligne devient FRÉQUENTE au lieu
  // d'exceptionnelle avec trois listes — c'est le point de vigilance
  // mesurable du lot, et il se teste.
  ...
});
it('le budget de la vue Tâches tient : 6×64 + 5×8 + 112 = 536 ≤ 585', () => { ... });
it('cocher demande toujours deux appuis', () => { ... });
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent** — `npm test -- pieces cochage taches maison`
- [ ] **Step 3: Écrire les remplacements**

`cochage.ts`, la table de libellés :

```ts
const LIBELLES_LISTE: Record<string, string> = {
  'todo.maintenance': 'Entretien',
  'todo.travail': 'Travail',
  'todo.home_stock_shopping': 'Courses',
  'todo.home_stock_expirations': 'À consommer',
};
```

**On garde `todo.update_item` pour cocher** — seule exception à la règle « la tablette écrit par websocket ». Trois raisons : c'est déjà écrit, testé et **partagé avec `todo.maintenance` et `todo.travail`**, deux listes qui ne sont pas `home_stock` et ne le seront jamais ; `ShoppingTodoList.async_update_todo_item` fait exactement la bonne chose (cocher vaut « je l'ai », jamais « c'est en stock », et un `uid` périmé est un no-op explicite) ; et écrire un `home_stock/list/check` en parallèle donnerait **deux façons de cocher la même ligne** sur la même dalle, avec deux traitements d'erreur. La lecture reste `Connexion.listerTaches` (`todo/item/list`), qui marche déjà sur ces entités **sans une ligne de plus**.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent** — `npm test -- pieces cochage taches maison`
- [ ] **Step 5: Le vérificateur — la tâche la plus à risque du lot**

Run : `node outils/verifier-rendu.mjs`
Expected: vert. **Deux points à surveiller nommément :**
1. La cuisine passe de 4 à **5** entrées de synthèse. `.synthese-texte` est borné à 2 lignes (`-webkit-line-clamp`) et chaque écart supplémentaire coûtait **+16 px** avant ce plafond — c'est ce qui avait fait déborder le mode voiture (574 → 590 px). Le contrôle doit rester vert **et** ne signaler aucun texte tronqué.
2. La vue « Tâches » de la cuisine passe à trois listes. Le « +N » doit apparaître, et **aucune tâche ne doit disparaître sans être comptée**.

En cas d'échec : **retirer**. La première chose à retirer est la ligne DLC du salon, pas une ligne de la cuisine.

- [ ] **Step 6: Vérifier que le test a des dents**

Retirer `horsTaches` de la ligne du salon : `le salon ne rend PAS la liste des DLC` doit tomber. Déclarer la ligne DLC **avant** `todo.maintenance` : le test d'ordre doit tomber. Remettre le code correct.

- [ ] **Step 7: Commit**

```bash
git -C .../wallpanel-app add src/pieces.ts src/cochage.ts src/rendu/maison.ts tests/
git -C .../wallpanel-app commit -m "feat: la ligne DLC, la liste de courses et les commandes de la cuisine passent à home_stock"
```

---

## Task 16: Le retrait de Grocy — `src/grocy.ts` disparaît

**Dépôt : `wallpanel-app`.** À ce point, plus rien n'appelle `src/grocy.ts`. **Laisser `src/grocy.ts` et `home_stock` cohabiter donnerait deux plans de repas et deux listes de courses sur la même dalle** — précisément la règle « pas de donnée en double sur la même tablette » que ce projet applique sans exception. Le lot ne se termine pas avant cette tâche.

**Files:**
- Delete: `src/grocy.ts`, `tests/grocy.test.ts`
- Modify: `src/demarrage.ts`, `src/rendu/defaut.ts`, `src/rendu/recette.ts`, `src/rendu/maison.ts`, `src/rendu/corps.ts`, `src/geste.ts`, `src/interaction.ts`, `src/recette.ts`, `src/recette-en-cours.ts`, `src/styles/base.css`, `README.md`
- Test: `tests/pieces.test.ts`

**Les treize fichiers de `src/` qui mentionnent Grocy aujourd'hui** (relevé du 2026-08-21) : `geste.ts`, `repas.ts`, `grocy.ts`, `recette.ts`, `demarrage.ts`, `interaction.ts`, `recette-en-cours.ts`, `pieces.ts`, `styles/base.css`, `rendu/maison.ts`, `rendu/corps.ts`, `rendu/defaut.ts`, `rendu/recette.ts`. La plupart ne portent plus que des **commentaires** — et un commentaire qui parle d'une source morte est pire qu'absent : il envoie la prochaine personne lire un fichier qui n'existe plus.

**L'assertion de fin de parcours.** Un test qui scanne **tout `src/`** — le seul moyen d'attraper un reliquat dans un fichier oublié :

```ts
it("aucune chaîne 'grocy' ne subsiste dans src/", () => {
  // Une assertion sur le RÉPERTOIRE, pas sur une liste de fichiers : une
  // liste de fichiers ne voit pas celui qu'on a oublié d'y mettre.
  // Insensible à la casse : « Grocy », « grocy_shopping_list », « GrocyPlan ».
  const fautifs: string[] = [];
  for (const fichier of parcourir('src/')) {
    if (/grocy/i.test(readFileSync(fichier, 'utf8'))) fautifs.push(fichier);
  }
  expect(fautifs).toEqual([]);
});
```

**Ce qui reste servi, et qu'on ne touche pas** : `/local/grocy-scanner.html` et `/local/grocy-recipes.html` restent en place tant que le lot 7 n'a pas conclu. Simplement, **plus aucune tablette n'y renvoie**. Le conteneur Grocy tourne toujours ; ses **données** sont l'affaire du lot 7.

- [ ] **Step 1: Écrire le test de scan**

Dans `tests/pieces.test.ts`, en tête de fichier — il est le gardien du lot, il doit être facile à trouver.

- [ ] **Step 2: Lancer, vérifier qu'il échoue** — `npm test -- pieces` → FAIL, avec la liste des fichiers fautifs. **Cette liste est la liste de travail de la tâche.**
- [ ] **Step 3: Supprimer et nettoyer**

```bash
git -C .../wallpanel-app rm src/grocy.ts tests/grocy.test.ts
```

Puis reprendre chaque fichier de la liste : les commentaires qui expliquaient une décision **restent**, réécrits pour dire ce qui est vrai maintenant (`src/garde-manger.ts` au lieu de `src/grocy.ts`, `sensor.home_stock_next_meal` au lieu de `todo.grocy_meal_plan`). **On ne supprime pas une explication : on la met à jour.** Les chiffres mesurés (3,8 Mo/jour, 87 recettes, 62 tags sur 98) restent, avec leur date — ils justifient des seuils encore en vigueur.

- [ ] **Step 4: Rafraîchir le `README.md`**

Le nombre de fichiers de tests (**33 → le compte réel**) et la disparition de Grocy de la description de l'app.

- [ ] **Step 5: Lancer, vérifier que tout passe**

```bash
cd /opt/nivuus/HomeAssistant/data/tools/wallpanel-app && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert, **`grocy.test.ts` en moins**, `garde-manger.test.ts` en plus.

- [ ] **Step 6: Commit**

```bash
git -C .../wallpanel-app add -A
git -C .../wallpanel-app commit -m "chore: src/ ne connaît plus Grocy — le client, ses appelants et ses commentaires"
```

---

## Task 17: Les mesures — salve et régime établi

**Dépôt : `wallpanel-app`.** **Obligation du lot**, et la dernière étape avant le déploiement. Ces deux mesureurs **ne déploient pas**.

**Files:** aucun, sauf si une mesure impose une correction.

**Pourquoi ce n'est pas décoratif.** Avant la coalescence des redessins, ce projet mesurait **1712 recalculs de style à chaque connexion websocket** — de quoi faire tuer Fully par Android sur une page qui *rendait juste*. Une page correcte peut être une page qui tue son navigateur : **les tests et le vérificateur de rendu ne voient pas ce défaut-là.**

- [ ] **Step 1: Relever l'état d'avant, sur le bundle DÉPLOYÉ**

```bash
cd /opt/nivuus/HomeAssistant/data/tools/wallpanel-app
node outils/mesurer-salve.mjs cuisine        # le bundle en place, celui d'avant le lot
node outils/mesurer-rendus.mjs cuisine 300
```

Noter les deux chiffres. **C'est la seule référence disponible** : après la Task 18, le bundle d'avant n'existe plus.

- [ ] **Step 2: Mesurer `src/`, celui du lot**

```bash
node outils/mesurer-salve.mjs cuisine --src
node outils/mesurer-rendus.mjs cuisine 300
```

- [ ] **Step 3: Comparer, et décider**

| Mesure | Attendu |
|---|---|
| Coût des douze premières secondes | **En baisse** — une lecture HTTP de 3,8 Mo/jour et un `setInterval` de 15 minutes ont disparu |
| Redessins en régime établi | **Stable ou en baisse** — le bloc repas suit maintenant `subscribe_events`, déjà coalescé, au lieu d'un intervalle propre |

Une **hausse** de l'une des deux est un défaut à corriger **avant** la Task 18, pas une observation à consigner. La cause la plus probable serait une lecture ajoutée dans un chemin de redessin plutôt qu'à l'ouverture d'une vue.

- [ ] **Step 4: Le contrôle complet, une dernière fois avant le mur**

```bash
cd /opt/nivuus/HomeAssistant/data/tools/wallpanel-app && npm test && node outils/verifier-rendu.mjs
./scripts/test.sh -q
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: **les cinq suites vertes**, 70 exécutions côté panneau. **Tout ce qui peut être vérifié avant le build l'a maintenant été.**

- [ ] **Step 5: Consigner les chiffres**

Dans le message de commit, et repris en Task 19 dans `docs/exploitation.md` — un chiffre mesuré qui n'est écrit nulle part est un chiffre à remesurer.

```bash
git -C .../wallpanel-app commit --allow-empty -m "chore: mesures salve et rendus, avant/après — <chiffres>"
```

---

## Task 18: `npm run build` de `wallpanel-app` — LE DÉPLOIEMENT DU MUR

**Dépôt : `wallpanel-app`.** ⚠️ **Cette tâche déploie sur les trois tablettes de la maison. Elle ne fait que ça.**

**Elle ne se lance que si toutes les conditions de la Task 17 sont vertes.** Si l'une ne l'est pas, on ne construit pas : on répare.

```json
"build": "npm run jetons && rollup -c && node scripts/versionner.mjs"
```

`rollup -c` écrit dans `config/www/wallpanel/` — le dossier que Home Assistant sert aux trois tablettes — et `versionner.mjs` incrémente le `?v=` des trois pages HTML. **Il n'y a aucune étape de validation entre ce build et les trois écrans de la maison.** La règle « un build est un déploiement » vaut ici **en pire** que pour le panneau : le panneau se recharge quand on ouvre la page, la tablette de la cuisine tourne 24 h sur 24 et sert d'horloge.

**Files:** `config/www/wallpanel/*` (artefacts de build — **jamais édités à la main**), `src/*.html` versionnés.

- [ ] **Step 1: Vérifier une dernière fois que rien n'attend**

```bash
git -C /opt/nivuus/HomeAssistant/data/tools/wallpanel-app status --porcelain
```
Expected: propre. **Construire un arbre sale, c'est déployer ce qu'on n'a pas relu.**

- [ ] **Step 2: Construire — une fois**

```bash
cd /opt/nivuus/HomeAssistant/data/tools/wallpanel-app && npm run build
```

- [ ] **Step 3: Vérifier ce qui a été écrit**

```bash
git -C /opt/nivuus/HomeAssistant status --porcelain config/www/wallpanel/
```
Attendu : `wallpanel.js`, `wallpanel.css` et les **trois** pages `salon.html`, `bureau.html`, `cuisine.html` (leur `?v=` a changé). **Rien d'autre.**

- [ ] **Step 4: Vérifier le bundle RÉELLEMENT en place**

```bash
node outils/verifier-rendu.mjs --deploye
```
Expected: mêmes scénarios verts, cette fois sur le bundle construit et minifié. C'est le seul moment du lot où `--deploye` a un sens.

- [ ] **Step 5: Faire recharger les trois tablettes**

Le **seul** geste de contrôle autorisé sur l'instance vivante, dans cet ordre, pour chaque pièce :

1. `button.tablette_<piece>_vider_le_cache_du_navigateur` — la WebView Fully peut continuer à servir l'ancien bundle ;
2. `button.tablette_<piece>_load_start_url`.

Aucun `docker compose`, aucun redémarrage, aucun rechargement d'intégration.

- [ ] **Step 6: Contrôle visuel**

Lire `image.tablette_<piece>_capture_d_ecran` pour les trois pièces. Après un rechargement, la tablette met **plusieurs secondes** à peindre : on obtient des frames partiels. **Se fier à l'heure de l'horloge affichée, pas à `frame_timestamp`** (peu fiable).

Ce qu'on vérifie, pièce par pièce :

| Pièce | Attendu |
|---|---|
| **Cuisine** | Le bloc central montre le repas suivant **ou** les tâches d'entretien si rien n'est planifié ; la ligne de synthèse peut porter « n produits à consommer » ; les quatre commandes sont là ; « Courses » ouvre la vue Tâches |
| **Salon** | Rien de neuf **sauf** la ligne de synthèse DLC ; sa vue « Tâches » ne porte **que** l'entretien |
| **Bureau** | **Strictement rien de changé** |

- [ ] **Step 7: Commit**

```bash
git -C /opt/nivuus/HomeAssistant/data/tools/wallpanel-app add -A
git -C /opt/nivuus/HomeAssistant/data/tools/wallpanel-app commit -m "chore: build — la cuisine passe à home_stock sur les trois tablettes"
```

> **Le retour arrière, s'il faut :** `git revert` dans `wallpanel-app`, puis `npm run build`. **Il n'y a pas d'autre chemin** — les dashboards `.storage/lovelace.wallpanel_*` de secours sont périmés depuis le 2026-08-02 et les modifier n'a aucun effet.

---

## Task 19: Le bundle du panneau, la documentation, les amendements de spec

**Dépôt : `meal`.** La dernière tâche. Elle construit le bundle du panneau — **une seule fois, quand tout le reste est vert**, règle du lot 1 — et écrit ce que le propriétaire doit faire de ses mains.

**Files:**
- Modify: `docs/exploitation.md`
- Build: `custom_components/home_stock/panel/home-stock-panel.js`

- [ ] **Step 1: Écrire la section « Lot 6 — les quatre surfaces »**

Dans `docs/exploitation.md`, dans le ton des sections précédentes : ce que le propriétaire doit faire, et ce qui se répare.

1. **Installer les phrases vocales.** Copier `custom_sentences/fr/home_stock.yaml` dans `config/custom_sentences/fr/`, coller le bloc `intent_script` de `packages/home_stock_intents.yaml` dans `configuration.yaml` (ou charger le fichier comme paquet), recharger. **La liste des sept phrases, en clair, avec leurs variantes et leur réponse attendue** — c'est le document qu'on relit quand une phrase ne marche pas, et il doit être rejouable à la main en trois minutes.
2. **Le blueprint `courses_bleuenn.yaml`** : à importer, avec son heure et son agent. Rappeler que les trois blueprints du composant sont **livrés, jamais installés**.
3. **Ce que la tablette de la cuisine montre maintenant, et ce qu'elle ne montre pas** — la table des refus (kcal, €, objectifs, ruptures, planning de la semaine, estimation du panier, tickets, piles faibles, garanties), parce que *« pourquoi les kcal ne sont pas au mur ? »* est une question qui reviendra. Sur 343 × 585 px, **la conception consiste à refuser.**
4. **La procédure de déploiement de `wallpanel-app`**, avec l'avertissement **en première ligne** : `npm run build` **déploie**. Puis vider le cache, recharger l'URL, regarder la capture — et se fier à l'heure de l'horloge affichée, pas à `frame_timestamp`.
5. **Le retour arrière**, en une phrase : `git revert` dans `wallpanel-app`, puis `npm run build`. Pas d'autre chemin ; les dashboards `.storage` de secours sont périmés.
6. **Le rappel du lot 7** : Grocy tourne toujours, `/local/grocy-scanner.html` et `/local/grocy-recipes.html` restent servis, **plus aucune tablette n'y renvoie**. Les données Grocy et les six *chores* (litière, fontaine, croquettes, poubelles) sont le lot 7.
7. **Les chiffres de la Task 17**, avant/après.

- [ ] **Step 2: Écrire les amendements aux specs précédentes**

Toujours dans `docs/exploitation.md`, sous « Amendements aux specs précédents » — **ce sont des amendements de spec, pas du code**, et les documents d'origine ne sont pas réécrits (usage des lots précédents) :

| Spec | Ligne fausse | Correction |
|---|---|---|
| Lot 0, § 5.1 | « Liste de courses cochable (`todo`) » en colonne Lovelace | Vrai pour le téléphone, le PC et l'app mobile ; **faux pour les tablettes murales**, qui ne lisent aucun dashboard |
| Lot 0, § 5.1 | « Boutons de validation (`button`, scripts) » | **Abandonné.** Aucune entité `button` n'a jamais été créée : valider un repas demande des portions et des ingrédients à ignorer — c'est un écran, jamais un bouton |
| Lot 4, § 18 | « La tablette de la cuisine affiche la liste avec la carte `todo-list` native » | **Faux.** Elle l'affiche via `listesTachesExtra` dans `wallpanel-app` |
| Lot 5, § 17 | « Une ligne *n* piles faibles si elle se révèle utile » | Elle ne l'est pas : doublon avec « {n} tâches d'entretien », qui les compte déjà sur les trois tablettes |
| Lot 5, § 18 | « Alerte de fin de garantie annoncée à la voix » | **Refusée.** Une fin de garantie se traite avec une facture sous les yeux |

Et la répartition qui vaut à partir du lot 6 : **Lovelace** (cartes natives sur les entités, aucune carte livrée par `home_stock` — le dashboard appartient au propriétaire) · **Panneau** (les dix-sept écrans, en étroit et en large) · **Tablettes murales** (`wallpanel-app` : bloc repas, ligne DLC, vue « Tâches », vue recette) · **Voix** (sept phrases).

- [ ] **Step 3: Construire le bundle du panneau — une fois**

```bash
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm run build
```

- [ ] **Step 4: Vérifier ce qui a été écrit**

```bash
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain custom_components/home_stock/panel/
```
**Un seul fichier doit avoir changé.**

- [ ] **Step 5: Vérifier le bundle réellement en place**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs --deploye`
Expected: mêmes scénarios verts, cette fois sur le bundle construit.

- [ ] **Step 6: Les cinq suites, une dernière fois**

```bash
./scripts/test.sh -q
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
cd /opt/nivuus/HomeAssistant/data/tools/wallpanel-app && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert. Côté panneau, **70 exécutions**.

- [ ] **Step 7: Commit**

```bash
git -C /opt/nivuus/HomeAssistant/data/meal add docs/exploitation.md custom_components/home_stock/panel/home-stock-panel.js
git -C /opt/nivuus/HomeAssistant/data/meal commit -m "chore: the four surfaces documented, spec amendments, and the built panel"
```

---

## Ce que ce plan ne fait pas

Rappel, pour qu'aucune tâche n'aille les chercher :

- **La reprise des données Grocy et l'extinction du conteneur** — **lot 7, sans exception.** Le lot 6 débranche les *surfaces* ; les *données* restent, le conteneur tourne, `/local/grocy-scanner.html` et `/local/grocy-recipes.html` restent servis. Aucune écriture dans Grocy, jamais.
- **Les six *chores* Grocy** (litière, fontaine, croquettes, poubelles) — trou de la feuille de route repéré au lot 5, tranché au lot 7. Ce sont des tâches **périodiques**, et `todo.maintenance` est piloté par des conditions.
- **Une souscription `home_stock/subscribe` depuis la tablette.** `envoyerCommande` résout au premier `result` et **oublie l'`id`** : les événements suivants ne seraient vus par personne. Tout ce que la tablette affiche vit dans un état ou un attribut, donc arrive déjà par `subscribe_events`. **La tablette est un client de plus, pas un client privilégié.**
- **Une file hors-ligne sur la tablette.** Trois mètres du routeur, qui est le serveur HA. Rejouer une validation de repas sans témoin est **pire** que la refuser.
- **Un client HTTP vers `home_stock`.** Il n'y en a pas, et il n'en faut pas : `home_stock` n'expose aucune vue HTTP. C'est précisément ce qui a rendu `src/grocy.ts` fragile.
- **Des capteurs template dans `config/custom_templates/`.** `wallpanel.jinja` est **périmé** et n'alimente plus que des capteurs inutilisés. Le ressusciter ajouterait un troisième endroit où une règle métier vit.
- **Une carte Lovelace ou un dashboard `wallpanel_*`.** Les `.storage/lovelace.wallpanel_*` sont périmés : les modifier n'a **aucun effet** sur les tablettes. Et `home_stock` ne livre **jamais** de carte : les entités sont là, le dashboard appartient au propriétaire — même contrat que les blueprints.
- **Un mode principal nouveau dans `modes.ts`.** Un mode répond à un **moment**, pas à un état ; « il y a trois choses à acheter » n'a pas de fin. Le mode `recette` et le bloc `blocDefaut: 'repas'` existaient : on les **resource**.
- **Une alerte plein écran pour une DLC.** `alertes.ts` exige *anormal* **et** *traitable en quelques minutes*. Une DLC échoue aux deux.
- **Un bloc garde-manger au bureau**, et quoi que ce soit d'autre que la ligne DLC au salon. **La retenue est le travail principal d'un lot « surfaces ».**
- **Les kcal, les €, les objectifs, les ruptures, le planning de la semaine, l'estimation du panier, les tickets, les piles faibles et les garanties sur les tablettes.** Une comptabilité se lit assise ; un dépassement au mur à l'heure du dîner est un reproche.
- **Le geste « retirer cet ingrédient » sur la tablette.** Retirer une quantité est un **choix** — et tout geste qui demande un choix vit dans le panneau, et seulement là.
- **Jeter (`waste`), retirer une ligne de courses, consommer un produit au hasard, planifier un repas — à la voix.** Non bornés ou irréversibles. Un `removed_at` dit par erreur **empêche la ligne de revenir**, silencieusement, à chaque réconciliation : c'est le pire cas de tout le lot.
- **La vue dense sur `scanner`, `fiche`, `panier`, `rangement`, `session`, `recettes`, `recette`, `validation`, `consommation`.** Écrans de magasin ou vues debout : six variantes de plus à vérifier pour zéro gain.
- **Un second bundle, un second vérificateur, une fusion de `wallpanel-app` et du panneau.** Deux cadres, deux moteurs, deux jeux de seuils, deux authentifications. **Ce sont deux applications : elles partagent un modèle, pas un rendu.**
- **Toute migration de schéma, table, motif de mouvement ou capteur nouveau.** *Un lot de surfaces qui touche au modèle de données est un lot qui a mal lu ce qui existait.*
- **Redémarrer Home Assistant, recharger l'intégration, ou installer quoi que ce soit.** Les deux constructions prévues sont les seules choses que ce plan met en production. Importer les blueprints, coller les intents et recharger restent **le geste du propriétaire**.
