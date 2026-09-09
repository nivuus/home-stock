#!/usr/bin/env python3
"""Phase install du package home-stock : deposer le garde-manger chez le socle.

Ce package est un SATELLITE : il n'a pas de repertoire de deploiement a lui,
il ecrit dans celui que `home-manager` a cree. Son manifeste le declare par
`requires: packages: [home-manager]`, ce qui fait installer le socle en
premier.

PLUSIEURS REGLES.

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

3. LES PHRASES VOCALES SONT CONDITIONNELLES AU FRAGMENT D'INTENTS. Les deux
   portent les memes sept identifiants, mais leurs regles de chargement sont
   opposees : `custom_sentences/` est charge automatiquement par Home
   Assistant, `packages/` seulement si `configuration.yaml` declare
   `packages:`. Deposer les phrases sans le fragment rendrait les sept
   phrases RECONNUES SANS GESTIONNAIRE : l'assistant repondrait une erreur au
   lieu de passer la main a l'agent de repli. Voir CONDITIONAL_FILES plus bas.

4. DEUX EXECUTIONS CONCURRENTES SE SERIALISENT. Reexecuter ce hook est le seul
   mecanisme de mise a jour, et rien n'empechait deux passages simultanes de
   s'entrelacer — l'un sortant en 0 pendant que l'autre a mi-chemin a deja
   efface ce qu'il n'a pas fini de redeposer. Voir exclusive_deposit().

CE HOOK N'ECRIT JAMAIS DANS configuration.yaml. Le fragment d'intents porte
lui-meme la regle : « intent_script est une cle de configuration.yaml, un
fichier que le proprietaire tient a la main ». Quand la declaration `packages:`
manque, le hook la SIGNALE, avec la ligne exacte a ajouter — et dit que les
phrases vocales restent en attente de cette ligne.
"""
import argparse
import contextlib
import fcntl
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

# Fichier depose dans un repertoire PARTAGE : copie seul, jamais par
# remplacement du repertoire, qui appartient aussi aux autres integrations.
# Il est depose INCONDITIONNELLEMENT : c'est du texte inerte tant que rien ne
# le charge, et son absence est ce qui rend les phrases dangereuses (regle 3).
INTENTS_REL = "packages/home_stock_intents.yaml"
SHARED_FILES = (
    (INTENTS_REL, INTENTS_REL),
)

# Les phrases vocales, elles, sont CONDITIONNELLES — et ce n'est pas une
# precaution, c'est une correction de bug. Home Assistant charge
# custom_sentences/ tout seul, mais l'intent_script qui repond a ces phrases
# vit dans le fragment ci-dessus, que HA n'inclut que si configuration.yaml
# declare `packages:`. Deposees sans lui, les sept phrases deviennent
# reconnues SANS gestionnaire : l'assistant repond une erreur au lieu de
# passer la main a l'agent de repli. Les deux, ou aucun.
CONDITIONAL_FILES = (
    ("custom_sentences/fr/home_stock.yaml", "custom_sentences/fr/home_stock.yaml"),
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


def _discard(path):
    """Ecarter ce qui occupe deja `path`, quelle que soit sa nature.

    rmtree refuse un lien symbolique et un fichier simple ; ce sont pourtant
    deux etats releves en revue a cet emplacement (une reinstallation qui
    suit une bidouille manuelle, par exemple). On distingue donc explicitement
    plutot que de laisser un traceback nu decider a la place de l'operateur.
    """
    if not os.path.lexists(path):
        return
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def replace_tree(source, dest):
    """Remplacer dest par source, entierement, sans jamais laisser dest absent.

    L'ancienne version faisait rmtree() puis copytree() : entre les deux, dest
    n'existe pas. La revue a mesure 291 lectures sur fichier absent pendant
    cette fenetre — panel.py relit son bundle de 234 Ko sur le disque a chaque
    chargement de page, sans cache — et si le processus meurt entre les deux
    appels, l'integration a purement disparu.

    On copie donc vers un repertoire voisin temporaire (l'ancien arbre reste
    intact tant que cette copie n'est pas terminee), puis on bascule par
    os.replace(), atomique sur un meme systeme de fichiers. os.replace() sur
    un repertoire exige une cible vide ou absente : on ecarte donc l'ancien
    dest juste avant le double remplacement, en le deplacant plutot qu'en
    l'effacant, pour ne le supprimer qu'une fois le nouveau en place.
    """
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)

    tmp = dest + ".new"
    old_aside = dest + ".old"
    _discard(tmp)
    _discard(old_aside)

    try:
        # Le bytecode de la source n'est pas de la source. Un __pycache__ pose
        # par l'interpreteur qui a lu ce depot (pytest en collecte un pour
        # chaque module qu'il importe) serait recopie tel quel dans le config
        # de Home Assistant, qui tourne sur un AUTRE interpreteur : au mieux
        # inutile, au pire un .pyc perime a cote du .py qui vient d'arriver.
        # Mesure : sans ce filtre, la suite autonome tombe sur
        # "le bytecode perime a disparu: got True, want False" des que la
        # source porte un __pycache__ - ce qui est exactement ce qui arrive
        # quand pytest passe avant.
        shutil.copytree(source, tmp, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    except Exception:
        _discard(tmp)
        raise

    moved_old = os.path.lexists(dest)
    if moved_old:
        if os.path.isdir(dest) and not os.path.islink(dest):
            os.replace(dest, old_aside)
        else:
            # Un lien symbolique ou un fichier simple a cet emplacement : rien
            # a preserver, rien que rmtree() saurait de toute facon traiter.
            os.remove(dest)
            moved_old = False

    os.replace(tmp, dest)

    if moved_old:
        shutil.rmtree(old_aside)


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

    La lecture est TOLERANTE a l'encodage : ce controle tourne apres les
    depots (regle 2 et 3 plus haut), donc une UnicodeDecodeError ici ferait
    echouer l'installation entiere alors que tous les fichiers sont deja en
    place — pire que le message superflu qu'elle empecherait.
    """
    path = os.path.join(config_dir, "configuration.yaml")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return False
    wanted = os.path.dirname(INTENTS_REL)
    return any(match.group(1) == wanted
               for match in PACKAGES_RE.finditer(text))


@contextlib.contextmanager
def exclusive_deposit(config_dir):
    """Serialiser les executions concurrentes du hook sur le meme socle.

    Reexecuter ce hook est le seul mecanisme de mise a jour du package, et
    rien ne l'empechait de tourner deux fois en meme temps : une revue en a
    lance quatre en parallele et vu l'une sortir en 0 avec {"event": "done"}
    alors que onze fichiers manquaient, panel.py compris.

    Le verrou porte sur config_dir lui-meme : il existe forcement a cet
    instant (la regle 1 vient de le verifier) et ce n'est l'artefact d'aucune
    des deux executions — contrairement a tout ce que ce hook depose, qui
    n'existerait pas encore lors d'un tout premier passage.
    """
    fd = os.open(config_dir, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


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

    with exclusive_deposit(config_dir):
        emit({"event": "progress", "pct": 20, "msg": "Depose de l'integration"})
        for rel_source, rel_dest in OWNED_TREES:
            replace_tree(os.path.join(HERE, rel_source),
                         os.path.join(config_dir, rel_dest))

        emit({"event": "progress", "pct": 55,
              "msg": "Depose du fragment d'intents"})
        for rel_source, rel_dest in SHARED_FILES:
            copy_file(os.path.join(HERE, rel_source),
                      os.path.join(config_dir, rel_dest))

        # Regle 3 : les phrases ne partent que si le fragment ci-dessus sera
        # vraiment charge. Sans quoi elles seraient reconnues sans gestionnaire.
        packages_declared = declares_packages(config_dir)
        if packages_declared:
            emit({"event": "progress", "pct": 75,
                  "msg": "Depose des phrases vocales"})
            for rel_source, rel_dest in CONDITIONAL_FILES:
                copy_file(os.path.join(HERE, rel_source),
                          os.path.join(config_dir, rel_dest))
        else:
            emit({"event": "progress", "pct": 90,
                  "msg": "Les phrases vocales du garde-manger ne sont PAS "
                         "deposees : elles sont en attente d'une ligne dans "
                         "configuration.yaml, sous « homeassistant: » : "
                         f"{PACKAGES_DECLARATION}"})

        emit({"event": "progress", "pct": 95,
              "msg": "Garde-manger depose dans la configuration de Home Assistant"})

    emit({"event": "done"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
