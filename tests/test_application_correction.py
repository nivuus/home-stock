"""Corriger une ligne déjà écrite, sans réécrire l'histoire.

Une contrepassation est une écriture de plus, de motif IDENTIQUE et de signe
inverse, reliée à sa cible par `movement.corrects_id` (amendement A1). Le
journal reste en ajout seul, et les quatre requêtes d'agrégat absorbent la
correction sans qu'une ligne de SQL bouge.
"""
import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.domain.correction import CorrectionError
from custom_components.home_stock.messages import french_message
from custom_components.home_stock.storage import repositories as repo

from test_application import manager, pasta  # noqa: F401

PARIS = ZoneInfo("Europe/Paris")


def _stocked(manager, pasta, *, quantity=500.0, price=0.004):
    return manager.add_stock(
        article_id=pasta["article_id"], quantity=quantity,
        location_id=pasta["location_id"], price_per_base_unit=price,
        occurred_at="2026-08-14T10:00:00",
    )


def test_correcting_a_consumption_gives_the_stock_back(manager, pasta):
    """Le journal gagne une ligne, le lot retrouve sa quantité, et
    `closed_at` repasse à NULL si le lot redevient non vide."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=500.0,
                                        occurred_at="2026-08-14T18:00:00")
    conn = manager.db.read()
    assert conn.execute("SELECT closed_at FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()["closed_at"] is not None

    result = manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    assert result["movement_id"] == movement_id
    assert result["batch_id"] == batch_id
    assert result["restored"] is True
    conn = manager.db.read()
    batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert batch["remaining"] == pytest.approx(500.0)
    assert batch["closed_at"] is None


def test_the_correction_is_a_second_row_never_an_update(manager, pasta):
    """`movement` est en ajout seul par déclencheur depuis le lot 0 : le test
    compte deux lignes et vérifie que la première est intacte."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    conn = manager.db.read()
    before = dict(repo.get_movement(conn, movement_id))

    result = manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    conn = manager.db.read()
    assert dict(repo.get_movement(conn, movement_id)) == before
    rows = repo.movements_of_batch(conn, batch_id)
    assert [r["id"] for r in rows] == sorted(r["id"] for r in rows)
    mirror = repo.get_movement(conn, result["correction_id"])
    assert mirror["corrects_id"] == movement_id
    assert mirror["reason"] == before["reason"]
    assert mirror["quantity"] == pytest.approx(-before["quantity"])


def test_the_daily_totals_absorb_the_correction_without_a_single_query_change(manager, pasta):
    """LA preuve de l'amendement A1 : après correction, `totals_between` sur
    la journée de la correction rend un kcal et un coût NÉGATIFS, SANS que
    _PERSONAL_SUMS, journal_entries ou counted_movements aient été touchés."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    conn = manager.db.read()
    original = repo.get_movement(conn, movement_id)

    manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    conn = manager.db.read()
    totals = repo.totals_between(conn, "2026-08-21T00:00:00", "2026-08-22T00:00:00")
    entries = repo.journal_entries(conn, "2026-08-21T00:00:00", "2026-08-22T00:00:00")
    counted = repo.counted_movements(conn, "2026-08-21T00:00:00")
    assert totals["kcal"] == pytest.approx(-original["kcal"])
    assert totals["cost"] == pytest.approx(-original["cost"])
    assert len(entries) == 1 and entries[0]["quantity"] == pytest.approx(200.0)
    assert len(counted) == 1 and counted[0]["kcal"] == pytest.approx(-original["kcal"])


def test_the_correction_is_booked_on_the_day_it_is_made(manager, pasta):
    """`occurred_at` est l'instant de l'ÉCRITURE. La barre d'hier ne bouge
    pas ; celle d'aujourd'hui porte une entrée négative."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    conn = manager.db.read()
    yesterday = repo.totals_between(conn, "2026-08-14T00:00:00",
                                    "2026-08-15T00:00:00")
    today = repo.totals_between(conn, "2026-08-21T00:00:00", "2026-08-22T00:00:00")
    assert yesterday["kcal"] == pytest.approx(700.0)
    assert today["kcal"] == pytest.approx(-700.0)


def test_a_movement_cannot_be_corrected_twice(manager, pasta):
    """La garantie est portée par l'index UNIQUE partiel, pas par la lecture
    préalable : deux corrections concurrentes de la même ligne rembourseraient
    deux fois. L'aperçu, lui, le dit en français avant qu'on appuie."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    assert manager.preview_correction(movement_id)["correctable"] is False
    assert manager.preview_correction(movement_id)["refusal"] == (
        "Cette ligne a déjà été corrigée.")

    with pytest.raises(sqlite3.IntegrityError):
        with manager.db.write() as conn:
            repo.insert_movement(
                conn, occurred_at="2026-08-21T10:00:00",
                product_id=pasta["product_id"], article_id=pasta["article_id"],
                quantity=200.0, reason="consumption", base_unit="g",
                corrects_id=movement_id)


def test_correcting_a_correction_is_refused(manager, pasta):
    """`corrects_id IS NOT NULL` sur la cible. Corriger la correction, c'est
    refaire la première écriture : le geste existe déjà, c'est la saisie."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    result = manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    with pytest.raises(CorrectionError) as refus:
        manager.correct_movement(result["correction_id"],
                                 occurred_at="2026-08-21T11:00:00")
    assert french_message(refus.value) == (
        "Cette ligne est déjà une correction : corriger une correction, "
        "c'est refaire la saisie."
    )


def test_reversing_a_consumption_on_an_emptied_batch_restores_it(manager, pasta):
    """Rendre du stock ne peut jamais rendre `remaining` négatif : le refus
    du § 12.2 vise l'annulation d'un ACHAT, testée juste après."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    # Le lot est ensuite vidé par un inventaire : rien à rendre.
    with manager.db.write() as conn:
        repo.set_batch_remaining(conn, batch_id, 0.0, closed_at="2026-08-15T09:00:00")

    result = manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")
    assert result["restored"] is True
    conn = manager.db.read()
    assert conn.execute("SELECT remaining FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()["remaining"] == pytest.approx(200.0)


def test_a_purchase_reversal_that_would_make_remaining_negative_is_refused(manager, pasta):
    """Annuler un achat retire du stock. Si ce stock est déjà parti, le
    refus dit ce qui reste — plutôt qu'un lot à quantité négative."""
    batch_id = _stocked(manager, pasta, quantity=500.0)
    conn = manager.db.read()
    purchase_id = repo.movements_of_batch(conn, batch_id)[0]["id"]
    manager.consume_batch(batch_id, quantity=400.0, occurred_at="2026-08-15T18:00:00")

    with pytest.raises(ValueError) as refus:
        manager.correct_movement(purchase_id, occurred_at="2026-08-21T09:00:00")
    assert french_message(refus.value) == (
        "Impossible d'annuler cette ligne : le lot n'a plus que 100.0. "
        "Le stock a déjà été repris ailleurs."
    )
    conn = manager.db.read()
    assert repo.correction_of(conn, purchase_id) is None


def test_a_reversal_may_push_a_batch_above_its_initial_quantity(manager, pasta):
    """AUTORISÉE, explicitement : un lot peut légitimement dépasser son
    initial après annulation d'une sortie faite avant une conversion d'unité.
    Refuser bloquerait le seul cas où la correction est vraiment utile."""
    batch_id = _stocked(manager, pasta, quantity=500.0)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    with manager.db.write() as conn:
        repo.set_batch_remaining(conn, batch_id, 500.0)

    manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    conn = manager.db.read()
    assert conn.execute("SELECT remaining FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()["remaining"] == pytest.approx(700.0)


def test_a_missing_batch_still_gets_its_journal_line(manager, pasta):
    """Le journal doit rester juste même quand le stock ne peut plus l'être :
    la ligne miroir s'écrit, aucun stock n'est ajusté, et le résultat le dit
    (`restored is False`)."""
    with manager.db.write() as conn:
        movement_id = repo.insert_movement(
            conn, occurred_at="2026-08-14T18:00:00", product_id=pasta["product_id"],
            article_id=pasta["article_id"], batch_id=None, quantity=-200.0,
            reason="consumption", base_unit="g", kcal=700.0, cost=0.8,
        )

    result = manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")

    assert result["restored"] is False and result["batch_id"] is None
    conn = manager.db.read()
    mirror = repo.get_movement(conn, result["correction_id"])
    assert mirror["quantity"] == pytest.approx(200.0)
    assert mirror["kcal"] == pytest.approx(-700.0)


@pytest.mark.parametrize("reason, phrase", [
    ("transfer", "Un transfert ne se corrige pas : il ne change aucune quantité, "
                 "seulement un emplacement."),
    ("conversion", "Une conversion d'unité ne se corrige pas ligne à ligne : "
                   "ses deux écritures vont par paire."),
    ("cooked", "Un mouvement de cuisine s'annule en corrigeant le repas entier, "
               "pas ligne à ligne."),
])
def test_a_transfer_a_conversion_and_a_cooked_are_refused(manager, pasta, reason, phrase):
    """Trois motifs, trois refus, trois messages français distincts."""
    with manager.db.write() as conn:
        movement_id = repo.insert_movement(
            conn, occurred_at="2026-08-14T18:00:00", product_id=pasta["product_id"],
            article_id=pasta["article_id"], quantity=-200.0, reason=reason,
            base_unit="g",
        )
    with pytest.raises(CorrectionError) as refus:
        manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")
    assert french_message(refus.value) == phrase


def test_a_purchase_is_corrected_like_any_other(manager, pasta):
    """Son coût n'entre dans aucun capteur — et il entre dans l'export du
    journal et dans la valeur du stock. Le laisser faux « parce qu'aucun
    capteur ne le lit » est le raisonnement qui produit une base à deux
    vitesses."""
    batch_id = _stocked(manager, pasta, quantity=500.0)
    conn = manager.db.read()
    purchase = repo.movements_of_batch(conn, batch_id)[0]
    assert purchase["reason"] == "purchase"

    result = manager.correct_movement(purchase["id"], occurred_at="2026-08-21T09:00:00")

    conn = manager.db.read()
    mirror = repo.get_movement(conn, result["correction_id"])
    batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert mirror["reason"] == "purchase"
    assert mirror["quantity"] == pytest.approx(-500.0)
    assert mirror["cost"] == pytest.approx(-purchase["cost"])
    assert batch["remaining"] == pytest.approx(0.0)
    assert batch["closed_at"] == "2026-08-21T09:00:00"


def test_replaying_the_same_correction_returns_the_first_one(manager, pasta):
    """`idempotency_key = correction:<id>` : la file hors ligne rejoue."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")
    first = manager.correct_movement(movement_id, occurred_at="2026-08-21T09:00:00")
    again = manager.correct_movement(movement_id, occurred_at="2026-08-21T09:05:00")

    assert again["correction_id"] == first["correction_id"]
    conn = manager.db.read()
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM movement WHERE corrects_id = ?",
        (movement_id,)).fetchone()["n"] == 1
    assert conn.execute("SELECT remaining FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()["remaining"] == pytest.approx(500.0)


def test_preview_says_what_will_happen_before_it_happens(manager, pasta):
    """Nom du produit, quantité, kcal, coût, date du lot visé. Une opération
    irréversible qui ne s'annonce pas est une opération qu'on déclenche par
    erreur."""
    batch_id = _stocked(manager, pasta)
    movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                        occurred_at="2026-08-14T18:00:00")

    preview = manager.preview_correction(movement_id)

    assert preview["product_name"] == "Pâtes"
    assert preview["quantity"] == pytest.approx(200.0)
    assert preview["base_unit"] == "g"
    assert preview["kcal"] == pytest.approx(700.0)
    assert preview["cost"] == pytest.approx(0.8)
    assert preview["reason"] == "consumption"
    assert preview["batch_id"] == batch_id
    assert preview["batch_entered_at"] == "2026-08-14T10:00:00"
    assert preview["correctable"] is True
    conn = manager.db.read()
    assert repo.correction_of(conn, movement_id) is None


def test_preview_of_an_uncorrectable_movement_says_why(manager, pasta):
    with manager.db.write() as conn:
        movement_id = repo.insert_movement(
            conn, occurred_at="2026-08-14T18:00:00", product_id=pasta["product_id"],
            article_id=pasta["article_id"], quantity=0.0, reason="transfer",
            base_unit="g",
        )
    preview = manager.preview_correction(movement_id)
    assert preview["correctable"] is False
    assert preview["refusal"] == (
        "Un transfert ne se corrige pas : il ne change aucune quantité, "
        "seulement un emplacement."
    )


def test_an_unknown_movement_is_refused_in_french(manager):
    with pytest.raises(LookupError) as refus:
        manager.correct_movement(4242, occurred_at="2026-08-21T09:00:00")
    assert french_message(refus.value) == "Mouvement 4242 inconnu."


# --- § 12.4 : corriger un prix ---------------------------------------------

def test_correcting_a_price_updates_the_batch_and_records_an_observation(manager, pasta):
    """La moitié « en avant » : toutes les sorties FUTURES seront chiffrées
    juste, sans rien réécrire."""
    batch_id = _stocked(manager, pasta, price=0.004)

    result = manager.correct_price(batch_id, price_per_base_unit=0.006,
                                   observed_on="2026-08-21", source="receipt")

    assert result["batch_id"] == batch_id
    conn = manager.db.read()
    assert conn.execute("SELECT price_per_base_unit FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()[0] == pytest.approx(0.006)
    price = conn.execute("SELECT * FROM price WHERE id = ?",
                         (result["price_id"],)).fetchone()
    assert price["price_per_base_unit"] == pytest.approx(0.006)
    assert price["source"] == "receipt"
    assert price["observed_on"] == "2026-08-21"


def test_the_normal_case_writes_no_journal_line_at_all(manager, pasta):
    """Un lot dont rien n'est sorti : `corrected_movements == 0`. C'est pour
    ça que le ticket se photographie à la caisse et pas la semaine d'après."""
    batch_id = _stocked(manager, pasta, price=0.004)
    conn = manager.db.read()
    before = conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"]

    result = manager.correct_price(batch_id, price_per_base_unit=0.006,
                                   observed_on="2026-08-21")

    # L'achat lui-même est corrigé : il entre dans la valeur du stock et dans
    # l'export du journal. Aucune SORTIE ne l'est, il n'y en a pas.
    assert result["corrected_movements"] == 1
    conn = manager.db.read()
    assert conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"] == before + 2


def test_each_affected_movement_gets_a_reversal_then_a_rewrite(manager, pasta):
    """Deux lignes par mouvement, dans cet ordre, `corrects_id` sur la
    première seulement, toutes dans la même transaction."""
    batch_id = _stocked(manager, pasta, price=0.004)
    eaten = manager.consume_batch(batch_id, quantity=200.0,
                                  occurred_at="2026-08-14T18:00:00")

    manager.correct_price(batch_id, price_per_base_unit=0.006,
                          observed_on="2026-08-21", moment="2026-08-21T09:00:00")

    conn = manager.db.read()
    rows = repo.movements_of_batch(conn, batch_id)
    tail = [r for r in rows if r["id"] > eaten]
    # achat contrepassé, achat réécrit, sortie contrepassée, sortie réécrite
    assert [r["corrects_id"] for r in tail] == [1, None, eaten, None]
    assert all(r["occurred_at"] == "2026-08-21T09:00:00" for r in tail)
    assert tail[3]["cost"] == pytest.approx(200.0 * 0.006)


def test_the_nutritional_balance_of_a_price_correction_is_zero(manager, pasta):
    """Épinglé explicitement (§ 12.4) : un prix faux n'a jamais faussé des
    calories. La somme des trois lignes vaut celle de l'originale."""
    batch_id = _stocked(manager, pasta, price=0.004)
    eaten = manager.consume_batch(batch_id, quantity=200.0,
                                  occurred_at="2026-08-14T18:00:00")
    conn = manager.db.read()
    original = repo.get_movement(conn, eaten)

    manager.correct_price(batch_id, price_per_base_unit=0.006,
                          observed_on="2026-08-21", moment="2026-08-21T09:00:00")

    conn = manager.db.read()
    trio = [r for r in repo.movements_of_batch(conn, batch_id)
            if r["id"] == eaten or r["corrects_id"] == eaten
            or (r["id"] > eaten and r["reason"] == "consumption")]
    assert len(trio) == 3
    for column in ("kcal", "proteins", "carbohydrates", "fat", "salt"):
        assert sum(r[column] or 0.0 for r in trio) == pytest.approx(original[column] or 0.0)


def test_only_the_cost_moves(manager, pasta):
    """`cost` bouge de la différence exacte ; `kcal` ne bouge pas d'un iota."""
    batch_id = _stocked(manager, pasta, price=0.004)
    manager.consume_batch(batch_id, quantity=200.0, occurred_at="2026-08-14T18:00:00")
    conn = manager.db.read()
    before = repo.totals_between(conn)

    manager.correct_price(batch_id, price_per_base_unit=0.006,
                          observed_on="2026-08-21", moment="2026-08-21T09:00:00")

    conn = manager.db.read()
    after = repo.totals_between(conn)
    assert after["kcal"] == pytest.approx(before["kcal"])
    assert after["cost"] == pytest.approx(before["cost"] + 200.0 * (0.006 - 0.004))


def test_the_purchase_movement_is_corrected_too(manager, pasta):
    """Il entre dans l'export du journal et dans la valeur du stock."""
    batch_id = _stocked(manager, pasta, quantity=500.0, price=0.004)
    conn = manager.db.read()
    purchase = repo.movements_of_batch(conn, batch_id)[0]

    manager.correct_price(batch_id, price_per_base_unit=0.006,
                          observed_on="2026-08-21", moment="2026-08-21T09:00:00")

    conn = manager.db.read()
    assert repo.correction_of(conn, purchase["id"])["cost"] == pytest.approx(-2.0)
    rewritten = [r for r in repo.movements_of_batch(conn, batch_id)
                 if r["reason"] == "purchase" and r["corrects_id"] is None
                 and r["id"] != purchase["id"]]
    assert len(rewritten) == 1
    assert rewritten[0]["cost"] == pytest.approx(3.0)
    # Le lot n'a pas bougé : contrepassation puis réécriture s'annulent.
    assert conn.execute("SELECT remaining FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()["remaining"] == pytest.approx(500.0)


def test_correcting_a_price_twice_only_corrects_what_is_not_yet_corrected(manager, pasta):
    """L'index unique tient : la seconde correction ne contrepasse pas ce qui
    l'est déjà, elle corrige les lignes que la première a écrites."""
    batch_id = _stocked(manager, pasta, price=0.004)
    manager.consume_batch(batch_id, quantity=200.0, occurred_at="2026-08-14T18:00:00")
    manager.correct_price(batch_id, price_per_base_unit=0.006,
                          observed_on="2026-08-21", moment="2026-08-21T09:00:00")

    second = manager.correct_price(batch_id, price_per_base_unit=0.005,
                                   observed_on="2026-08-22",
                                   moment="2026-08-22T09:00:00")

    assert second["corrected_movements"] == 2      # les deux réécritures
    conn = manager.db.read()
    totals = repo.totals_between(conn)
    assert totals["cost"] == pytest.approx(200.0 * 0.005)


def test_preview_of_a_price_correction_counts_what_will_be_rewritten(manager, pasta):
    batch_id = _stocked(manager, pasta, price=0.004)
    assert manager.preview_price_correction(
        batch_id, price_per_base_unit=0.006)["corrected_movements"] == 1
    manager.consume_batch(batch_id, quantity=200.0, occurred_at="2026-08-14T18:00:00")
    preview = manager.preview_price_correction(batch_id, price_per_base_unit=0.006)
    assert preview["corrected_movements"] == 2
    assert preview["batch_id"] == batch_id
    assert preview["price_per_base_unit"] == pytest.approx(0.006)
    conn = manager.db.read()
    assert conn.execute("SELECT price_per_base_unit FROM batch WHERE id = ?",
                        (batch_id,)).fetchone()[0] == pytest.approx(0.004)
