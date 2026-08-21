"""Une seule table de correspondance des unités, partagée, jamais copiée."""
from custom_components.home_stock import import_grocy
from custom_components.home_stock.grocy import units


def test_import_grocy_reuses_the_very_same_objects():
    """L'IDENTITÉ, pas l'égalité. Une copie qui dit la même chose aujourd'hui
    est précisément ce que ce test existe pour interdire : elle dira autre
    chose le jour où quelqu'un ajoutera « Flacon » d'un seul côté."""
    assert import_grocy.MASS_UNITS is units.MASS_UNITS
    assert import_grocy.VOLUME_UNITS is units.VOLUME_UNITS
    assert import_grocy.CONTAINER_UNITS is units.CONTAINER_UNITS
    assert import_grocy.DOSAGE_UNITS is units.DOSAGE_UNITS


def test_the_three_families_and_the_refusal():
    assert units.base_unit("kg") == ("g", 1000.0)
    assert units.base_unit("cl") == ("ml", 10.0)
    assert units.base_unit("Bouteille") == ("piece", 1.0)
    assert units.base_unit("Lot") == ("piece", 1.0)
    assert units.base_unit("Pot") == ("piece", 1.0)
    assert units.base_unit("cs") is None      # dosage, pas stockage
    assert units.base_unit("parsec") is None


def test_a_dosage_unit_is_never_a_stock_unit():
    """« cs » et « cc » doivent rester hors des trois familles : un produit
    stocké « à la cuillère » est une erreur de saisie, pas une unité."""
    for name in units.DOSAGE_UNITS:
        assert units.base_unit(name) is None


def test_no_unit_name_belongs_to_two_families():
    familles = [set(units.MASS_UNITS), set(units.VOLUME_UNITS),
                units.CONTAINER_UNITS, units.DOSAGE_UNITS]
    for i, une in enumerate(familles):
        for autre in familles[i + 1:]:
            assert not (une & autre)
