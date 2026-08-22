"""Les deux espaces de noms de `product.external_ref`."""
import pytest

from custom_components.home_stock.grocy.refs import grocy_product_id


@pytest.mark.parametrize("ref, attendu", [
    ("350", 350),
    (350, 350),
    ("  350  ", 350),
    ("-1", -1),
])
def test_un_identifiant_grocy_est_rendu_en_entier(ref, attendu):
    assert grocy_product_id(ref) == attendu


@pytest.mark.parametrize("ref", [
    "grocy:spare:AAA",
    "grocy:spare:CR2032",
    "grocy:spare:9 V",
    "grocy:battery:12",
    None,
    "",
    "   ",
    "350x",
    "3.5",
])
def test_tout_le_reste_n_est_pas_un_produit_grocy(ref):
    """None veut dire « cette ligne ne vient pas du catalogue Grocy ». Un
    appelant qui la traiterait comme une anomalie signalerait cinq faux
    positifs à chaque import."""
    assert grocy_product_id(ref) is None
