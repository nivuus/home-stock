"""Les fixtures sont la mesure. Si elles bougent, tout le lot 7 bouge.

Ces tests ne testent pas du code : ils testent que les données figées le
2026-08-21 sont toujours celles sur lesquelles la spec a été écrite. Un
chiffre qui change ici est un amendement de spec, jamais une correction de
test.
"""
import re


def test_the_hundred_and_two_recipes(grocy_reel):
    recettes = grocy_reel["recipes"]
    assert len(recettes) == 102
    types = {}
    for ligne in recettes:
        types[str(ligne["type"])] = types.get(str(ligne["type"]), 0) + 1
    assert types == {"normal": 87, "1": 15}
    # Aucune copie fantôme : elles sont toutes à identifiant négatif.
    assert all(ligne["id"] > 0 for ligne in recettes)


def test_the_five_hundred_and_ten_ingredient_rows(grocy_reel):
    ids = {ligne["id"] for ligne in grocy_reel["recipes"]}
    lignes = grocy_reel["recipes_pos"]
    retenues = [l for l in lignes if l["recipe_id"] in ids]
    orphelines = [l for l in lignes if l["recipe_id"] not in ids]
    assert len(retenues) == 510
    assert len(orphelines) == 200      # résidus des recettes du jour/semaine


def test_the_structure_the_splitter_will_meet(grocy_reel):
    html = "".join(l["description"] or "" for l in grocy_reel["recipes"])
    assert html.count('<div class="page-recipes">') == 323
    assert html.count("<h3") == 234
    assert "<h3>" not in html          # AUCUN h3 nu : ils sont tous stylés
    assert html.count("<img") == 229


def test_three_quarters_of_the_hashes_are_css_colours(grocy_reel):
    """443 `#` dans la base, 327 sont des couleurs. Un motif de minuteur trop
    lâche transforme `color:#888;font-size:12px` en un minuteur « 888;font-size »
    de 12 secondes — c'est arrivé pendant l'analyse de la spec."""
    html = "".join(l["description"] or "" for l in grocy_reel["recipes"])
    assert html.count("#") == 443
    couleurs = len(re.findall(r"#[0-9a-fA-F]{3,6}\b(?=[;\"'])", html))
    assert couleurs == 327


def test_the_fifteen_type_one_recipes_have_no_pages(grocy_reel):
    """Leur description est un <ol><li> nu. C'est la forme que le découpeur
    doit rendre en UNE page, jamais en zéro."""
    for ligne in grocy_reel["recipes"]:
        if str(ligne["type"]) == "1":
            assert '<div class="page-recipes">' not in (ligne["description"] or "")
            assert "<ol" in ligne["description"]


def test_the_hundred_and_eight_stock_rows(grocy_reel):
    lots = grocy_reel["stock"]
    assert len(lots) == 108
    assert len({l["product_id"] for l in lots}) == 87
    sentinelles = [l for l in lots if l["best_before_date"] == "2999-12-31"]
    assert len(sentinelles) == 10
    sans_emplacement = [l for l in lots if not l["location_id"] or l["location_id"] == 1]
    assert len(sans_emplacement) == 29


def test_the_forty_two_future_meal_plan_rows(grocy_reel):
    plan = grocy_reel["meal_plan"]
    assert len(plan) == 108
    assert len({l["section_id"] for l in plan}) == 4      # dont la ligne -1


def test_the_nine_open_shopping_rows(grocy_reel):
    lignes = grocy_reel["shopping_list"]
    assert len(lignes) == 25
    assert len([l for l in lignes if not l["done"]]) == 9


def test_the_thirty_conversions_are_fifteen_round_trips(grocy_reel):
    assert len(grocy_reel["quantity_unit_conversions"]) == 30


def test_the_recipe_that_kept_its_real_data_uris(grocy_reel):
    """L'unique recette non stubbée : c'est elle qui prouve que le décodeur
    écrit un VRAI JPEG et non le stub des 101 autres.

    La spec disait « la recette 41 ». La 41 ne porte AUCUN data-URI (elle
    pointe une image hébergée par Grocy) : la première qui en porte est la 69,
    et elle en porte deux. Amendement A1 du § 22.
    """
    intactes = {l["recipe_id"] for l in grocy_reel["inline_images"]
                if not l["stubbed"]}
    assert intactes == {69}
    r69 = next(l for l in grocy_reel["recipes"] if l["id"] == 69)
    assert "data:image/jpeg;base64," in r69["description"]
    assert len(r69["description"]) > 100_000


def test_every_other_data_uri_was_stubbed_and_its_original_recorded(grocy_reel):
    """Les 60 autres charges utiles sont remplacées par un JPEG 1×1 valide, et
    inline_images.json garde de chacune sa longueur et son SHA-256 : la fixture
    est allégée, la trace de ce qu'elle remplace ne l'est pas."""
    inline = grocy_reel["inline_images"]
    assert len(inline) == 62
    assert len([l for l in inline if l["stubbed"]]) == 60
    assert all(len(l["original_sha256"]) == 64 for l in inline)
    assert all(l["original_base64_length"] > 0 for l in inline)
