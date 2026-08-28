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
# Les deux tags que Home Assistant accepte pour charger un repertoire de
# paquets, et le nom du repertoire qu'ils designent — capture indispensable :
# `packages: !include_dir_named autre_dossier` declare bien quelque chose,
# mais pas le repertoire `packages/` ou ce hook depose son fragment. Sans la
# capture, le hook se tairait sur une configuration qui n'a aucune chance de
# charger ce qu'il vient d'ecrire.
PACKAGES_RE = re.compile(
    r"^\s*packages:\s*!include_dir_(?:merge_)?named\s+(\S+)\s*$", re.MULTILINE)


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
    """configuration.yaml charge-t-il le repertoire ou ce hook depose ?

    Une recherche textuelle, pas un yaml.safe_load : configuration.yaml est
    plein de tags !include et !secret que le parseur standard refuse.

    LIMITE ASSUMEE : une declaration logee dans un fichier inclus
    (`homeassistant: !include core.yaml`) echappe a cette recherche, qui ne
    lit que configuration.yaml. Le hook signalera alors une ligne deja
    presente ailleurs — un message superflu, jamais une perte.
    """
    path = os.path.join(config_dir, "configuration.yaml")
    try:
        with open(path) as fh:
            text = fh.read()
    except OSError:
        return False
    wanted = os.path.dirname(SHARED_FILES[1][1])
    return any(match.group(1) == wanted
               for match in PACKAGES_RE.finditer(text))


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
