"""La réconciliation de la liste de courses, sans base et sans Home Assistant.

Même sémantique que la macro `maintenance_plan()` de la maison, mot pour
mot : un seuil d'APPARITION, un seuil de MAINTIEN plus large, et jamais de
fermeture sur une donnée absente.
"""
import pytest

from custom_components.home_stock.const import SHORTAGE_KEEP_FACTOR
from custom_components.home_stock.domain.shoppinglist import (
    Claim, Plan, WantedItem, item_quantity, reconcile, shortage_claim,
)


def _existing(item_id, *, product_id=None, free_text=None, quantity=None,
              checked_at=None, removed_at=None, claims=()):
    return {
        "id": item_id, "product_id": product_id, "free_text": free_text,
        "quantity": quantity, "checked_at": checked_at, "removed_at": removed_at,
        "claims": [{"origin": c.origin, "quantity": c.quantity, "detail": c.detail}
                   for c in claims],
    }


# --- la quantité d'une ligne ------------------------------------------------

def test_two_origins_make_one_line_with_two_claims():
    """Le lait sous son seuil ET manquant pour le gratin de jeudi."""
    wanted = [WantedItem(product_id=7, claims=(
        Claim("shortage", 2000.0, "seuil 2 L"),
        Claim("meal_plan", 1500.0, "Dîner de jeudi"),
    ))]
    plan = reconcile(wanted=wanted, existing=[], session_open=False)
    assert len(plan.to_create) == 1
    assert {c.origin for c in plan.to_create[0].claims} == {"shortage", "meal_plan"}


def test_the_quantity_is_the_maximum_never_the_sum():
    """Seuil = 2 L, recette = 1,5 L → 2 L. Pas 3,5 L."""
    assert item_quantity((Claim("shortage", 2000.0), Claim("meal_plan", 1500.0))) == 2000.0


def test_a_claim_without_a_quantity_never_erases_a_known_one():
    """« Prends du pain » n'écrase pas « 500 g » et ne s'y ajoute pas."""
    assert item_quantity((Claim("shortage", 500.0), Claim("manual", None))) == 500.0
    assert item_quantity((Claim("manual", None), Claim("shortage", 500.0))) == 500.0


def test_an_item_with_no_quantity_at_all_says_what_it_takes():
    """Aucune revendication chiffrée → `quantity is None`, « ce qu'il faut »."""
    assert item_quantity((Claim("manual", None), Claim("recurring", None))) is None
    assert item_quantity(()) is None


# --- les cinq règles du § 7.3 -----------------------------------------------

def test_the_shortage_disappears_but_the_meal_keeps_the_line_alive():
    """On rachète du lait : la revendication `shortage` s'éteint, celle du
    planning tient, la LIGNE survit — et sa quantité retombe à celle du repas."""
    existing = [_existing(1, product_id=7, quantity=2000.0, claims=(
        Claim("shortage", 2000.0), Claim("meal_plan", 1500.0)))]
    wanted = [WantedItem(product_id=7, claims=(Claim("meal_plan", 1500.0),))]

    plan = reconcile(wanted=wanted, existing=existing, session_open=False)

    assert plan.to_remove == ()
    assert plan.claims_to_drop == ({"item_id": 1, "origin": "shortage"},)
    assert plan.to_update == ({"item_id": 1, "quantity": 1500.0},)


def test_an_item_with_no_claim_left_is_removed():
    """`removed_at`, jamais un DELETE."""
    existing = [_existing(1, product_id=7, quantity=2000.0,
                          claims=(Claim("shortage", 2000.0),))]
    plan = reconcile(wanted=[WantedItem(product_id=7, claims=())],
                     existing=existing, session_open=False)
    assert plan.to_remove == (1,)
    assert plan.claims_to_drop == ({"item_id": 1, "origin": "shortage"},)
    assert plan.to_create == ()


def test_a_manual_line_is_never_removed_by_the_robot():
    """Seule dérogation à « la liste appartient au composant », et
    indispensable : sans elle, « prends des piles pour la télécommande du
    salon » disparaîtrait en quinze minutes."""
    existing = [_existing(1, free_text="Piles télécommande salon",
                          claims=(Claim("manual", None, "ajouté à la main"),))]
    plan = reconcile(wanted=[], existing=existing, session_open=False)
    assert plan.to_remove == ()
    assert plan.claims_to_drop == ()


def test_a_manual_claim_survives_next_to_a_dead_one(): 
    existing = [_existing(1, product_id=7, claims=(
        Claim("manual", None), Claim("shortage", 2000.0)))]
    plan = reconcile(wanted=[WantedItem(product_id=7, claims=())],
                     existing=existing, session_open=False)
    assert plan.to_remove == ()
    assert plan.claims_to_drop == ({"item_id": 1, "origin": "shortage"},)


def test_a_checked_item_is_left_alone_while_the_session_is_open():
    """La fenêtre entre le chariot et le placard : la rupture existe encore
    en base, et rien ne doit remettre la ligne pendant qu'on est à la caisse."""
    existing = [_existing(1, product_id=7, checked_at="2026-08-21T10:00:00",
                          claims=(Claim("shortage", 2000.0),))]
    wanted = [WantedItem(product_id=7, claims=(Claim("shortage", 2000.0),))]

    plan = reconcile(wanted=wanted, existing=existing, session_open=True)

    assert plan == Plan((), (), (), (), ())


def test_a_checked_item_is_purged_once_the_session_is_closed():
    """Et une ligne NEUVE est recréée si la rupture persiste : on a coché
    sans acheter, ou pas assez. La liste dit ce qui manque MAINTENANT."""
    existing = [_existing(1, product_id=7, checked_at="2026-08-21T10:00:00",
                          claims=(Claim("shortage", 2000.0),))]
    wanted = [WantedItem(product_id=7, claims=(Claim("shortage", 2000.0),))]

    plan = reconcile(wanted=wanted, existing=existing, session_open=False)

    assert plan.to_remove == (1,)
    assert len(plan.to_create) == 1
    assert plan.to_create[0].product_id == 7


def test_a_checked_item_whose_need_is_gone_is_purged_without_a_new_line():
    existing = [_existing(1, product_id=7, checked_at="2026-08-21T10:00:00",
                          claims=(Claim("shortage", 2000.0),))]
    plan = reconcile(wanted=[], existing=existing, session_open=False)
    assert plan.to_remove == (1,) and plan.to_create == ()


def test_a_removed_line_is_not_put_back_by_the_next_pass():
    """Barrée à la main : la réconciliation s'en souvient."""
    existing = [_existing(1, product_id=7, removed_at="2026-08-21T09:00:00",
                          claims=(Claim("shortage", 2000.0),))]
    wanted = [WantedItem(product_id=7, claims=(Claim("shortage", 2000.0),))]

    plan = reconcile(wanted=wanted, existing=existing, session_open=False)

    assert plan == Plan((), (), (), (), ())


def test_a_free_text_line_never_merges_with_a_product_line():
    """Pas d'appariement par nom : c'est ce qui a produit 35 doublons dans
    Grocy en avril 2026."""
    existing = [_existing(1, free_text="Lait", claims=(Claim("manual", None),))]
    wanted = [WantedItem(product_id=7, claims=(Claim("shortage", 2000.0),))]

    plan = reconcile(wanted=wanted, existing=existing, session_open=False)

    assert len(plan.to_create) == 1
    assert plan.to_create[0].product_id == 7
    assert plan.to_remove == ()


def test_a_claim_whose_quantity_moved_is_rewritten():
    existing = [_existing(1, product_id=7, quantity=2000.0,
                          claims=(Claim("shortage", 2000.0, "seuil 2 L"),))]
    wanted = [WantedItem(product_id=7, claims=(Claim("shortage", 800.0, "seuil 2 L"),))]

    plan = reconcile(wanted=wanted, existing=existing, session_open=False)

    assert plan.claims_to_add == ({"item_id": 1, "claim": Claim("shortage", 800.0, "seuil 2 L")},)
    assert plan.to_update == ({"item_id": 1, "quantity": 800.0},)


def test_an_unchanged_claim_produces_no_write_at_all():
    existing = [_existing(1, product_id=7, quantity=2000.0,
                          claims=(Claim("shortage", 2000.0, "seuil 2 L"),))]
    wanted = [WantedItem(product_id=7, claims=(Claim("shortage", 2000.0, "seuil 2 L"),))]
    assert reconcile(wanted=wanted, existing=existing,
                     session_open=False) == Plan((), (), (), (), ())


def test_reconcile_is_deterministic_and_writes_nothing():
    """Deux appels sur les mêmes entrées rendent le même Plan ; le Plan est
    un `frozen dataclass`, il ne porte aucune connexion."""
    existing = [_existing(1, product_id=7, claims=(Claim("shortage", 2000.0),))]
    wanted = [WantedItem(product_id=9, claims=(Claim("meal_plan", 300.0),))]
    first = reconcile(wanted=wanted, existing=existing, session_open=False)
    second = reconcile(wanted=wanted, existing=existing, session_open=False)
    assert first == second
    with pytest.raises(Exception):
        first.to_create = ()


# --- l'hystérésis -----------------------------------------------------------

def _row(quantity, *, min_quantity=500.0, product_id=7, name="Pâtes"):
    return {"product_id": product_id, "name": name,
            "min_quantity": min_quantity, "quantity": quantity}


def test_the_hysteresis_keeps_a_line_up_to_fifteen_percent_above_the_threshold():
    """Seuil 500 g : apparaît sous 500, se maintient jusqu'à 575, disparaît
    au-delà. Sans cette marge, un produit qui oscille fait clignoter sa ligne
    tous les quarts d'heure — et une liste qui clignote est une liste qu'on
    n'ouvre plus."""
    assert SHORTAGE_KEEP_FACTOR == 1.15
    assert shortage_claim(_row(400.0), already_claimed=False) is not None
    assert shortage_claim(_row(520.0), already_claimed=False) is None
    assert shortage_claim(_row(520.0), already_claimed=True) is not None
    assert shortage_claim(_row(600.0), already_claimed=True) is None


@pytest.mark.parametrize("quantity, already_claimed, kept", [
    (499.9, False, True),
    (500.0, False, False),
    (575.0, True, True),
    (575.1, True, False),
])
def test_the_hysteresis_boundaries_are_exact(quantity, already_claimed, kept):
    """499,9 → apparaît. 500,0 → n'apparaît pas. 575,0 → maintenue.
    575,1 → fermée. Les quatre, pas seulement les deux du milieu."""
    assert (shortage_claim(_row(quantity),
                           already_claimed=already_claimed) is not None) is kept


def test_the_shortage_claim_asks_for_what_is_missing():
    claim = shortage_claim(_row(200.0), already_claimed=False)
    assert claim.origin == "shortage"
    assert claim.quantity == pytest.approx(300.0)
    assert "500" in claim.detail


def test_a_claim_maintained_above_its_threshold_asks_for_nothing_precise():
    claim = shortage_claim(_row(520.0), already_claimed=True)
    assert claim.quantity is None


@pytest.mark.parametrize("row", [
    {"product_id": 7, "name": "Pâtes", "min_quantity": None, "quantity": 200.0},
    {"product_id": 7, "name": "Pâtes", "min_quantity": 500.0, "quantity": None},
])
def test_a_missing_measurement_maintains_instead_of_closing(row):
    """Seuil supprimé, produit désactivé, appariement de recette défait : la
    revendication est MAINTENUE. On ne retire une ligne que sur une mesure
    qui prouve que le besoin a disparu, jamais sur une absence de mesure.
    C'est ce qui évite les disparitions fantômes au redémarrage, quand les
    entités sont encore muettes."""
    assert shortage_claim(row, already_claimed=True) is not None
    # Et une donnée absente ne fait jamais APPARAÎTRE une ligne non plus.
    assert shortage_claim(row, already_claimed=False) is None
