"""Le matériau d'emballage, lu à la volée dans `article.off_raw`.

Aucune colonne : la donnée est lue une fois par ouverture de l'écran
« manger », sur un seul article, et n'est jamais agrégée, triée, filtrée ni
jointe (spec § 9.4).
"""
import json

from custom_components.home_stock.off.packaging import bins_from_raw


def _raw(**payload) -> str:
    return json.dumps({"product_name": "Yaourt", **payload})


def test_a_structured_packaging_yields_its_bins():
    raw = _raw(packagings=[
        {"material": "en:pp-polypropylene", "shape": "en:pot"},
        {"material": "en:cardboard", "shape": "en:sleeve"},
    ])
    assert bins_from_raw(raw) == {
        "bins": ["yellow"],
        "materials": ["en:pp-polypropylene", "en:cardboard"],
    }


def test_two_components_in_two_bins_give_two_bins():
    # L'ordre de sortie suit RECYCLING_BINS, jamais l'ordre de lecture : deux
    # fiches décrivant le même emballage doivent rendre la même liste, sinon la
    # ligne de l'écran « manger » change de mot d'un article à l'autre.
    raw = _raw(packagings=[{"material": "en:glass"}, {"material": "en:cardboard"}])
    assert bins_from_raw(raw)["bins"] == ["yellow", "glass"]
    inverse = _raw(packagings=[{"material": "en:cardboard"}, {"material": "en:glass"}])
    assert bins_from_raw(inverse)["bins"] == ["yellow", "glass"]


def test_bins_are_deduplicated_by_bin_not_by_material():
    """Le pot et son étui vont dans le même bac : ce qu'on doit faire, c'est
    ouvrir UN couvercle, pas lire un inventaire."""
    raw = _raw(packagings=[{"material": "en:plastic"}, {"material": "en:cardboard"},
                           {"material": "en:pp-polypropylene"}])
    assert bins_from_raw(raw)["bins"] == ["yellow"]


def test_packaging_tags_are_the_fallback_only():
    assert bins_from_raw(_raw(packaging_tags=["en:glass", "fr:bocal"]))["bins"] == ["glass"]
    # `packagings` présent : les tags ne sont même pas regardés.
    both = _raw(packagings=[{"material": "en:glass"}], packaging_tags=["en:plastic"])
    assert bins_from_raw(both)["bins"] == ["glass"]


def test_an_empty_packagings_list_falls_back_to_the_tags():
    raw = _raw(packagings=[], packaging_tags=["en:cardboard"])
    assert bins_from_raw(raw)["bins"] == ["yellow"]


def test_an_unknown_material_is_ignored_and_the_others_survive():
    raw = _raw(packagings=[{"material": "en:unobtainium"}, {"material": "en:glass"}])
    assert bins_from_raw(raw) == {"bins": ["glass"], "materials": ["en:glass"]}


def test_nothing_known_yields_nothing_at_all():
    for raw in (_raw(packagings=[{"material": "en:unobtainium"}]),
                _raw(packaging_tags=["fr:bocal"]),        # une forme, pas un matériau
                _raw()):
        assert bins_from_raw(raw) is None


def test_anything_unusable_yields_none_without_raising():
    for raw in (None, "", "{tronqu", "[1, 2]", '"une chaine"', "{}",
                _raw(packagings="du plastique"),
                _raw(packagings=[1, 2, 3]),
                _raw(packagings=[{"shape": "en:pot"}]),   # composant sans matériau
                _raw(packaging_tags="en:glass"),
                _raw(packaging_tags=[None, 42])):
        assert bins_from_raw(raw) is None


def test_the_bins_returned_are_all_declared_in_the_constant():
    from custom_components.home_stock.const import RECYCLING_BINS

    raw = _raw(packagings=[{"material": "en:glass"}, {"material": "en:cardboard"},
                           {"material": "en:plastic-film"}])
    assert set(bins_from_raw(raw)["bins"]) <= set(RECYCLING_BINS)
