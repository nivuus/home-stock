"""Le découpeur, sur les 102 descriptions réelles.

Trois pièges mesurés sur la base et non négociables : aucun <h3> nu, une
description sans page rend UNE page, et l'échappement se défait une seule
fois. Chacun a son test, et chacun de ces tests doit tomber seul.
"""
import pytest

from custom_components.home_stock.grocy import html as gh


def _description(grocy_reel, recipe_id):
    return next(ligne["description"] for ligne in grocy_reel["recipes"] if ligne["id"] == recipe_id)


def _normales(grocy_reel):
    return [ligne for ligne in grocy_reel["recipes"] if str(ligne["type"]) == "normal"]


def _type_un(grocy_reel):
    return [ligne for ligne in grocy_reel["recipes"] if str(ligne["type"]) == "1"]


def test_the_three_hundred_and_twenty_three_pages(grocy_reel):
    """La somme exacte, sur les 87 recettes `normal`. Un découpeur qui rend
    322 ou 324 a mangé ou inventé une page, et c'est invisible autrement."""
    total = sum(len(gh.decouper(ligne["description"])) for ligne in _normales(grocy_reel))
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
    total = sum(len(p.bullets) for ligne in _normales(grocy_reel)
                for p in gh.decouper(ligne["description"]) if p.kind == "step")
    assert total == 468


def test_the_ingredients_page_bullets_are_not_counted_as_instructions(grocy_reel):
    """415 <li> dans les <ul> d'ingrédients, pour 414 lignes de recipes_pos :
    la page est un miroir, et le découpeur ne doit surtout pas la confondre
    avec une étape."""
    total = sum(len(p.bullets) for ligne in _normales(grocy_reel)
                for p in gh.decouper(ligne["description"]) if p.kind == "ingredients")
    assert total == 415


def test_the_two_hundred_and_twenty_nine_images(grocy_reel):
    total = sum(len(p.images) for ligne in grocy_reel["recipes"]
                for p in gh.decouper(ligne["description"]))
    assert total == 229


def test_the_meta_line_gives_minutes_and_utensils(grocy_reel):
    m = gh.meta(_description(grocy_reel, 1))
    assert isinstance(m.total_minutes, int) and 1 <= m.total_minutes <= 600
    assert m.utensils
    assert m.summary


def test_every_normal_recipe_has_a_meta_line(grocy_reel):
    """87 lignes méta pour 87 recettes. Une seule absente et le compteur
    total_minutes serait NULL sans que personne s'en aperçoive."""
    avec = [ligne for ligne in _normales(grocy_reel)
            if gh.meta(ligne["description"]).total_minutes is not None]
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
    avec = [ligne for ligne in _normales(grocy_reel)
            if gh.meta(ligne["description"]).utensils]
    assert len(avec) == 87
    mayo = next(ligne for ligne in _normales(grocy_reel) if ligne["id"] == 67)
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


# --- minuteurs --------------------------------------------------------------

def test_a_label_with_spaces_survives():
    """#Repos poulet:600, pas #Repos. Un motif #(\\S+): coupe au premier
    espace et perd la moitié du libellé, sans rien signaler."""
    assert gh.minuteurs("Laisser reposer. #Repos poulet:600") == [("Repos poulet", 600)]
    assert gh.minuteurs("#Cabillaud face 1:180") == [("Cabillaud face 1", 180)]
    assert gh.minuteurs("#Airfryer légumes:1050") == [("Airfryer légumes", 1050)]


@pytest.mark.parametrize("fragment", [
    'style="color:#888;font-size:12px"',
    'style="color:#333;"',
    '<p style="color:#555;font-size:14px;">Une accroche.</p>',
    "#fff",
    "background:#1a1a1a;padding:12px",
])
def test_a_css_colour_is_never_a_timer(fragment):
    """327 des 443 # de la base sont des couleurs. C'est l'erreur qui a été
    commise pour de vrai sur la première expression essayée."""
    assert gh.minuteurs(fragment) == []


def test_the_hundred_and_sixteen_timers(grocy_reel):
    """116, pas 115. Un minuteur perdu, c'est une cuisson non minutée sur une
    tablette, et personne ne s'en aperçoit avant d'avoir brûlé le poisson."""
    total = 0
    for ligne in grocy_reel["recipes"]:
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                total += len(gh.minuteurs(puce))
    assert total == 116


def test_every_timer_lives_in_a_normal_recipe(grocy_reel):
    for ligne in _type_un(grocy_reel):
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                assert gh.minuteurs(puce) == [], ligne["name"]


def test_durations_stay_inside_the_measured_range(grocy_reel):
    durees = [s for ligne in grocy_reel["recipes"]
              for p in gh.decouper(ligne["description"]) for b in p.bullets
              for _, s in gh.minuteurs(b)]
    assert min(durees) == 25
    assert max(durees) == 3600


def test_a_bullet_with_two_timers_becomes_two_instructions():
    puce = "Poêle à feu vif, saisir 4 min par face. #Poulet face 1:240 #Poulet face 2:240"
    resultat = gh.instructions(puce)
    assert len(resultat) == 2
    assert resultat[0].timer_label == "Poulet face 1" and resultat[0].timer_seconds == 240
    assert "saisir 4 min par face" in resultat[0].text
    # Le texte de la seconde est le libellé du second minuteur : une chaîne
    # qui existe DÉJÀ dans la source, jamais une phrase inventée.
    assert resultat[1].text == "Poulet face 2"
    assert resultat[1].timer_seconds == 240


def test_the_eight_double_bullets_and_no_more(grocy_reel):
    doubles = [b for ligne in grocy_reel["recipes"]
               for p in gh.decouper(ligne["description"]) for b in p.bullets
               if len(gh.minuteurs(b)) == 2]
    assert len(doubles) == 8


def test_no_bullet_carries_three_timers(grocy_reel):
    """Le dédoublement ne traite que la paire. Trois minuteurs sur une puce
    demanderaient une décision qui n'a pas été prise — mieux vaut le savoir
    par un test rouge que par une instruction avalée."""
    for ligne in grocy_reel["recipes"]:
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                assert len(gh.minuteurs(puce)) <= 2


def test_the_marker_never_stays_in_the_text():
    resultat = gh.instructions("Laisser reposer. #Repos poulet:600")
    assert "#" not in resultat[0].text
    assert resultat[0].text == "Laisser reposer."


def test_five_hundred_and_sixty_one_instructions_in_all(grocy_reel):
    """553 puces + les 8 dédoublements. C'est le chiffre que C8 contrôlera."""
    total = sum(len(gh.instructions(b)) for ligne in grocy_reel["recipes"]
                for p in gh.decouper(ligne["description"])
                if p.kind != "ingredients" for b in p.bullets)
    assert total == 561


def test_the_check_of_m004_can_never_be_violated(grocy_reel):
    """CHECK ((timer_label IS NULL) = (timer_seconds IS NULL)) : le motif
    exigeant les deux, une puce à libellé sans durée ne peut pas naître."""
    for ligne in grocy_reel["recipes"]:
        for page in gh.decouper(ligne["description"]):
            for puce in page.bullets:
                for inst in gh.instructions(puce):
                    assert (inst.timer_label is None) == (inst.timer_seconds is None)
