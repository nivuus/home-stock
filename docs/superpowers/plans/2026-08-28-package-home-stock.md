# Package Nivuus `home-stock` — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire du garde-manger un package Nivuus satellite de `home-manager`, installable depuis le wizard au lieu d'un montage bind propre à une machine.

**Architecture:** Le dépôt existant devient le package : on lui ajoute un manifeste déclarant `requires: packages: [home-manager]` et un `hooks/install.py` qui dépose quatre artefacts dans le répertoire de configuration créé par le socle. Aucun hook `activate` — le tri topologique place l'installation du satellite avant le démarrage de Home Assistant par le socle.

**Tech Stack:** Python 3.11 (stdlib + PyYAML), tests en scripts autonomes lancés par `make test`.

**Spec:** `docs/superpowers/specs/2026-08-28-package-nivuus-home-stock-design.md`

## Global Constraints

- Répertoire de dépôt : **`{root}/opt/nivuus/home-manager/config`** — créé par le socle, jamais par ce package.
- **Le hook n'écrit JAMAIS dans `configuration.yaml`.** Règle posée par le projet lui-même dans `packages/home_stock_intents.yaml` (« l'intégration n'y touche jamais ») et par le `PRESERVED` du socle. Sur l'hôte de référence ce fichier fait 17 757 octets et porte les automations d'une maison entière.
- **Il ne touche jamais `home_stock.db`** ni `config/media/home_stock/` : ce sont les données de l'utilisateur, elles vivent à côté des artefacts livrés.
- **Deux destinations sont des répertoires partagés** — `custom_sentences/fr/` et `packages/` reçoivent les fichiers de plusieurs intégrations. Pour elles, le hook copie **le fichier**, jamais le répertoire. Pour `custom_components/home_stock/` et `blueprints/automation/home_stock/`, qui portent le nom du package, il remplace le répertoire entier.
- Seuls les fichiers **suivis par git** voyagent (`git archive HEAD` dans `iso-build/build.sh`).
- `tier: userspace` : ni `platform:`, ni `claims:`, ni `apt:`, ni `wizard.yaml`, ni hook `activate`.
- Tests : `python3` + PyYAML seulement, pas de pytest — les 142 tests pytest existants du projet gardent leur propre cible.
- Répertoire de travail : `~/Projects/Nivuus/packages/home-stock`.

---

### Task 1 : rapatrier l'historique de production

Sans cette tâche, le package empaquetterait la version « lot 0 » : 25 fichiers d'intégration au lieu de 75, sans le panel compilé, sans les blueprints, sans les intents. Elle vient donc en premier.

**Files:**
- Modify: le dépôt lui-même (aucun fichier édité — un fast-forward)

**Interfaces:**
- Consumes: rien.
- Produces: un arbre de travail portant les 345 fichiers suivis attendus par les tâches 2 et 3, dont `custom_components/home_stock/panel/home-stock-panel.js`.

- [ ] **Step 1: Constater l'écart**

Run:
```bash
cd ~/Projects/Nivuus/packages/home-stock
echo "ici      : $(git rev-list --count HEAD) commits, $(git ls-files custom_components | wc -l) fichiers d'integration"
echo "prod     : $(git -C /opt/nivuus/HomeAssistant/data/meal rev-list --count HEAD) commits, $(git -C /opt/nivuus/HomeAssistant/data/meal ls-files custom_components | wc -l) fichiers"
```
Expected: `ici : 29 commits, 25 fichiers` et `prod : 300 commits, 75 fichiers`.

- [ ] **Step 2: Vérifier que c'est bien un fast-forward**

Run:
```bash
git -C /opt/nivuus/HomeAssistant/data/meal merge-base --is-ancestor $(git rev-parse HEAD) HEAD \
  && echo "FAST-FORWARD possible" || echo "DIVERGENCE — arreter et rouvrir la question"
```

Le `$(git rev-parse HEAD)` s'évalue dans le dépôt courant (`home-stock`, 29
commits) ; le `merge-base` teste ce commit dans le dépôt de production. La
question posée est donc : « le HEAD d'ici est-il un ancêtre de là-bas ? »
Expected: `FAST-FORWARD possible`. Si `DIVERGENCE` apparaît, **arrêter le plan** : la spec repose sur l'absence de divergence, et une fusion est une décision qui appartient à l'utilisateur.

- [ ] **Step 3: Récupérer l'historique depuis le clone local**

Le clone de production sert de source : pas de réseau, pas d'identifiants.

```bash
git fetch /opt/nivuus/HomeAssistant/data/meal corrections-ui-panneau:corrections-ui-panneau
git merge --ff-only corrections-ui-panneau
```

- [ ] **Step 4: Vérifier le résultat**

Run:
```bash
echo "commits : $(git rev-list --count HEAD)"
echo "integration : $(git ls-files custom_components | wc -l) fichiers"
echo "panel compile : $(git ls-files custom_components/home_stock/panel/ | wc -l)"
echo "blueprints : $(git ls-files blueprints | wc -l)"
echo "intents : $(git ls-files packages | wc -l)"
echo "phrases : $(git ls-files custom_sentences | wc -l)"
```
Expected: `300`, `75`, `1`, `3`, `1`, `1`.

- [ ] **Step 5: Vérifier que la spec et le plan ont survécu**

Le fast-forward n'écrase pas les fichiers non suivis, mais mieux vaut le constater que le supposer.

Run: `ls docs/superpowers/specs/2026-08-28-package-nivuus-home-stock-design.md docs/superpowers/plans/2026-08-28-package-home-stock.md`
Expected: les deux chemins s'affichent.

- [ ] **Step 6: Committer la spec et le plan**

```bash
git add docs/superpowers/specs/2026-08-28-package-nivuus-home-stock-design.md \
        docs/superpowers/plans/2026-08-28-package-home-stock.md
git commit -m "docs: design et plan du package nivuus home-stock"
```

---

### Task 2 : le manifeste

**Files:**
- Create: `nivuus-package.yaml`, `Makefile`, `tests/test_manifest_contract.py`

**Interfaces:**
- Consumes: l'arbre rapatrié (Task 1).
- Produces: un package nommé `home-stock`, `tier: userspace`, `requires.packages == ("home-manager",)`, découvrable par `discover()`.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_manifest_contract.py` :

```python
#!/usr/bin/env python3
"""Le manifeste doit passer le parseur du moteur, pas une relecture locale.

NIVUUS_INSTALLER_DIR fait valider par installer/packages/manifest.py, qui fait
autorite. C'est le PREMIER package a declarer requires.packages : la
verification que le moteur le lit vraiment est le coeur de ce test.

Run: python3 tests/test_manifest_contract.py
     make test NIVUUS_INSTALLER_DIR=$HOME/Projects/Nivuus/packages/installer
"""
import os
import pathlib
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO / "nivuus-package.yaml"

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


data = yaml.safe_load(MANIFEST.read_text())

check("apiVersion", data.get("apiVersion"), "nivuus.dev/v1")
check("nom", data.get("name"), "home-stock")
check("tier", data.get("tier"), "userspace")

# LA declaration qui fait de ce package un satellite. Sans elle, le moteur
# ordonne alphabetiquement et « home-stock » passe APRES « home-manager » par
# chance, pas par contrat — et un renommage casserait tout en silence.
check("depend du socle", (data.get("requires") or {}).get("packages"),
      ["home-manager"])

check("aucun bloc platform", "platform" in data, False)
check("aucun claim", "claims" in data, False)

# Ni apt ni wizard : manifest.json ne declare aucun requirements Python, et il
# n'y a rien a demander a l'operateur — le chemin de depot vient du socle, la
# base se cree seule. Une question sans effet est une promesse non tenue.
check("aucune dependance apt", "apt" in data, False)
check("aucun wizard", "wizard" in data, False)

check("hook install", (data.get("hooks") or {}).get("install"),
      "hooks/install.py")

# Pas de hook activate : le tri topologique place install(home-stock) avant
# que le socle ne demarre Home Assistant. Un activate serait au mieux inutile,
# au pire une course — les unites systemd d'activation ne sont pas ordonnees
# entre elles.
check("pas de hook activate", "activate" in (data.get("hooks") or {}), False)
check("pas de hook resolve", "resolve" in (data.get("hooks") or {}), False)

installer = os.environ.get("NIVUUS_INSTALLER_DIR")
if installer:
    sys.path.insert(0, str(pathlib.Path(installer) / "installer"))
    from packages.manifest import load_manifest

    manifest = load_manifest(str(MANIFEST))
    check("parseur du moteur: nom", manifest.name, "home-stock")
    check("parseur du moteur: dependance lue", manifest.packages,
          ("home-manager",))
    check("parseur du moteur: hook install resolu",
          manifest.hook_path("install").endswith("hooks/install.py"), True)
    check("parseur du moteur: aucun activate",
          manifest.hook_path("activate"), "")
else:
    print("NIVUUS_INSTALLER_DIR absent : verification locale seule")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("test_manifest_contract: OK")
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `python3 tests/test_manifest_contract.py`
Expected: FAIL — `FileNotFoundError: nivuus-package.yaml`

- [ ] **Step 3: Écrire le manifeste**

Créer `nivuus-package.yaml` :

```yaml
apiVersion: nivuus.dev/v1
name: home-stock
version: 1.0.0
label: "Garde-manger (stocks, dates limites, courses)"
tier: userspace

# Le premier satellite. `requires.packages` fait installer home-manager
# AVANT ce package : le hook depose ses fichiers dans le repertoire de
# configuration que le socle vient de creer. Sans cette ligne, le moteur
# ordonne alphabetiquement — ici l'ordre serait bon par hasard, et un
# renommage le casserait sans que rien ne le signale.
requires:
  packages: [home-manager]

# Ni `apt:`, ni `wizard:`, ni hook `activate` — les trois deliberement.
#
# `apt:` : manifest.json ne declare aucun `requirements` Python. Les trois
# `dependencies` de l'integration (http, websocket_api, panel_custom) sont des
# composants internes de Home Assistant, deja presents.
#
# `wizard:` : le chemin de depot vient du socle, et la base de donnees se cree
# seule au premier demarrage. Il n'y a rien a demander, et une question sans
# effet est une promesse qu'on ne tient pas.
#
# `activate` : le tri topologique garantit que ce package s'installe avant que
# le socle ne demarre Home Assistant, donc l'integration est chargee des le
# premier demarrage. Un activate serait au mieux inutile, au pire une course :
# les unites nivuus-package-activate@<nom>.service vivent toutes dans
# multi-user.target.wants, et systemd ne les ordonne pas entre elles.
hooks:
  install: hooks/install.py
```

- [ ] **Step 4: Écrire le Makefile**

Créer `Makefile` :

```makefile
# Package Nivuus home-stock — cibles de test.
#
# DEUX SUITES, DELIBEREMENT SEPAREES.
#
# `test` couvre le PACKAGE : manifeste et hook d'installation. Scripts
# autonomes, python3 + PyYAML seulement, comme dans le depot installer — c'est
# ce qui permet de les lancer sur une machine qui n'a rien d'autre.
#
# `test-integration` couvre l'INTEGRATION Home Assistant : 142 tests pytest,
# qui demandent homeassistant et ses dependances. Les melanger rendrait le
# package intestable partout ou HA n'est pas installe.
#
# NIVUUS_INSTALLER_DIR fait valider le manifeste par le VRAI parseur du moteur.
#   make test NIVUUS_INSTALLER_DIR=$$HOME/Projects/Nivuus/packages/installer

PACKAGE_DIR := $(CURDIR)
PYTHON ?= python3

.PHONY: test test-integration help

help:
	@grep -E '^[a-zA-Z_-]+:.*' $(MAKEFILE_LIST) | sed 's/:.*//' | sort

test:
	@for t in test_manifest_contract test_install_hook; do \
	    echo "--- $$t"; \
	    $(PYTHON) $(PACKAGE_DIR)/tests/$$t.py || exit 1; \
	done

test-integration:
	$(PYTHON) -m pytest $(PACKAGE_DIR)/tests
```

- [ ] **Step 5: Lancer le test pour vérifier qu'il passe**

Run: `python3 tests/test_manifest_contract.py`
Expected: PASS — `test_manifest_contract: OK`

- [ ] **Step 6: Vérifier avec le parseur du moteur**

Run: `NIVUUS_INSTALLER_DIR=/home/mallanic/Projects/Nivuus/packages/installer python3 tests/test_manifest_contract.py`
Expected: PASS, sans la ligne `NIVUUS_INSTALLER_DIR absent`. C'est la première validation de bout en bout de `requires.packages` sur un manifeste réel.

- [ ] **Step 7: Commit**

```bash
git add nivuus-package.yaml Makefile tests/test_manifest_contract.py
git commit -m "feat: manifeste du package nivuus home-stock, satellite de home-manager"
```

---

### Task 3 : le hook d'installation

**Files:**
- Create: `hooks/install.py`, `tests/test_install_hook.py`

**Interfaces:**
- Consumes: le manifeste (Task 2), l'arbre rapatrié (Task 1).
- Produces: les quatre artefacts déposés sous `{root}/opt/nivuus/home-manager/config/`. Rien n'est consommé par une tâche ultérieure.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_install_hook.py` :

```python
#!/usr/bin/env python3
"""Le hook depose quatre artefacts, et ne detruit rien d'autre.

Deux familles d'assertions :
  - ce qu'il DOIT deposer, aux bons chemins ;
  - ce qu'il ne doit PAS toucher — les donnees de l'utilisateur, et les
    repertoires qu'il partage avec d'autres integrations.

Run: python3 tests/test_install_hook.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "install.py"
CONFIG_REL = "opt/nivuus/home-manager/config"

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def run(root):
    return subprocess.run(
        [sys.executable, str(HOOK), "--phase", "install", "--root", str(root)],
        input=json.dumps({"answers": {}}), capture_output=True, text=True)


def socle(root, configuration=""):
    """Le repertoire de configuration que home-manager aurait cree."""
    config = pathlib.Path(root) / CONFIG_REL
    config.mkdir(parents=True)
    (config / "configuration.yaml").write_text(configuration)
    return config


# --- le socle est absent -------------------------------------------------
# requires.packages bloque le cas dans le wizard, mais le hook tourne aussi en
# autonome, ou rien ne l'a valide. Creer une arborescence orpheline que
# personne ne lira serait pire que refuser.
with tempfile.TemporaryDirectory() as root:
    proc = run(root)
    check("sans le socle, le hook refuse", proc.returncode, 1)
    check("le message nomme le socle", "home-manager" in proc.stderr, True)
    check("rien n'a ete depose",
          (pathlib.Path(root) / CONFIG_REL).exists(), False)

# --- installation nominale ----------------------------------------------
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    proc = run(root)
    check("installation reussit", proc.returncode, 0)

    check("l'integration est deposee",
          (config / "custom_components/home_stock/manifest.json").is_file(),
          True)
    # Le panel compile : sans lui l'interface ne s'affiche pas, et il ne se
    # reconstruit pas sans Node.
    check("le panel compile est depose",
          (config / "custom_components/home_stock/panel"
           / "home-stock-panel.js").is_file(), True)
    check("les blueprints sont deposes",
          len(list((config / "blueprints/automation/home_stock").glob("*.yaml"))),
          3)
    check("les phrases sont deposees",
          (config / "custom_sentences/fr/home_stock.yaml").is_file(), True)
    check("le fragment d'intents est depose",
          (config / "packages/home_stock_intents.yaml").is_file(), True)

    # configuration.yaml ne declare pas packages: — le hook doit le DIRE, et
    # ne surtout pas l'ecrire lui-meme.
    check("le hook signale la declaration manquante",
          "packages: !include_dir_named packages" in proc.stdout, True)
    check("le hook n'a pas touche configuration.yaml",
          (config / "configuration.yaml").read_text(), "")

# --- configuration.yaml declare deja packages: --------------------------
with tempfile.TemporaryDirectory() as root:
    declared = "homeassistant:\n  packages: !include_dir_named packages\n"
    config = socle(root, declared)
    proc = run(root)
    check("rien a signaler quand c'est deja declare",
          "!include_dir_named" in proc.stdout, False)
    check("configuration.yaml reste inchange",
          (config / "configuration.yaml").read_text(), declared)

# --- les donnees de l'utilisateur ---------------------------------------
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    (config / "home_stock.db").write_text("base sqlite de l'utilisateur")
    (config / "media/home_stock").mkdir(parents=True)
    (config / "media/home_stock/recette.jpg").write_text("photo")

    run(root)
    check("la base n'est pas touchee",
          (config / "home_stock.db").read_text(),
          "base sqlite de l'utilisateur")
    check("les images ne sont pas touchees",
          (config / "media/home_stock/recette.jpg").read_text(), "photo")

# --- les repertoires PARTAGES -------------------------------------------
# custom_sentences/fr/ et packages/ recoivent les fichiers de plusieurs
# integrations. Les remplacer supprimerait le travail des autres.
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    (config / "custom_sentences/fr").mkdir(parents=True)
    (config / "custom_sentences/fr/autre_integration.yaml").write_text("phrases")
    (config / "packages").mkdir(parents=True)
    (config / "packages/mon_package.yaml").write_text("ma config")

    run(root)
    check("les phrases d'une autre integration survivent",
          (config / "custom_sentences/fr/autre_integration.yaml").read_text(),
          "phrases")
    check("le fragment d'un autre package survit",
          (config / "packages/mon_package.yaml").read_text(), "ma config")

# --- fichiers fantomes ---------------------------------------------------
# Un module retire entre deux versions doit disparaitre, sinon Home Assistant
# le charge encore. custom_components/home_stock/ porte le nom du package : il
# lui appartient, il est remplace en entier.
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    run(root)
    fantome = config / "custom_components/home_stock/module_supprime.py"
    fantome.write_text("code d'une version precedente")
    cache = config / "custom_components/home_stock/__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "vieux.pyc").write_text("bytecode perime")

    run(root)
    check("le module obsolete a disparu", fantome.exists(), False)
    check("le bytecode perime a disparu", cache.exists(), False)
    check("l'integration est toujours la",
          (config / "custom_components/home_stock/manifest.json").is_file(),
          True)

# --- idempotence ---------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    socle(root)
    run(root)
    proc = run(root)
    check("deuxieme passage sans erreur", proc.returncode, 0)

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("test_install_hook: OK")
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `python3 tests/test_install_hook.py`
Expected: FAIL — le hook n'existe pas ; `proc.returncode` vaut 2, pas 1.

- [ ] **Step 3: Écrire le hook**

Créer `hooks/install.py` :

```python
#!/usr/bin/env python3
"""Phase install du package home-stock : deposer le garde-manger chez le socle.

Ce package est un SATELLITE : il n'a pas de repertoire de deploiement a lui,
il ecrit dans celui que `home-manager` a cree. Son manifeste le declare par
`requires: packages: [home-manager]`, ce qui fait installer le socle en
premier.

DEUX REGLES.

1. IL REFUSE SI LE SOCLE EST ABSENT. `requires.packages` bloque deja le cas
   dans le wizard, mais ce hook tourne aussi en autonome — `--root /`, un
   config.json ecrit a la main — ou rien ne l'a valide. Creer une arborescence
   orpheline que personne ne lira serait pire que refuser.

2. IL REMPLACE CE QUI LUI APPARTIENT, IL COPIE DANS CE QU'IL PARTAGE.
   `custom_components/home_stock/` et `blueprints/automation/home_stock/`
   portent le nom du package : ils sont supprimes puis recopies, sans quoi un
   module retire entre deux versions et les __pycache__ perimes survivraient —
   des fichiers fantomes que Home Assistant chargerait.
   `custom_sentences/fr/` et `packages/` sont PARTAGES avec les autres
   integrations : les remplacer supprimerait leur travail. Pour ceux-la, un
   fichier est copie, jamais un repertoire.

CE HOOK N'ECRIT JAMAIS DANS configuration.yaml. Le fragment d'intents porte
lui-meme la regle : « intent_script est une cle de configuration.yaml, un
fichier que le proprietaire tient a la main ». Quand la declaration `packages:`
manque, le hook la SIGNALE, avec la ligne exacte a ajouter.
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Le repertoire de configuration cree par home-manager.
CONFIG_REL = "opt/nivuus/home-manager/config"

# Repertoires qui portent le nom du package : remplaces en entier.
OWNED_TREES = (
    ("custom_components/home_stock", "custom_components/home_stock"),
    ("blueprints/automation/home_stock", "blueprints/automation/home_stock"),
)

# Fichiers deposes dans des repertoires PARTAGES : copies un par un.
SHARED_FILES = (
    ("custom_sentences/fr/home_stock.yaml", "custom_sentences/fr/home_stock.yaml"),
    ("packages/home_stock_intents.yaml", "packages/home_stock_intents.yaml"),
)

# La declaration sans laquelle Home Assistant ignore config/packages/.
PACKAGES_DECLARATION = "packages: !include_dir_named packages"
PACKAGES_RE = re.compile(r"^\s*packages:\s*!include_dir_named\s", re.MULTILINE)


def emit(event):
    print(json.dumps(event), flush=True)


def replace_tree(source, dest):
    """Remplacer dest par source, entierement."""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copytree(source, dest, symlinks=True)


def copy_file(source, dest):
    """Deposer un fichier dans un repertoire partage, sans toucher au reste."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(source, dest)


def declares_packages(config_dir):
    """configuration.yaml charge-t-il le repertoire packages/ ?

    Une recherche textuelle, pas un yaml.safe_load : configuration.yaml est
    plein de tags !include et !secret que le parseur standard refuse. La
    question posee ici est litterale, la reponse peut l'etre aussi.
    """
    path = os.path.join(config_dir, "configuration.yaml")
    try:
        with open(path) as fh:
            return bool(PACKAGES_RE.search(fh.read()))
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--root", default="/")
    args = parser.parse_args()
    json.load(sys.stdin)          # le contexte est lu, rien n'en depend ici
    root = args.root.rstrip("/") or "/"

    config_dir = os.path.join(root, CONFIG_REL)

    # Regle 1 : refuser plutot que de creer un orphelin.
    if not os.path.isdir(config_dir):
        print("home-stock install: le package home-manager n'est pas installe "
              f"({config_dir} est absent) ; le garde-manger depose ses fichiers "
              "dans la configuration de Home Assistant, qu'il ne cree pas "
              "lui-meme", file=sys.stderr)
        return 1

    emit({"event": "progress", "pct": 20, "msg": "Depose de l'integration"})
    for rel_source, rel_dest in OWNED_TREES:
        replace_tree(os.path.join(HERE, rel_source),
                     os.path.join(config_dir, rel_dest))

    emit({"event": "progress", "pct": 60,
          "msg": "Depose des phrases et du fragment d'intents"})
    for rel_source, rel_dest in SHARED_FILES:
        copy_file(os.path.join(HERE, rel_source),
                  os.path.join(config_dir, rel_dest))

    # Le fragment est depose, mais Home Assistant ne le lira que si
    # configuration.yaml le declare — et ce fichier appartient a l'operateur.
    if not declares_packages(config_dir):
        emit({"event": "progress", "pct": 90,
              "msg": "Les phrases vocales du garde-manger demandent une ligne "
                     "dans configuration.yaml, sous « homeassistant: » : "
                     f"{PACKAGES_DECLARATION}"})

    emit({"event": "progress", "pct": 95,
          "msg": "Garde-manger depose dans la configuration de Home Assistant"})
    emit({"event": "done"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rendre le hook exécutable**

```bash
chmod +x hooks/install.py
```

- [ ] **Step 5: Lancer le test pour vérifier qu'il passe**

Run: `python3 tests/test_install_hook.py`
Expected: PASS — `test_install_hook: OK`

- [ ] **Step 6: Lancer les deux suites du package**

Run: `make test NIVUUS_INSTALLER_DIR=/home/mallanic/Projects/Nivuus/packages/installer`
Expected: deux blocs, tous deux `OK`.

- [ ] **Step 7: Commit**

```bash
git add hooks/install.py tests/test_install_hook.py
git commit -m "feat(hooks): phase install, quatre artefacts chez le socle"
```

---

### Task 4 : la ligne que le socle gagne

Une ligne dans le bootstrap de `home-manager`, pour que les installations neuves chargent les fragments sans que personne n'ait rien à faire.

**Files:**
- Modify: `~/Projects/Nivuus/packages/home-manager/stack/config/configuration.yaml`
- Modify: `~/Projects/Nivuus/packages/home-manager/tests/test_install_hook.py`

**Interfaces:**
- Consumes: rien de ce plan.
- Produces: rien de consommé par une tâche ultérieure. Effet : sur une installation neuve, `declares_packages()` du hook de la Task 3 rend `True` et le message de rappel ne s'affiche pas.

- [ ] **Step 1: Écrire le test qui échoue**

Dans `~/Projects/Nivuus/packages/home-manager/tests/test_install_hook.py`, ajouter dans le bloc `--- installation neuve ---`, juste après l'assertion `le bootstrap de Home Assistant est cree` :

```python
    # Le bootstrap declare packages: pour que les satellites puissent deposer
    # un fragment de configuration qui sera VRAIMENT charge. Sans cette ligne,
    # config/packages/ existe et Home Assistant l'ignore — un satellite
    # deposerait ses intents dans le vide.
    bootstrap = (dest / "config" / "configuration.yaml").read_text()
    check("le bootstrap charge le repertoire packages/",
          "packages: !include_dir_named packages" in bootstrap, True)
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd ~/Projects/Nivuus/packages/home-manager && python3 tests/test_install_hook.py`
Expected: FAIL — `le bootstrap charge le repertoire packages/: got False, want True`

- [ ] **Step 3: Ajouter la ligne au bootstrap**

Dans `~/Projects/Nivuus/packages/home-manager/stack/config/configuration.yaml`, remplacer :

```yaml
default_config:
```

par :

```yaml
default_config:

# Charge tout fichier depose dans config/packages/. C'est par la que les
# packages satellites livrent leurs fragments de configuration — des
# intent_script, par exemple — sans jamais ecrire dans ce fichier-ci, qui
# appartient au proprietaire de la machine.
homeassistant:
  packages: !include_dir_named packages
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `python3 tests/test_install_hook.py`
Expected: PASS — `test_install_hook: OK`

- [ ] **Step 5: Vérifier que le bootstrap reste un YAML valide**

`!include_dir_named` est un tag propre à Home Assistant : `yaml.safe_load` le refuse. La vérification porte donc sur la structure, pas sur la sémantique.

Run:
```bash
cd ~/Projects/Nivuus/packages/home-manager
python3 -c "
import yaml
class L(yaml.SafeLoader): pass
L.add_multi_constructor('!', lambda loader, suffix, node: None)
d = yaml.load(open('stack/config/configuration.yaml'), Loader=L)
assert 'homeassistant' in d, 'bloc homeassistant absent'
assert 'packages' in d['homeassistant'], 'cle packages absente'
print('bootstrap valide, packages declare')
"
```
Expected: `bootstrap valide, packages declare`

- [ ] **Step 6: Lancer la suite complète du socle**

Run: `make test NIVUUS_INSTALLER_DIR=/home/mallanic/Projects/Nivuus/packages/installer`
Expected: cinq blocs, tous `OK`.

- [ ] **Step 7: Commit**

```bash
git add stack/config/configuration.yaml tests/test_install_hook.py
git commit -m "feat(stack): le bootstrap charge config/packages/ pour les satellites"
```

---

### Task 5 : installer en production et retirer le bind

Le package existe ; reste à le faire prendre la place du montage bind sur cette machine.

**Files:**
- Modify: `~/Projects/Nivuus/packages/home-manager/stack/docker-compose.dev.yml`
- Modify: `/opt/nivuus/home-manager/docker-compose.dev.yml` (le déploiement)

**Interfaces:**
- Consumes: le hook de la Task 3.
- Produces: rien de consommé par du code.

- [ ] **Step 1: Relever l'état de référence**

Run:
```bash
docker exec homeassistant ls /config/custom_components/home_stock | wc -l
curl -s -o /dev/null -w "HA: HTTP %{http_code}\n" http://localhost:8123/
```
Expected: un nombre de fichiers non nul, et `HA: HTTP 200`. Noter le nombre.

- [ ] **Step 2: Installer le package sur la machine vivante**

Le hook fait un `rmtree` sur `config/custom_components/home_stock`, et le bind
est encore actif. **Vérifier d'abord que ce chemin n'est pas un point de
montage côté hôte** : Docker monte dans le namespace du conteneur, et le
chemin hôte est un répertoire vide ordinaire — mais si cette machine était
configurée autrement, le `rmtree` traverserait le montage et effacerait le
dépôt de production.

Run:
```bash
D=/opt/nivuus/home-manager/config/custom_components/home_stock
mountpoint -q "$D" && { echo "ARRET : $D est un point de montage, le rmtree effacerait la source"; exit 1; }
echo "sur : $(ls -A "$D" 2>/dev/null | wc -l) entrees cote hote, pas un point de montage"
```
Expected: `sur : 0 entrees cote hote, pas un point de montage`. Si le message
`ARRET` apparaît, ne pas continuer.

Puis installer — le dépôt écrit **sous** le montage, ce qui est voulu : le
contenu sera révélé au retrait du bind.

Run:
```bash
cd ~/Projects/Nivuus/packages/home-stock
echo '{"answers":{}}' | python3 hooks/install.py --phase install --root /
```
Expected: les lignes de progression jusqu'à `{"event": "done"}`, et le rappel de la ligne `packages: !include_dir_named packages` — `configuration.yaml` de production ne la déclare pas.

- [ ] **Step 3: Vérifier ce qui a été déposé**

Run:
```bash
ls /opt/nivuus/home-manager/config/blueprints/automation/home_stock/
ls /opt/nivuus/home-manager/config/custom_sentences/fr/
ls /opt/nivuus/home-manager/config/packages/
```
Expected: les 3 blueprints, `home_stock.yaml`, et `home_stock_intents.yaml`.

- [ ] **Step 4: Retirer le bind du dépôt du socle**

Dans `~/Projects/Nivuus/packages/home-manager/stack/docker-compose.dev.yml`, supprimer ces deux lignes :

```yaml
      # home_stock jusqu'a ce que le package satellite existe : lui seul des
      # cinq binds d'origine pointait sur une source reelle.
      - /opt/nivuus/HomeAssistant/data/meal/custom_components/home_stock:/config/custom_components/home_stock
```

- [ ] **Step 5: Appliquer au déploiement et redémarrer Home Assistant**

```bash
cp ~/Projects/Nivuus/packages/home-manager/stack/docker-compose.dev.yml \
   /opt/nivuus/home-manager/
cd /opt/nivuus/home-manager && docker compose up -d
```

- [ ] **Step 6: Vérifier que l'intégration vient bien du package**

Run:
```bash
sleep 20
docker exec homeassistant ls /config/custom_components/home_stock | wc -l
docker exec homeassistant test -f /config/custom_components/home_stock/panel/home-stock-panel.js \
  && echo "panel compile present"
curl -s -o /dev/null -w "HA: HTTP %{http_code}\n" http://localhost:8123/
docker logs homeassistant 2>&1 | grep -i "home_stock" | grep -iE "error|failed" | tail -3
```
Expected: un nombre de fichiers au moins égal à celui du Step 1, `panel compile present`, `HA: HTTP 200`, et aucune ligne d'erreur `home_stock`. **Si l'intégration ne charge pas, remettre le bind** (`git checkout` du fichier, `cp`, `docker compose up -d`) et investiguer avant d'aller plus loin.

- [ ] **Step 7: Commit du socle**

```bash
cd ~/Projects/Nivuus/packages/home-manager
git add stack/docker-compose.dev.yml
git commit -m "fix(stack): home_stock vient du package satellite, plus d'un bind"
```

---

## Vérification finale

- [ ] `make test NIVUUS_INSTALLER_DIR=…` passe dans `home-stock` (2 suites) et dans `home-manager` (5 suites).
- [ ] Le manifeste de `home-stock` est accepté par le vrai parseur du moteur, avec `requires.packages == ("home-manager",)`.
- [ ] `install_order` du moteur place `home-manager` avant `home-stock` — vérifiable par :
      ```bash
      cd ~/Projects/Nivuus/packages/installer && python3 -c "
      import sys; sys.path.insert(0, 'installer')
      from packages.manifest import load_manifest
      from packages.dependencies import install_order
      a = load_manifest('$HOME/Projects/Nivuus/packages/home-stock/nivuus-package.yaml')
      b = load_manifest('$HOME/Projects/Nivuus/packages/home-manager/nivuus-package.yaml')
      print([m.name for m in install_order([a, b])])
      "
      ```
      Attendu : `['home-manager', 'home-stock']`.
- [ ] Sur la machine, Home Assistant répond et charge `home_stock` depuis `config/`, sans bind.
- [ ] `home_stock.db` et `config/media/home_stock/` n'ont pas été modifiés.
- [ ] Aucun `configuration.yaml` existant n'a été touché.

## Ce qui reste à l'opérateur

Deux gestes que ce plan prépare sans les faire :

1. **Pousser vers `nivuus/home-stock`** — l'environnement n'a pas d'identifiants GitHub. Après la Task 1 le dépôt local porte les 300 commits ; la commande sera `git push origin corrections-ui-panneau` (ou vers `master`, selon le point 2).
2. **Choisir quelle branche devient `master`** — la production vit sur `corrections-ui-panneau`, et `master` est 271 commits derrière.
3. **Ajouter `packages: !include_dir_named packages`** au `configuration.yaml` de production, sous `homeassistant:`, pour activer les phrases vocales du garde-manger. Une ligne, dans un fichier que le package s'interdit de toucher.
