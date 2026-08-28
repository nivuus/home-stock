#!/usr/bin/env python3
"""Le hook depose ses artefacts, et ne detruit rien d'autre.

Familles d'assertions :
  - ce qu'il DOIT deposer, aux bons chemins, et sous quelle condition ;
  - ce qu'il ne doit PAS toucher — les donnees de l'utilisateur, et les
    repertoires qu'il partage avec d'autres integrations ;
  - ce qu'il doit encaisser proprement — un dest deja occupe par autre chose
    qu'un repertoire, un configuration.yaml mal encode, deux executions en
    meme temps.

Run: python3 tests/test_install_hook.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

import yaml

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


DECLARED = "homeassistant:\n  packages: !include_dir_named packages\n"

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

# --- installation nominale, SANS la declaration packages: -----------------
# Le fragment d'intents est toujours depose. Les phrases vocales, elles, ne
# doivent PAS l'etre : sans la declaration, personne ne charge le fragment qui
# leur donne un gestionnaire, et les deposer quand meme rendrait les sept
# phrases reconnues SANS reponse.
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
    check("le fragment d'intents est depose",
          (config / "packages/home_stock_intents.yaml").is_file(), True)
    check("les phrases NE sont PAS deposees sans la declaration",
          (config / "custom_sentences/fr/home_stock.yaml").exists(), False)

    # configuration.yaml ne declare pas packages: — le hook doit le DIRE, et
    # ne surtout pas l'ecrire lui-meme.
    check("le hook signale la declaration manquante",
          "packages: !include_dir_named packages" in proc.stdout, True)
    check("le hook dit que les phrases sont en attente de cette declaration",
          "PAS" in proc.stdout and "attente" in proc.stdout, True)
    check("le hook n'a pas touche configuration.yaml",
          (config / "configuration.yaml").read_text(), "")

# --- configuration.yaml declare deja packages: -----------------------------
# La declaration est presente : le fragment sera charge, les phrases peuvent
# donc partir avec lui.
with tempfile.TemporaryDirectory() as root:
    config = socle(root, DECLARED)
    proc = run(root)
    check("rien a signaler quand c'est deja declare",
          "!include_dir_named" in proc.stdout, False)
    check("configuration.yaml reste inchange",
          (config / "configuration.yaml").read_text(), DECLARED)
    check("les phrases sont deposees quand la declaration est presente",
          (config / "custom_sentences/fr/home_stock.yaml").is_file(), True)
    check("le fragment d'intents est toujours depose",
          (config / "packages/home_stock_intents.yaml").is_file(), True)

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
    config = socle(root, DECLARED)
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

# --- une integration et un blueprint VOISINS -----------------------------
# custom_components/ et blueprints/automation/ sont partages avec trente
# autres integrations. Si OWNED_TREES s'elargissait un jour de
# `custom_components/home_stock` a `custom_components` tout court, la suite
# devait rester rouge : ce test le garantit.
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    (config / "custom_components/autre_integration").mkdir(parents=True)
    (config / "custom_components/autre_integration/__init__.py").write_text(
        "# appartient a une autre integration, jamais a home_stock\n")
    (config / "blueprints/automation/un_autre_auteur").mkdir(parents=True)
    (config / "blueprints/automation/un_autre_auteur/routine.yaml").write_text(
        "blueprint:\n  name: Routine d'un autre auteur\n")

    run(root)
    check("l'integration voisine survit",
          (config / "custom_components/autre_integration/__init__.py").read_text(),
          "# appartient a une autre integration, jamais a home_stock\n")
    check("le blueprint d'un autre auteur survit",
          (config / "blueprints/automation/un_autre_auteur/routine.yaml")
          .read_text(),
          "blueprint:\n  name: Routine d'un autre auteur\n")

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

# --- remplacement propre d'un dest deja occupe par autre chose -----------
# replace_tree() bascule desormais par os.replace(), qui exige une cible vide
# ou absente. Un lien symbolique ou un fichier simple a cet emplacement (une
# bidouille manuelle avant reinstallation, par exemple) doivent etre ecartes
# proprement, jamais faire remonter un traceback nu.
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    (config / "custom_components").mkdir(parents=True)
    ailleurs = pathlib.Path(root) / "ailleurs"
    ailleurs.mkdir()
    (config / "custom_components/home_stock").symlink_to(ailleurs,
                                                           target_is_directory=True)

    proc = run(root)
    check("un lien symbolique a la place de dest n'empeche pas l'installation",
          proc.returncode, 0)
    check("aucun traceback quand dest est un lien symbolique",
          "Traceback" in proc.stderr, False)
    check("dest est redevenu un vrai repertoire",
          (config / "custom_components/home_stock/manifest.json").is_file(),
          True)
    check("le lien d'origine n'a pas ete suivi ni efface",
          ailleurs.exists(), True)

with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    (config / "blueprints/automation").mkdir(parents=True)
    (config / "blueprints/automation/home_stock").write_text(
        "pas un repertoire")

    proc = run(root)
    check("un fichier simple a la place de dest n'empeche pas l'installation",
          proc.returncode, 0)
    check("aucun traceback quand dest est un fichier simple",
          "Traceback" in proc.stderr, False)
    check("dest est redevenu un vrai repertoire",
          len(list((config / "blueprints/automation/home_stock").glob("*.yaml"))),
          3)

# --- idempotence ---------------------------------------------------------
with tempfile.TemporaryDirectory() as root:
    socle(root)
    run(root)
    proc = run(root)
    check("deuxieme passage sans erreur", proc.returncode, 0)

# --- variantes de declaration ------------------------------------------
# `!include_dir_merge_named` charge le repertoire tout autant : signaler une
# ligne a ajouter serait inviter l'operateur a creer une cle en double, et les
# phrases doivent partir tout aussi bien que sous `!include_dir_named`.
with tempfile.TemporaryDirectory() as root:
    config = socle(root,
                   "homeassistant:\n"
                   "  packages: !include_dir_merge_named packages\n")
    proc = run(root)
    check("la variante merge_named est reconnue",
          "!include_dir_named" in proc.stdout, False)
    check("les phrases partent aussi sous merge_named",
          (config / "custom_sentences/fr/home_stock.yaml").is_file(), True)

# Le cas silencieux : une declaration qui ne designe PAS le repertoire ou ce
# hook depose. Le fragment ne sera jamais charge — le hook doit le dire, et
# les phrases ne doivent pas partir.
with tempfile.TemporaryDirectory() as root:
    config = socle(root,
                   "homeassistant:\n"
                   "  packages: !include_dir_named autre_dossier\n")
    proc = run(root)
    check("une declaration visant un autre repertoire est signalee",
          "packages: !include_dir_named packages" in proc.stdout, True)
    check("les phrases ne partent pas quand la declaration vise ailleurs",
          (config / "custom_sentences/fr/home_stock.yaml").exists(), False)

# --- configuration.yaml mal encode ----------------------------------------
# declares_packages() ouvrait le fichier en texte et ne rattrapait qu'OSError.
# Ce controle tourne APRES les depots : une UnicodeDecodeError ici faisait
# echouer l'installation entiere alors que tous les fichiers etaient deja en
# place, et le package n'etait jamais enregistre.
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    (config / "configuration.yaml").write_bytes(b"homeassistant:\n"
                                                  b"  name: Chez moi \xff\xfe\n")
    proc = run(root)
    check("un configuration.yaml mal encode n'interrompt pas l'installation",
          proc.returncode, 0)
    check("l'integration est deposee malgre l'encodage",
          (config / "custom_components/home_stock/manifest.json").is_file(),
          True)
    check("le fragment d'intents est depose malgre l'encodage",
          (config / "packages/home_stock_intents.yaml").is_file(), True)

# --- deux executions concurrentes -----------------------------------------
# Reexecuter ce hook est le seul mecanisme de mise a jour. Une revue en a
# lance quatre en parallele et vu l'une sortir en 0 avec 11 fichiers manquants,
# panel.py compris. Le verrou (fcntl.flock) doit serialiser les executions au
# lieu de les laisser s'entremeler.
with tempfile.TemporaryDirectory() as root:
    config = socle(root)
    procs = [subprocess.Popen(
        [sys.executable, str(HOOK), "--phase", "install", "--root", root],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True) for _ in range(4)]
    outputs = [p.communicate(json.dumps({"answers": {}})) for p in procs]
    codes = [p.returncode for p in procs]

    check("les quatre executions concurrentes reussissent", codes, [0, 0, 0, 0])
    check("l'integration est complete apres la course",
          (config / "custom_components/home_stock/manifest.json").is_file(),
          True)
    check("le panel compile est complet apres la course",
          (config / "custom_components/home_stock/panel"
           / "home-stock-panel.js").is_file(), True)
    check("les blueprints sont complets apres la course",
          len(list((config / "blueprints/automation/home_stock").glob("*.yaml"))),
          3)
    check("aucun repertoire temporaire ne traine apres la course",
          sorted(p.name for p in config.glob("custom_components/home_stock.*")),
          [])
    for i, (out, err) in enumerate(outputs):
        check(f"execution {i} : chaque ligne de stdout est un evenement JSON",
              all(bool(json.loads(line)) for line in out.splitlines() if line),
              True)

# --- phrases et intents doivent se correspondre ---------------------------
# Les deux fichiers portent les memes sept identifiants d'intents, aux memes
# regles de chargement opposees (voir hooks/install.py). Rien d'autre ne
# surveillait ce couplage dans la suite qui tourne sans pytest ni
# Home Assistant — c'est exactement ce qui a casse en production.
sentences_doc = yaml.safe_load(
    (REPO / "custom_sentences/fr/home_stock.yaml").read_text(encoding="utf-8"))
intents_doc = yaml.safe_load(
    (REPO / "packages/home_stock_intents.yaml").read_text(encoding="utf-8"))
check("les phrases et le fragment d'intents portent les memes identifiants",
      set(sentences_doc["intents"]), set(intents_doc["intent_script"]))
check("il y a bien sept intents des deux cotes",
      len(sentences_doc["intents"]), 7)

if failures:
    print("\n".join(failures))
    sys.exit(1)
print("test_install_hook: OK")
