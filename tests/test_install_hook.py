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
