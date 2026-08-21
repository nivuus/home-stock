"""Comparer des totaux à des plafonds. Rien d'autre.

Un objectif est un MAXIMUM (spec § 7.5) : sur une journée vide, tout vaut
zéro, rien n'est dépassé, et il n'y a donc rien à protéger contre une alerte
à 4 h 01. Aucune garde « la journée n'est pas vide » ne doit apparaître ici —
elle prouverait qu'un plancher s'est glissé dans le lot.
"""
import pytest

from custom_components.home_stock.domain.goals import exceeded

TODAY = {"kcal": 2400.0, "salt": 8.4, "proteins": 70.0, "fiber": None}
WEEK = {"kcal": 2100.0, "salt": 5.0, "proteins": 68.0, "fiber": None}


def test_no_goal_set_means_nothing_to_report():
    assert exceeded(TODAY, WEEK, {}) == []


def test_a_day_over_its_cap_is_reported():
    assert exceeded(TODAY, WEEK, {"salt": 6.0}) == [
        {"nutrient": "salt", "scope": "day", "value": 8.4, "goal": 6.0, "ratio": 1.4}]


def test_a_goal_reached_exactly_is_not_exceeded():
    """`>`, jamais `>=` : manger exactement son objectif, c'est le tenir."""
    assert exceeded({"salt": 6.0}, {"salt": 6.0}, {"salt": 6.0}) == []


def test_the_week_mean_has_its_own_line_with_the_same_cap():
    result = exceeded({"salt": 2.0}, {"salt": 7.0}, {"salt": 6.0})
    assert [e["scope"] for e in result] == ["week"]


def test_both_windows_can_fire_at_once():
    result = exceeded({"salt": 8.4}, {"salt": 7.2}, {"salt": 6.0})
    assert [e["scope"] for e in result] == ["day", "week"]


def test_entries_are_sorted_by_ratio_descending():
    result = exceeded({"salt": 12.0, "kcal": 2400.0}, {"salt": 1.0, "kcal": 1.0},
                      {"salt": 6.0, "kcal": 2300.0})
    assert [e["nutrient"] for e in result] == ["salt", "kcal"]
    assert result[0]["ratio"] > result[1]["ratio"]


def test_an_empty_day_exceeds_nothing():
    zeros = dict.fromkeys(("kcal", "salt", "proteins"), 0.0)
    assert exceeded(zeros, zeros, {"kcal": 2000.0, "salt": 6.0}) == []


def test_a_missing_or_null_total_is_not_a_breach():
    """Un nutriment que le journal ne sait pas chiffrer n'est pas un
    dépassement : NULL n'est pas 0.0, et ce n'est pas non plus l'infini."""
    assert exceeded({"fiber": None}, {"fiber": None}, {"fiber": 30.0}) == []
    assert exceeded({}, {}, {"fiber": 30.0}) == []


def test_a_goal_set_to_none_is_no_goal_at_all():
    assert exceeded(TODAY, WEEK, {"salt": None}) == []


def test_a_goal_on_an_unknown_nutrient_is_ignored():
    """Le formulaire est fermé sur GOAL_NUTRIENTS, mais des options écrites à
    la main dans `.storage` ne doivent pas faire tomber un coordinateur."""
    assert exceeded(TODAY, WEEK, {"vitamine_x": 1.0}) == []


def test_no_entity_is_ever_read():
    """Garde-fou de lecture : ce module n'importe rien de Home Assistant."""
    import custom_components.home_stock.domain.goals as module
    source = open(module.__file__).read()
    for forbidden in ("homeassistant", "hass", "sensor.", "datetime", "ZoneInfo"):
        assert forbidden not in source
