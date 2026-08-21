"""Which price the panel offers when an article is scanned."""
from custom_components.home_stock.domain.pricing import suggest_price


def test_the_price_of_this_shop_wins_over_everything():
    result = suggest_price(in_store=0.002, open_prices=0.0015, last_known=0.003,
                           store="Leclerc")
    assert result.price_per_base_unit == 0.002
    assert result.source == "store"
    assert result.store == "Leclerc"


def test_open_prices_fills_in_when_this_shop_is_unknown():
    result = suggest_price(in_store=None, open_prices=0.0015, last_known=0.003,
                           store="Lidl")
    assert result.price_per_base_unit == 0.0015
    assert result.source == "open_prices"


def test_the_last_known_price_is_the_final_fallback():
    result = suggest_price(in_store=None, open_prices=None, last_known=0.003, store=None)
    assert result.price_per_base_unit == 0.003
    assert result.source == "last_known"


def test_nothing_known_means_nothing_suggested():
    """This is the one moment the numeric keypad is allowed to open."""
    result = suggest_price(in_store=None, open_prices=None, last_known=None, store=None)
    assert result.price_per_base_unit is None
    assert result.source is None


def test_a_zero_price_is_a_real_price_and_is_kept():
    result = suggest_price(in_store=0.0, open_prices=0.002, last_known=None, store="Leclerc")
    assert result.price_per_base_unit == 0.0
    assert result.source == "store"


def test_a_zero_open_prices_price_is_not_treated_as_absent():
    """A truthiness check here would fall through to last_known instead."""
    result = suggest_price(in_store=None, open_prices=0.0, last_known=0.003, store="Lidl")
    assert result.price_per_base_unit == 0.0
    assert result.source == "open_prices"


def test_a_zero_last_known_price_is_not_treated_as_absent():
    """A truthiness check here would fall through to no suggestion at all."""
    result = suggest_price(in_store=None, open_prices=None, last_known=0.0, store=None)
    assert result.price_per_base_unit == 0.0
    assert result.source == "last_known"


# --- amendement A3 : un prix suggéré n'est pas un prix observé --------------

def test_a_store_price_is_observed_and_open_prices_is_not():
    """Seule la branche « ce magasin » repose sur une observation réelle :
    quelqu'un a vu ce prix ici. Les deux autres sont des suppositions, et
    les inscrire comme observées fait que la cascade se nourrit d'elle-même."""
    assert suggest_price(in_store=0.002, open_prices=None, last_known=None,
                         store="Leclerc").observed is True
    assert suggest_price(in_store=None, open_prices=0.003, last_known=None,
                         store="Leclerc").observed is False
    assert suggest_price(in_store=None, open_prices=None, last_known=0.004,
                         store=None).observed is False


def test_nothing_known_is_not_observed_either():
    assert suggest_price(in_store=None, open_prices=None, last_known=None,
                         store=None).observed is False
