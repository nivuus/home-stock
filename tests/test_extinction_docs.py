"""La procédure d'extinction est un livrable, donc elle se teste.

Ces tests lisent des fichiers Markdown. Ils ne lancent rien, n'arrêtent rien
et ne touchent à aucun fichier de /opt/nivuus/HomeAssistant/config/.
"""
from pathlib import Path

RACINE = Path(__file__).parent.parent
PROCEDURE = (RACINE / "docs/extinction/README.md").read_text("utf-8")
INVENTAIRE = (RACINE / "docs/extinction/inventaire-grocy.md").read_text("utf-8")
RETOUR = (RACINE / "docs/extinction/retour-arriere.md").read_text("utf-8")


def test_the_procedure_is_a_numbered_list_of_eighteen_gestures():
    import re
    numeros = [l for l in PROCEDURE.splitlines() if re.match(r"^\d+\. ", l)]
    assert len(numeros) >= 18
    # Numérotés de 1 à 18, sans trou : un geste sauté est un incident dans
    # six semaines.
    assert [int(l.split(".", 1)[0]) for l in numeros] == list(range(1, 19))


def test_every_thing_that_breaks_has_its_gesture():
    """L'inventaire du §17.1, relu. Chacun doit apparaître dans la procédure,
    avec le geste correspondant — pas seulement dans le tableau."""
    for casse in ("maintenance.jinja", "todo.grocy_batteries",
                  "script.afficher_recette_cuisine", "script.afficher_repas_prevu",
                  "automation.grocy_rappel_liste_de_courses_au_depart",
                  "grocy-off/sync.sh", "Pomerium", "grocy-recipes.html"):
        assert casse in PROCEDURE, casse


def test_the_silent_one_is_flagged_as_silent():
    """L'automation de rappel de courses SE TAIRA SANS ERREUR : int(0) lit
    une entité unavailable comme 0. C'est le pire des cas, et il doit être
    écrit comme tel — une panne bruyante se voit, celle-ci non."""
    bloc = PROCEDURE[PROCEDURE.index("grocy_rappel_liste_de_courses"):][:900]
    assert "sans erreur" in bloc or "silencieu" in bloc


def test_the_raccord_is_named_as_a_prerequisite():
    """Le raccord du lot 5 n'est TOUJOURS PAS posé : maintenance.jinja a
    encore ses 142 lignes. Le poser est un préalable, pas une option."""
    assert "docs/raccord/README.md" in PROCEDURE
    assert "préalable" in PROCEDURE or "avant" in PROCEDURE


def test_the_freeze_comes_before_the_stock_import():
    assert PROCEDURE.index("Geler Grocy") < PROCEDURE.index("import_grocy_stock")


def test_the_catalogue_replay_comes_before_the_stock():
    """La cible bouge : le rejeu rattrape ce qui a été créé depuis, au moins
    le produit #350."""
    assert PROCEDURE.index("import_grocy_catalog") < PROCEDURE.index(
        "import_grocy_stock")


def test_the_equipment_import_comes_before_the_raccord():
    """Seule dépendance d'ordre du lot 5 vers le lot 7 : sans l'import, le
    raccord FERME 14 tâches de pile au lieu de les déplacer."""
    assert PROCEDURE.index("import_grocy_equipment") < PROCEDURE.index(
        "docs/raccord")


def test_nothing_is_stopped_before_the_check_is_green():
    assert PROCEDURE.index("check_grocy_migration") < PROCEDURE.index(
        "docker compose stop")
    assert "tant que `ok` n'est pas `true`" in PROCEDURE


def test_the_proof_happens_while_grocy_is_still_running():
    """Ouvrir une recette, vérifier l'image, arrêter TEMPORAIREMENT, rouvrir,
    redémarrer. On n'éteint pas encore."""
    assert "docker start grocy" in PROCEDURE
    assert "temporairement" in PROCEDURE.lower()


def test_the_stop_is_never_a_down_minus_v():
    assert "docker compose stop" in PROCEDURE
    assert "down -v" not in PROCEDURE.replace("PAS `down -v`", "")
    assert "watchtower" in PROCEDURE.lower()      # sinon il le relance


def test_the_retention_periods_are_written():
    for duree in ("12 mois", "3 mois"):
        assert duree in RETOUR


def test_grocy_is_never_restarted_to_be_used_again():
    """Il est rallumé pour être LU. Le sens de la migration ne s'inverse
    jamais — décision du lot 0, « Écriture vers Grocy : jamais »."""
    assert "ne rien saisir" in RETOUR
    assert "127.0.0.1:9283" in RETOUR      # l'accès local, après le retrait Pomerium


def test_what_never_comes_back_is_said_before_not_after():
    assert "statistiques long terme" in RETOUR
    assert "ajout seul" in RETOUR


def test_the_dead_things_are_listed_so_nobody_repairs_them():
    for mort in ("wallpanel/rooms.py", "lovelace.wallpanel_cuisine",
                 "wallpanel-app"):
        assert mort in INVENTAIRE


def test_the_docs_never_ask_the_component_to_stop_anything():
    """Toutes les commandes docker de ces documents sont adressées au
    PROPRIÉTAIRE. Aucune n'est appelable par le composant."""
    for fichier in (PROCEDURE, INVENTAIRE, RETOUR):
        assert "hass.services" not in fichier or "docker" not in fichier


def test_the_procedure_says_the_component_never_stops_grocy():
    """Écrit noir sur blanc, parce que c'est la contrainte qui prime sur tout
    le reste du lot."""
    assert "geste humain" in PROCEDURE


def test_exploitation_says_the_journal_starts_on_switchover_day():
    texte = (RACINE / "docs/exploitation.md").read_text("utf-8")
    assert "commence le jour de la bascule" in texte
    assert "local_todo" in texte        # le chemin de repli des 6 corvées


def test_exploitation_says_where_the_pictures_live():
    texte = (RACINE / "docs/exploitation.md").read_text("utf-8")
    assert "media/home_stock" in texte
    assert "www/" in texte              # et pourquoi surtout pas là
