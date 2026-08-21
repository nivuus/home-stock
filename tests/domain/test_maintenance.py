"""La règle qui crée et ferme les tâches de pile, testée sans Home Assistant.

Deux invariants dominent tout le fichier :
  - `items ⊆ keep` : sa violation est le clignotement de tâche que CLAUDE.md
    décrit — la tâche apparaît, la synchro suivante la ferme, la suivante la
    rouvre, et Bleuenn l'annonce à chaque fois.
  - jamais de fermeture sur un capteur indisponible : tout ce qui n'est pas une
    mesure numérique fraîche produit `keep` SANS `items`.
"""
from datetime import datetime, timedelta

import pytest

from custom_components.home_stock.const import BATTERY_MUTE_HOURS
from custom_components.home_stock.domain.maintenance import (
    battery_plan, mute_summary_for, summary_for,
)

NOW = datetime(2026, 8, 21, 12, 0, 0)


def _pile(**kw):
    base = {"id": 1, "label": "Velux (CH)", "kind": "primary", "tracked": True,
            "entity_id": "sensor.velux_ch_batterie", "state": "18",
            "last_percent": 18.0, "last_reading_at": "2026-08-21T11:00:00",
            "low_percent": 20.0, "keep_percent": 25.0, "spare": None}
    return {**base, **kw}


def _resumes(plan):
    return [i["summary"] for i in plan["items"]]


def test_the_three_kinds_give_the_three_verbs():
    assert summary_for("primary", "Velux (CH)") == "Pile à changer — Velux (CH)"
    assert summary_for("rechargeable_cell", "Capteur") == "Piles à recharger — Capteur"
    assert summary_for("built_in", "Rideau") == "Recharger — Rideau"
    assert mute_summary_for("Velux (CH)") == "Pile HS ? — Velux (CH)"


def test_a_battery_under_its_threshold_becomes_an_item():
    plan = battery_plan([_pile()], now=NOW)
    assert _resumes(plan) == ["Pile à changer — Velux (CH)"]
    assert plan["items"][0]["description"] == "18 %"
    assert plan["items"][0]["entity"] == "sensor.velux_ch_batterie"


def test_the_description_is_a_whole_percent_like_the_macro_renders_it():
    """Le macro rend `s.state | int(-1)`. Écrire « 19.6 % » rafraîchirait les
    14 tâches le jour de la bascule sans qu'aucune valeur n'ait bougé."""
    plan = battery_plan([_pile(state="19.6", last_percent=19.6)], now=NOW)
    assert plan["items"][0]["description"] == "19 %"


def test_hysteresis_between_the_two_thresholds():
    # 22 % : au-dessus du seuil d'apparition, sous celui de maintien.
    plan = battery_plan([_pile(state="22", last_percent=22.0)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — Velux (CH)"]
    # 26 % : la tâche a le droit de se fermer.
    plan = battery_plan([_pile(state="26", last_percent=26.0)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == []


def test_the_thresholds_are_per_battery():
    """Une CR2032 annonce 100 % jusqu'à mourir en trois jours ; une AAA descend
    lentement. C'est le cas concret qui justifie des seuils déclarables."""
    plan = battery_plan([_pile(state="45", last_percent=45.0,
                               low_percent=50.0, keep_percent=60.0)], now=NOW)
    assert _resumes(plan) == ["Pile à changer — Velux (CH)"]


def test_a_mute_sensor_protects_both_summaries():
    """Une pile faible qui se tait ne prouve pas qu'elle a été changée : on
    garde « Pile HS ? — X » ET « Pile à changer — X »."""
    vieux = (NOW - timedelta(hours=BATTERY_MUTE_HOURS + 1)).isoformat()
    plan = battery_plan([_pile(state="unavailable", last_reading_at=vieux)], now=NOW)
    assert _resumes(plan) == ["Pile HS ? — Velux (CH)"]
    assert set(plan["keep"]) == {"Pile HS ? — Velux (CH)", "Pile à changer — Velux (CH)"}
    assert "27 h" in plan["items"][0]["description"]


def test_a_sensor_mute_for_less_than_the_threshold_creates_nothing():
    """25 h de silence, c'est un appareil sur pile qui n'a rien eu à dire :
    Z2M ne le déclare `offline` qu'après 25 h. Aucun item — mais keep, parce
    qu'on ne ferme rien sur un capteur muet."""
    recent = (NOW - timedelta(hours=BATTERY_MUTE_HOURS - 1)).isoformat()
    plan = battery_plan([_pile(state="unavailable", last_reading_at=recent)], now=NOW)
    assert plan["items"] == []
    assert set(plan["keep"]) == {"Pile HS ? — Velux (CH)", "Pile à changer — Velux (CH)"}


def test_a_never_read_battery_produces_no_item_at_all():
    """Déclaration fraîche : `last_reading_at` est NULL. Ni item de niveau, ni
    « Pile HS ? » — on ne sait rien, donc on n'affirme rien. keep seulement."""
    plan = battery_plan([_pile(state=None, last_percent=None,
                               last_reading_at=None)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — Velux (CH)"]


def test_a_non_numeric_state_keeps_without_creating():
    for state in ("unknown", "", "faible", "NaN"):
        plan = battery_plan([_pile(state=state, last_percent=None)], now=NOW)
        assert plan["items"] == [], state
        assert plan["keep"] == ["Pile à changer — Velux (CH)"], state


def test_an_orphaned_anchor_never_closes_a_task():
    """L'entrée de registre a disparu (appareil remplacé, migration ZHA → Z2M
    du 2026-07-14 qui en a frappé plusieurs d'un coup) : `entity_id` est None.
    keep sans items, et surtout AUCUNE fermeture."""
    plan = battery_plan([_pile(entity_id=None, state=None)], now=NOW)
    assert plan["items"] == []
    assert plan["keep"] == ["Pile à changer — Velux (CH)"]


def test_an_untracked_battery_is_silent_everywhere():
    """tracked = 0 (tablette murale sur secteur) et tracked = NULL (découvert,
    pas décidé) : ni items, ni keep. Leur visibilité passe par le compteur
    `batteries_undeclared` et par le panneau, pas par todo.maintenance."""
    for tracked in (False, None):
        plan = battery_plan([_pile(tracked=tracked, state="3",
                                   last_percent=3.0)], now=NOW)
        assert plan == {"items": [], "keep": []}, tracked


def test_an_inactive_battery_is_ignored():
    plan = battery_plan([_pile(active=False, state="3", last_percent=3.0)], now=NOW)
    assert plan == {"items": [], "keep": []}


def test_the_spare_enriches_the_description_without_touching_the_summary():
    """Le suffixe est ce que le lot 5 apporte de neuf ; le résumé, lui, ne
    bouge pas d'un caractère, sinon la tâche existante se ferme."""
    plan = battery_plan([_pile(spare={"label": "CR2032", "cell_count": 1,
                                      "in_stock": 0.0})], now=NOW)
    assert plan["items"][0]["summary"] == "Pile à changer — Velux (CH)"
    assert plan["items"][0]["description"] == "18 % — 1× CR2032, aucune en stock"
    plan = battery_plan([_pile(spare={"label": "AAA", "cell_count": 2,
                                      "in_stock": 4.0})], now=NOW)
    assert plan["items"][0]["description"] == "18 % — 2× AAA, 4 en stock"


@pytest.mark.parametrize("pile", [
    _pile(), _pile(state="22", last_percent=22.0), _pile(state="26", last_percent=26.0),
    _pile(state="unavailable", last_reading_at="2026-08-19T00:00:00"),
    _pile(state="unknown"), _pile(entity_id=None, state=None),
    _pile(state=None, last_percent=None, last_reading_at=None),
    _pile(kind="built_in"), _pile(kind="rechargeable_cell"),
])
def test_items_are_always_a_subset_of_keep(pile):
    """L'invariant global. Sa violation EST le clignotement de tâche."""
    plan = battery_plan([pile], now=NOW)
    assert {i["summary"] for i in plan["items"]} <= set(plan["keep"])


def test_the_order_is_stable_and_lowest_first():
    piles = [_pile(id=1, label="A", state="18", last_percent=18.0),
             _pile(id=2, label="B", state="5", last_percent=5.0),
             _pile(id=3, label="C", state="12", last_percent=12.0)]
    assert _resumes(battery_plan(piles, now=NOW)) == [
        "Pile à changer — B", "Pile à changer — C", "Pile à changer — A"]


def test_keep_has_no_duplicates():
    """Deux piles portant le même libellé (deux « Capteur » dans deux pièces)
    ne doivent pas doubler une entrée de keep : `rejectattr('summary','in',…)`
    s'en moque, mais un doublon est le signe d'un libellé à corriger et il ne
    doit pas coûter deux fois."""
    piles = [_pile(id=1, state="22", last_percent=22.0),
             _pile(id=2, state="23", last_percent=23.0)]
    assert battery_plan(piles, now=NOW)["keep"] == ["Pile à changer — Velux (CH)"]


# --- tâche 3 : la fusion du plan, toujours pure -----------------------------

from custom_components.home_stock.domain.maintenance import merge_plan

MACRO = {
    "items": [
        {"summary": "Purificateur — filtre à remplacer",
         "description": "12 %", "entity": "sensor.purificateur_filtre"},
        {"summary": "Arroser Plante Télévision",
         "description": "18 % d'humidité", "entity": "sensor.plante_television_humidite"},
    ],
    "keep": ["Purificateur — filtre à remplacer", "Arroser Plante Télévision"],
}


def test_called_bare_the_merge_returns_the_batteries_alone():
    own = battery_plan([_pile()], now=NOW)
    fusion = merge_plan(own, extra_items=None, extra_keep=None)
    assert fusion == own


def test_the_macro_items_come_first_and_keep_their_order():
    own = battery_plan([_pile()], now=NOW)
    fusion = merge_plan(own, extra_items=MACRO["items"], extra_keep=MACRO["keep"])
    assert [i["summary"] for i in fusion["items"]] == [
        "Purificateur — filtre à remplacer", "Arroser Plante Télévision",
        "Pile à changer — Velux (CH)"]


def test_an_item_it_does_not_understand_is_copied_verbatim():
    """Le service ne doit PAS pouvoir faire disparaître la tâche du
    purificateur parce que la forme d'un item a évolué."""
    bizarres = [{"summary": "Vider la poubelle"},                 # pas d'entity
                {"summary": "Truc", "description": "x", "entity": "y", "urgence": 3},
                {"resume": "clé inconnue"},                       # pas de summary
                "une chaîne toute nue"]
    fusion = merge_plan(battery_plan([], now=NOW),
                        extra_items=bizarres, extra_keep=["Vider la poubelle"])
    assert fusion["items"] == bizarres


def test_a_macro_item_gets_its_spare_suffix_by_entity_not_by_text():
    fusion = merge_plan(
        battery_plan([], now=NOW), extra_items=MACRO["items"], extra_keep=MACRO["keep"],
        spares={"sensor.purificateur_filtre":
                {"label": "Filtre HEPA MB4", "cell_count": 1, "in_stock": 0.0}})
    assert fusion["items"][0]["description"] == "12 % — 1× Filtre HEPA MB4, aucun en stock"
    # La plante n'a pas de rechange : sa description est intacte.
    assert fusion["items"][1]["description"] == "18 % d'humidité"


def test_an_unknown_entity_in_spares_changes_nothing():
    fusion = merge_plan(battery_plan([], now=NOW), extra_items=MACRO["items"],
                        extra_keep=MACRO["keep"],
                        spares={"sensor.disparu": {"label": "X", "cell_count": 1,
                                                   "in_stock": 0.0}})
    assert fusion["items"] == MACRO["items"]


def test_a_summary_present_on_both_sides_is_merged_not_duplicated():
    own = battery_plan([_pile(label="Velux (CH)")], now=NOW)
    doublon = [{"summary": "Pile à changer — Velux (CH)",
                "description": "ancienne description", "entity": "sensor.velux_ch_batterie"}]
    fusion = merge_plan(own, extra_items=doublon, extra_keep=[])
    assert len(fusion["items"]) == 1
    assert fusion["items"][0]["description"] == "ancienne description"


def test_keep_is_the_union_deduplicated_and_ordered():
    own = battery_plan([_pile(state="22", last_percent=22.0)], now=NOW)
    fusion = merge_plan(own, extra_items=[], extra_keep=MACRO["keep"] + ["Arroser Plante Télévision"])
    assert fusion["keep"] == ["Purificateur — filtre à remplacer",
                              "Arroser Plante Télévision",
                              "Pile à changer — Velux (CH)"]


def test_the_merge_preserves_the_subset_invariant():
    own = battery_plan([_pile()], now=NOW)
    fusion = merge_plan(own, extra_items=MACRO["items"], extra_keep=MACRO["keep"])
    assert {i["summary"] for i in fusion["items"] if isinstance(i, dict) and "summary" in i} \
        <= set(fusion["keep"])


def test_extra_keep_that_is_not_a_list_of_strings_is_tolerated():
    """`extra_keep` arrive d'un rendu Jinja : il peut contenir n'importe quoi
    le jour où le macro change. Rien ne doit lever — une exception ici DÉSARME
    la fermeture (tâche 15), ce qui est correct mais coûte une synchro."""
    fusion = merge_plan(battery_plan([], now=NOW), extra_items=[],
                        extra_keep=["ok", None, 42, {"summary": "x"}])
    assert "ok" in fusion["keep"]
