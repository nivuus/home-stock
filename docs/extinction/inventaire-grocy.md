# Inventaire — ce qui casse, ce qui devient inerte, ce qui était déjà mort

Cherché, pas supposé : `grep -ril grocy` sur `config/` et `data/tools/` en
**lecture seule**, plus le registre d'entités, la crontab root et la
configuration du reverse proxy. Relevé le 2026-08-21.

## 1. Ce qui casse le jour de l'arrêt

| Quoi | Où | Geste |
|---|---|---|
| **`maintenance.jinja` bloc 3 + `maintenance_sync_taches`** lisant `todo.grocy_batteries` | `config/custom_templates/maintenance.jinja` (**142 lignes, bloc 3 toujours là**), `config/automations.yaml` **l. 4304-4321** | **Geste 8** — appliquer le raccord du lot 5, `docs/raccord/README.md`, dans son ordre : piles d'abord, `.jinja` ensuite, automation en dernier. 88 lignes contre 142 |
| **`script.afficher_recette_cuisine`** → iframe `/local/grocy-recipes.html` | `config/scripts.yaml` l. 293-331 | **Geste 13** — la page reste servie mais **interroge l'API de Grocy** : elle affichera une erreur. Pointer la vue du panneau, ou supprimer |
| **`script.afficher_repas_prevu`** → `state_attr('sensor.grocy_meal_plan','meals')` | `config/scripts.yaml` l. 407-435 | **Geste 13** — l'attribut devient `None` : branche « pas de recette », **dégradation silencieuse**. `sensor.home_stock_next_meal` porte déjà `meal_id` |
| **`automation.grocy_rappel_liste_de_courses_au_depart`** | `config/automations.yaml` l. 3672-3699 | **Geste 13, le pire des cas** : l'entité passe `unavailable`, `int(0)` la lit `0`, l'automation **ne se déclenche plus jamais, sans erreur**. Rebrancher sur `todo.home_stock_shopping` ou supprimer |
| **Les 55 images hébergées** par `grocy.allanic.me` | HTML des descriptions de recettes | **Gestes 3 et 10** — c'est la raison d'être du rapatriement |
| **Le cron root de 5 h 40**, `grocy-off/sync.sh` | crontab root | **Geste 14** — échouerait chaque nuit contre un port fermé, dans `/var/log/grocy-off.log`. À commenter |
| **Les 2 routes Pomerium** `grocy.allanic.me` → `127.0.0.1:9283` | `/opt/nivuus/Pomerium/config.yaml` l. 81 et 91 | **Geste 16** — 502 sinon. À retirer, **après une sauvegarde datée** |
| **Les 21 entités** de la plateforme `grocy` (7 `binary_sensor`, 6 `sensor`, 6 `todo`, 1 `calendar`) | registre d'entités | **Geste 17** — elles passent `unavailable`. Supprimer l'**entrée de configuration**, puis désinstaller le dépôt HACS |

## 2. Ce qui devient inerte sans rien casser

| Quoi | Pourquoi ce n'est pas grave |
|---|---|
| `config/www/grocy-scanner.html` | Page statique servie par Home Assistant. Elle s'ouvrira et ne répondra plus. Retirée au geste 18 |
| `config/www/grocy-recipes.html` | Idem. Son iframe est déjà traitée au geste 13 |
| `config/grocy_import.db` | Un **intrant** de la bascule, pas un fichier d'exploitation. Supprimé au geste 18 |

## 3. Ce qui était déjà mort — et qu'il ne faut surtout pas « réparer »

À écrire, sinon quelqu'un ira le corriger un soir et perdra sa soirée.

| Quoi | Depuis quand | Ce qu'il faut savoir |
|---|---|---|
| `data/tools/wallpanel/rooms.py` (l. 434-437, `todo.grocy_shopping_list`) | 2026-08-02 | **Générateur périmé.** Les tablettes affichent l'application dédiée `tools/wallpanel-app`, pas un dashboard Lovelace. Modifier ce fichier n'a **aucun effet** |
| `.storage/lovelace.wallpanel_cuisine` (16 références) | 2026-08-02 | Dashboard **périmé**, gardé comme filet de retour arrière. Le modifier n'a aucun effet sur les tablettes |
| `data/tools/wallpanel-app/src/` | — | **Zéro occurrence** de `grocy`. Deux tests le tiennent. Rien à faire |
| Les 8 sauvegardes `*.backup-*` de `.storage/` | — | Des copies datées. Aucune n'est lue |

## 4. Ce que Grocy détenait et que personne ne reprend

| Quoi | Volume | Décision |
|---|---|---|
| `stock_log` | 1 123 lignes | **Archivé en JSON**, jamais versé dans la comptabilité. Voir `retour-arriere.md` et la spec § 9 |
| Les 6 corvées et leurs pointages | 39 pointages sur 187 jours, soit 3,5 % de suivi | **Abandonnées.** Chemin de repli (`local_todo` + une automation quotidienne) dans `docs/exploitation.md`, **hors composant** |
| Les prix historiques | — | Mêmes défauts d'unité que les 7 lots écartés. Se réapprennent en trois sessions de courses (lot 4) et par Open Prices (lot 1) |
| La table de nidification des recettes | 5 651 lignes | Presque toutes produites par les triggers de `meal_plan`. Aucun usage réel constaté |
| Les 112 références Unsplash (46 images distinctes) | — | **Laissées telles quelles.** Le critère est « est-ce que ça meurt avec le conteneur ? », et Unsplash n'en dépend pas. Dette assumée et inscrite : le jour où elles tomberont, elles tomberont toutes ensemble |
