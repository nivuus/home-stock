# `home-stock` en package Nivuus — design

**Date** : 2026-08-28
**Statut** : validé, prêt pour le plan d'implémentation

## Objectif

Faire du garde-manger un **package Nivuus satellite** de `home-manager` :
installable depuis le wizard de l'installateur, au lieu d'un montage bind
propre à une machine.

C'est le premier consommateur réel de `requires.packages`, le champ ajouté au
contrat `nivuus.dev/v1` le 2026-08-28 pour que le moteur installe un socle
avant ses satellites.

## L'état de départ, et ce qu'il faut en comprendre

Deux clones du même dépôt coexistent sur la machine :

| | `/opt/nivuus/HomeAssistant/data/meal` | `packages/home-stock` |
|---|---|---|
| Remote | `maximeallanic/nivuus-home-stock` | `nivuus/home-stock` |
| Branche | `corrections-ui-panneau` | `master` |
| Commits | 300 | 29 |
| Rôle | **ce que Home Assistant charge** | dépôt de l'organisation |

Ils ne divergent pas : `master` est un **ancêtre** de la production, et les 30
commits de `origin/lot-1-scan-et-entree` sont tous présents en production. Le
dépôt d'organisation est simplement 271 commits en retard, et le rapatriement
est un fast-forward — pas une fusion.

**Décision** : `packages/home-stock` devient le package, après ce
fast-forward. Le montage bind qui sert aujourd'hui l'intégration disparaît de
`docker-compose.dev.yml` du socle une fois le package installé.

## Ce que le projet fournit, et ce qui se déploie

Le dépôt porte 345 fichiers suivis. Tout ne se déploie pas :

| Répertoire | Fichiers suivis | Déployé |
|---|---|---|
| `custom_components/home_stock/` | 75 | **oui** |
| `blueprints/automation/home_stock/` | 3 | **oui** |
| `custom_sentences/fr/` | 1 | **oui** |
| `packages/home_stock_intents.yaml` | 1 | **oui** |
| `frontend/` | 87 | non |
| `tests/` | 142 | non |
| `docs/` | 29 | non |

`frontend/` est une dépendance de **build**, pas de déploiement : Rollup le
compile en un bundle unique, `custom_components/home_stock/panel/home-stock-panel.js`
(234 Ko), que `panel.py` sert. Ce bundle **est versionné**, donc `git archive
HEAD` l'embarque et l'installateur n'a jamais besoin de Node. Les 104 Mo de
sources et de `node_modules` ne quittent pas le dépôt.

## Le manifeste

```yaml
apiVersion: nivuus.dev/v1
name: home-stock
version: 1.0.0
label: "Garde-manger (stocks, dates limites, courses)"
tier: userspace

requires:
  packages: [home-manager]
```

Rien d'autre, et chaque absence est un choix :

- **pas d'`apt:`** — `manifest.json` ne déclare aucun `requirements` Python.
  Ses trois `dependencies` (`http`, `websocket_api`, `panel_custom`) sont des
  composants internes de Home Assistant, déjà présents ;
- **pas de `wizard.yaml`** — le chemin de dépôt vient du socle, et la base se
  crée seule au premier démarrage. Il n'y a rien à demander, et une question
  sans effet est une promesse qu'on ne tient pas ;
- **pas de `claims:` ni de `requires.capabilities:`** — le garde-manger ne
  touche aucun matériel ;
- **pas de hook `activate`** (voir ci-dessous).

## Pourquoi il n'y a pas de hook `activate`

À l'installation, le tri topologique garantit `install(home-manager)` avant
`install(home-stock)` : les fichiers sont en place **avant** que le socle ne
démarre Home Assistant en phase `activate`. L'intégration est donc chargée au
premier démarrage, sans que personne n'ait à redémarrer quoi que ce soit.

Un hook `activate` serait au mieux inutile, au pire nuisible : les activations
sont armées comme des instances systemd indépendantes
(`nivuus-package-activate@<nom>.service`, toutes dans
`multi-user.target.wants`), et **systemd ne garantit aucun ordre entre elles**.
Un `activate` du satellite pourrait donc courir contre celui du socle.

> **Dette connue, hors périmètre.** Le tri topologique du 2026-08-28 ordonne
> les `install`, pas les `activate`. Sans conséquence ici, puisque ce package
> n'a pas d'`activate` — mais un futur satellite qui en aurait un devrait
> d'abord faire ordonner les units systemd entre elles.

## Le hook `install.py`

Deux règles le portent.

**1. Il refuse si le socle est absent.** `requires.packages` bloque déjà le
cas dans le wizard, mais le hook tourne aussi en autonome — `--root /`, un
`config.json` écrit à la main — où rien ne l'a validé. Si
`{root}/opt/nivuus/home-manager/config` n'existe pas, il sort en erreur en le
disant, plutôt que de créer une arborescence orpheline que personne ne lira.

**2. Il remplace le code, il ne le fusionne pas.**
`custom_components/home_stock/` est supprimé puis recopié. Une copie
par-dessus laisserait vivre les modules retirés entre deux versions et les
`__pycache__` périmés — des fichiers fantômes que Home Assistant chargerait.
Aucune donnée n'y vit : `home_stock.db` et les images de recettes sont dans
`config/`, à côté, et ne sont jamais touchées. `blueprints/automation/home_stock/`
suit la même règle : le répertoire porte le nom du package, il lui appartient.

**Mais deux destinations sont des répertoires PARTAGÉS**, et les remplacer
supprimerait le travail d'autres intégrations : `custom_sentences/fr/` reçoit
les phrases de toutes les intégrations de la langue, et `config/packages/`
tous les fragments de configuration. Pour ces deux-là, le hook copie **le
fichier**, jamais le répertoire — `custom_sentences/fr/home_stock.yaml` et
`packages/home_stock_intents.yaml`.

Destinations, toutes sous `{root}/opt/nivuus/home-manager/config/` :

| Source | Destination | Chargé par HA |
|---|---|---|
| `custom_components/home_stock/` | `custom_components/home_stock/` | automatiquement |
| `blueprints/automation/home_stock/` | `blueprints/automation/home_stock/` | automatiquement |
| `custom_sentences/fr/` | `custom_sentences/fr/` | automatiquement |
| `packages/home_stock_intents.yaml` | `packages/home_stock_intents.yaml` | **sous condition** |

## Le fragment d'intents, et la ligne que le package n'écrit pas

`home_stock_intents.yaml` porte un `intent_script` — une clé de
`configuration.yaml`. Home Assistant ne le charge que si `configuration.yaml`
déclare :

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Or le fichier porte lui-même la règle, posée par le projet :

> *« LIVRÉ, JAMAIS INSTALLÉ. […] `intent_script` est une clé de
> configuration.yaml, un fichier que le propriétaire tient à la main :
> l'intégration n'y touche jamais. »*

Elle coïncide avec celle du socle, où `config/configuration.yaml` est dans
`PRESERVED`. Sur l'hôte de référence, ce fichier fait 17 757 octets et porte
les automations d'une maison entière.

**Décision** : le hook dépose le fragment et, quand `configuration.yaml` ne
déclare pas `packages:`, l'écrit dans son flux de progression avec la ligne
exacte à ajouter. Il n'écrit jamais dans `configuration.yaml`.

**En regard, le socle change d'une ligne** : le bootstrap
`stack/config/configuration.yaml` de `home-manager` gagne
`packages: !include_dir_named packages`. Sans effet sur les installations
existantes — ce fichier n'est créé que s'il est absent — mais toute
installation neuve charge alors les fragments sans que personne n'ait rien à
faire.

Rejetée : l'insertion idempotente dans `configuration.yaml`. Elle marcherait
partout tout de suite, au prix de violer à la fois la règle du projet et
`PRESERVED`, sur le fichier le plus précieux de l'installation.

## Tests

Style du dépôt `installer` : scripts autonomes, `python3` + PyYAML, pas de
pytest.

- **`test_manifest_contract`** — le manifeste passe le **vrai** parseur du
  moteur quand `NIVUUS_INSTALLER_DIR` est fourni ; `requires.packages` vaut
  `("home-manager",)` ; ni `apt`, ni `wizard`, ni hook `activate`.
- **`test_install_hook`** — les quatre arbres déposés aux bons chemins ; le
  **refus quand le socle est absent** ; une `home_stock.db` posée à côté et
  vérifiée intacte ; l'idempotence ; un module obsolète présent avant
  l'installation et **absent après** ; le signalement quand `configuration.yaml`
  ne déclare pas `packages:` ; le silence quand il le déclare.

Le projet porte déjà 142 tests sous pytest. Le `Makefile` aura donc deux
cibles séparées : `test` pour les suites du package, `test-integration` pour le
pytest existant. Aucune conversion : mélanger les deux styles serait pire que
les séparer.

## Remise en ordre git

1. `packages/home-stock` est un fast-forward derrière la production : un pull
   depuis le clone local `data/meal` le fait passer de 29 à 300 commits, sans
   réseau.
2. **Deux décisions restent à l'opérateur** : pousser vers `nivuus/home-stock`
   demande des identifiants GitHub que l'environnement n'a pas, et choisir
   quelle branche devient `master` — la production vit sur
   `corrections-ui-panneau`. Le dépôt est préparé localement, la commande est
   donnée, l'exécution appartient à Maxime.
3. Une fois le package installé, le bind `home_stock` disparaît de
   `docker-compose.dev.yml` du socle : c'est le package qui dépose
   l'intégration.

## Ce que ce design ne fait pas

- il ne déploie pas les sources du frontend, seulement le bundle compilé ;
- il ne touche à aucun `configuration.yaml` existant ;
- il ne fusionne pas les deux remotes GitHub — il constate qu'ils sont sur la
  même ligne d'historique et prépare le fast-forward ;
- il ne fait pas ordonner les activations systemd entre elles ;
- il ne migre pas `home_stock.db` : elle est déjà au bon endroit, dans
  `config/`, et le package ne la touche jamais.
