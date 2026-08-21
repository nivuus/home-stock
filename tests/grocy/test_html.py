"""Le découpeur, sur les 102 descriptions réelles.

Trois pièges mesurés sur la base et non négociables : aucun <h3> nu, une
description sans page rend UNE page, et l'échappement se défait une seule
fois. Chacun a son test, et chacun de ces tests doit tomber seul.
"""
import pytest

from custom_components.home_stock.grocy import html as gh


def _description(grocy_reel, recipe_id):
    return next(l["description"] for l in grocy_reel["recipes"] if l["id"] == recipe_id)


def _normales(grocy_reel):
    return [l for l in grocy_reel["recipes"] if str(l["type"]) == "normal"]


def _type_un(grocy_reel):
    return [l for l in grocy_reel["recipes"] if str(l["type"]) == "1"]


def test_the_three_hundred_and_twenty_three_pages(grocy_reel):
    """La somme exacte, sur les 87 recettes `normal`. Un découpeur qui rend
    322 ou 324 a mangé ou inventé une page, et c'est invisible autrement."""
    total = sum(len(gh.decouper(l["description"])) for l in _normales(grocy_reel))
    assert total == 323


def test_a_description_without_pages_yields_one_page_not_zero(grocy_reel):
    """LE test qui empêche la perte silencieuse des 15 recettes de type 1."""
    for ligne in _type_un(grocy_reel):
        pages = gh.decouper(ligne["description"])
        assert len(pages) == 1, ligne["name"]
        assert pages[0].bullets, ligne["name"]      # le <ol> est bien dedans


def test_every_normal_recipe_has_exactly_one_ingredients_page(grocy_reel):
    for ligne in _normales(grocy_reel):
        pages = gh.decouper(ligne["description"])
        assert len([p for p in pages if p.kind == "ingredients"]) == 1, ligne["name"]


def test_a_styled_h3_is_still_a_title():
    """Il n'existe AUCUN <h3> nu dans la base : 234 sur 234 portent un style.
    Un motif littéral `<h3>` trouve zéro titre et rend des étapes sans nom."""
    page = gh.decouper(
        '<div class="page-recipes">'
        '<h3 style="color:#333;">Étape 2 — Saisir le poulet</h3>'
        '<ol><li>Chauffer la poêle.</li></ol></div>')[0]
    assert page.kind == "step"
    assert page.title == "Saisir le poulet"


def test_the_step_number_orders_but_does_not_title():
    pages = gh.decouper(
        '<div class="page-recipes"><h3 style="color:#333;">Étape 10 — Dresser</h3>'
        '<ol><li>Servir.</li></ol></div>')
    assert pages[0].title == "Dresser"


def test_entities_are_unescaped_exactly_once():
    """Grocy redécode &#x27; en ' à l'enregistrement. Un second passage
    transformerait un &amp;lt; légitime en <."""
    assert gh.texte("<li>l&#x27;huile d&#x27;olive</li>") == "l'huile d'olive"
    assert gh.texte("<li>a &amp;lt; b</li>") == "a &lt; b"


def test_strong_is_stripped_but_its_words_stay():
    assert gh.texte("<li>saisir <strong>4 min par face</strong></li>") \
        == "saisir 4 min par face"


def test_the_instruction_bullets_of_the_step_pages(grocy_reel):
    total = sum(len(p.bullets) for l in _normales(grocy_reel)
                for p in gh.decouper(l["description"]) if p.kind == "step")
    assert total == 468


def test_the_ingredients_page_bullets_are_not_counted_as_instructions(grocy_reel):
    """415 <li> dans les <ul> d'ingrédients, pour 414 lignes de recipes_pos :
    la page est un miroir, et le découpeur ne doit surtout pas la confondre
    avec une étape."""
    total = sum(len(p.bullets) for l in _normales(grocy_reel)
                for p in gh.decouper(l["description"]) if p.kind == "ingredients")
    assert total == 415


def test_the_two_hundred_and_twenty_nine_images(grocy_reel):
    total = sum(len(p.images) for l in grocy_reel["recipes"]
                for p in gh.decouper(l["description"]))
    assert total == 229


def test_the_meta_line_gives_minutes_and_utensils(grocy_reel):
    m = gh.meta(_description(grocy_reel, 1))
    assert isinstance(m.total_minutes, int) and 1 <= m.total_minutes <= 600
    assert m.utensils
    assert m.summary


def test_every_normal_recipe_has_a_meta_line(grocy_reel):
    """87 lignes méta pour 87 recettes. Une seule absente et le compteur
    total_minutes serait NULL sans que personne s'en aperçoive."""
    avec = [l for l in _normales(grocy_reel)
            if gh.meta(l["description"]).total_minutes is not None]
    assert len(avec) == 87


def test_a_duration_in_seconds_or_a_range_is_still_a_duration():
    """« 15 min » n'est pas la seule forme écrite : la mayonnaise au mixeur dit
    « 30 sec » et le gaspacho « 8-10 min ». Un motif qui n'accepte que les
    minutes entières rend deux total_minutes à NULL, en silence. Une fourchette
    se lit par sa borne HAUTE, les secondes montent à la minute."""
    couverture = ('<div class="page-recipes"><div>'
                  '<span>⏱ {duree}</span><span>🔥 ~450 kcal</span>'
                  '<span>{ustensile}</span></div>'
                  '<p style="color:#555;">Une accroche.</p></div>')
    assert gh.meta(couverture.format(duree="8-10 min",
                                     ustensile="🍳 Mixeur")).total_minutes == 10
    assert gh.meta(couverture.format(duree="30 sec",
                                     ustensile="🌀 Mixeur")).total_minutes == 1
    assert gh.meta(couverture.format(duree="15 min",
                                     ustensile="🍳 Poêle")).total_minutes == 15


def test_every_normal_recipe_names_its_utensils(grocy_reel):
    """87 sur 87. Les ustensiles sont le TROISIÈME span, toujours — pas
    « ce qui suit un 🍳 » : une recette porte un 🌀 à la place, et la chercher
    par son emoji la perdrait sans bruit."""
    avec = [l for l in _normales(grocy_reel)
            if gh.meta(l["description"]).utensils]
    assert len(avec) == 87
    mayo = next(l for l in _normales(grocy_reel) if l["id"] == 67)
    assert gh.meta(mayo["description"]).utensils == "Mixeur plongeur"


def test_a_type_one_recipe_has_no_meta_and_that_is_not_an_error(grocy_reel):
    for ligne in _type_un(grocy_reel):
        m = gh.meta(ligne["description"])
        assert m.total_minutes is None
        assert m.utensils is None


def test_the_kcal_of_the_meta_line_is_deliberately_not_returned(grocy_reel):
    """C'est une valeur CALCULÉE par recettes_miseenpage.py depuis le
    catalogue. La graver ici, c'est graver un chiffre daté."""
    assert not hasattr(gh.meta(_description(grocy_reel, 1)), "kcal")


def test_an_empty_description_yields_no_page():
    assert gh.decouper("") == []
    assert gh.decouper(None) == []


def test_nested_page_divs_do_not_produce_a_page():
    """La découpe porte sur les <div class="page-recipes"> de PREMIER niveau.
    Un compte naïf de balises ouvrantes en trouverait davantage."""
    pages = gh.decouper(
        '<div class="page-recipes"><div class="page-recipes">'
        '<h3 style="color:#333;">Étape 1 — X</h3><ol><li>a</li></ol>'
        '</div></div>')
    assert len(pages) == 1
