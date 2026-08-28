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
