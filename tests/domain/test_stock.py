from datetime import date, datetime

import pytest

from custom_components.home_stock.domain.stock import (
    Allocation,
    BatchView,
    InsufficientStock,
    allocate,
    is_empty,
    sort_batches,
)


def batch(id_, remaining, best_before=None, entered="2026-08-01", opened=None,
          price=None, kcal=None):
    return BatchView(
        id=id_,
        remaining=remaining,
        best_before=date.fromisoformat(best_before) if best_before else None,
        entered_at=datetime.fromisoformat(f"{entered}T10:00:00"),
        opened_at=datetime.fromisoformat(f"{opened}T10:00:00") if opened else None,
        price_per_base_unit=price,
        kcal_per_base_unit=kcal,
    )


def test_an_opened_batch_comes_first_even_with_a_later_date():
    # Finishing what is already open beats the closest expiry: that is how a
    # kitchen works, and it avoids opening a second pack for nothing.
    closed_soon = batch(1, 500, best_before="2026-08-20")
    opened_later = batch(2, 300, best_before="2026-09-30", opened="2026-08-10")
    assert [b.id for b in sort_batches([closed_soon, opened_later])] == [2, 1]


def test_batches_without_a_date_come_last():
    dated = batch(1, 500, best_before="2026-12-01")
    undated = batch(2, 500)
    assert [b.id for b in sort_batches([undated, dated])] == [1, 2]


def test_equal_dates_fall_back_to_entry_order():
    first = batch(1, 500, best_before="2026-09-01", entered="2026-07-01")
    second = batch(2, 500, best_before="2026-09-01", entered="2026-08-01")
    assert [b.id for b in sort_batches([second, first])] == [1, 2]


def test_partial_consumption_of_a_single_batch():
    # 200 g taken from a 500 g pack: 300 g left, the batch stays open.
    allocations = allocate([batch(1, 500, price=0.004, kcal=3.5)], 200)
    assert allocations == [
        Allocation(batch_id=1, quantity=200, price_per_base_unit=0.004,
                   kcal_per_base_unit=3.5, remaining_after=300, closes_batch=False)
    ]


def test_consumption_spans_several_batches():
    allocations = allocate(
        [batch(1, 300, best_before="2026-08-20", price=0.004),
         batch(2, 500, best_before="2026-09-20", price=0.005)],
        700,
    )
    assert [(a.batch_id, a.quantity, a.closes_batch) for a in allocations] == [
        (1, 300, True),
        (2, 400, False),
    ]
    # Each fraction keeps the price actually paid for it.
    assert allocations[0].price_per_base_unit == 0.004
    assert allocations[1].price_per_base_unit == 0.005


def test_a_batch_emptied_below_the_epsilon_is_closed():
    allocations = allocate([batch(1, 500.0000001)], 500)
    assert allocations[0].closes_batch is True
    assert allocations[0].remaining_after == 0


def test_consuming_more_than_available_is_refused():
    with pytest.raises(InsufficientStock) as error:
        allocate([batch(1, 300), batch(2, 100)], 500)
    assert error.value.requested == 500
    assert error.value.available == 400


def test_consuming_from_an_empty_stock_is_refused():
    with pytest.raises(InsufficientStock):
        allocate([], 1)


def test_allocate_refuses_a_non_positive_quantity():
    with pytest.raises(ValueError):
        allocate([batch(1, 100)], 0)


def test_is_empty_uses_the_epsilon():
    assert is_empty(0.0005) is True
    assert is_empty(0.01) is False


def test_allocate_does_not_walk_into_an_untouched_batch_on_float_dust():
    # 0.1 + 0.2 != 0.3 in binary float: after taking 0.1 from batch 1 and 0.2 from
    # batch 2, `left` is a tiny positive residue (~2.78e-17), not exactly zero. The
    # loop guard must treat that residue as empty (epsilon), or it walks into batch 3
    # and emits a phantom allocation against a pack that was never actually opened.
    allocations = allocate(
        [batch(1, 0.1), batch(2, 0.2), batch(3, 500.0)],
        0.1 + 0.2,
    )
    assert [a.batch_id for a in allocations] == [1, 2]


def test_a_shortfall_within_the_epsilon_is_served_not_refused():
    # Requesting 0.0005 more than the total available (400) is below the system's own
    # definition of "empty" (QUANTITY_EPSILON = 0.001). Refusing here would be pedantic
    # about dust the rest of the system already ignores, and serving the extra 0.0005
    # would push the stock negative. So: serve everything there is, close every batch
    # touched, and do not raise — the tiny shortfall is silently absorbed.
    allocations = allocate([batch(1, 300), batch(2, 100)], 400.0005)
    assert [(a.batch_id, a.quantity, a.closes_batch) for a in allocations] == [
        (1, 300, True),
        (2, 100, True),
    ]


def test_an_allocation_carries_the_macros_of_its_batch():
    batch_view = BatchView(
        id=1, remaining=500.0, best_before=None,
        entered_at=datetime(2026, 8, 1), opened_at=None,
        price_per_base_unit=0.004, kcal_per_base_unit=1.2,
        macros={"proteins": 0.05, "salt": 0.001},
    )
    [allocation] = allocate([batch_view], 200.0)
    assert allocation.macros == {"proteins": 0.05, "salt": 0.001}


def test_a_batch_view_without_macros_still_works():
    """Toutes les constructions du lot 0 et du lot 1 en sont dépourvues."""
    batch_view = BatchView(
        id=1, remaining=500.0, best_before=None,
        entered_at=datetime(2026, 8, 1), opened_at=None,
        price_per_base_unit=None, kcal_per_base_unit=None,
    )
    [allocation] = allocate([batch_view], 200.0)
    assert allocation.macros == {}
