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
