"""home_stock.resync_off: a background catalogue refresh from Open Food Facts."""
import json
import threading

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.off.client import BULK_INTERVAL, OffLookup, OffRecord
from custom_components.home_stock.storage import repositories as repo

MUESLI = {
    "code": "3229820129488",
    "product_name_fr": "Muesli Raisin, Figue, Datte, Abricot",
    "brands": "Bjorg",
    "product_quantity": 375,
    "product_quantity_unit": "g",
    "nutriscore_grade": "a",
    "categories_tags": ["en:plant-based-foods", "en:breakfasts", "en:breakfast-cereals"],
    "nutrition_data_per": "100g",
    "nutriments": {"energy-kcal_100g": 360, "proteins_100g": 9, "carbohydrates_100g": 60,
                   "fat_100g": 6, "salt_100g": 0.02},
}

# Only a name — no brand, no net weight, no Nutri-Score, no nutrition table.
# Stands in for an OFF page a contributor trimmed down after a fuller scan
# (or a fuller resync) already stored something better.
THIN_RECORD = {"code": "3229820129488", "product_name_fr": "Muesli"}


class FakeOffClient:
    """Stands in for the cascade. Nothing here reaches the network."""

    def __init__(self, records: dict[str, dict]):
        self._records = records
        self.codes: list[str] = []

    async def lookup_with_retry(self, code: str, **kwargs) -> OffLookup:
        self.codes.append(code)
        product = self._records.get(code)
        if product is None:
            return OffLookup()
        return OffLookup(record=OffRecord(code, "food", product))


class _FailsOnceOffClient:
    """The first lookup raises — a per-card failure that must not abort the
    rest of the pass — the rest answer normally."""

    def __init__(self, records: dict[str, dict]):
        self._records = records
        self.calls = 0

    async def lookup_with_retry(self, code: str, **kwargs) -> OffLookup:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("simulated network hiccup")
        product = self._records.get(code)
        if product is None:
            return OffLookup()
        return OffLookup(record=OffRecord(code, "food", product))


async def _no_wait(seconds: float) -> None:
    """A resync_sleeper that never actually waits — for tests with more than
    one barcode that are not themselves testing the wait."""


@pytest.fixture
async def entry(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()
    entry.runtime_data.off_client = FakeOffClient({"3229820129488": MUESLI})
    return entry


def _seed_article(manager, *, kcal_per_base_unit, manual_fields=()):
    with manager.db.write() as conn:
        product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
        article_id = repo.insert_article(
            conn, product_id=product_id, kcal_per_base_unit=kcal_per_base_unit,
            manual_fields=json.dumps(list(manual_fields)) if manual_fields else None,
        )
        repo.link_barcode(conn, "3229820129488", article_id)
    return article_id


async def test_a_hand_corrected_field_survives_a_resync_that_disagrees(
        hass: HomeAssistant, entry):
    """The one thing this task exists to prove: manual_fields wins over a
    fresh, disagreeing OFF answer, and everything NOT protected still
    refreshes — a resync that overwrote the correction, or one that changed
    nothing at all, would both hide here."""
    manager = entry.runtime_data.manager
    # 9.9 is what a person typed by hand; MUESLI's own kcal (360 per 100 g,
    # 3.6 per base unit for a g-based product) disagrees with it — the resync
    # must not be a no-op that happens to agree by coincidence.
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9,
                              manual_fields=("kcal_per_base_unit",)))

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)

    article = await hass.async_add_executor_job(_read)
    # Protected: the human's number, not OFF's 3.6.
    assert article["kcal_per_base_unit"] == 9.9
    # Not protected: OFF's answer for everything else actually landed.
    assert article["brand"] == "Bjorg"
    assert article["net_quantity"] == 375
    assert article["off_source"] == "food"
    assert article["off_synced_at"] is not None
    assert json.loads(article["off_raw"])["code"] == "3229820129488"


async def test_manual_fields_cannot_suppress_the_record_of_the_sync_itself(
        hass: HomeAssistant, entry):
    """off_synced_at/off_raw are never subject to manual_fields, even if a
    hand-edited (or corrupted) manual_fields value happens to name them —
    the panel itself can never put them there (it validates against
    ARTICLE_EDITABLE, which does not include either), but the review
    ruling was explicit: a human may protect a value, never the fact that
    a resync ran."""
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9,
                              manual_fields=("off_synced_at", "off_raw")))

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)

    article = await hass.async_add_executor_job(_read)
    assert article["off_synced_at"] is not None
    assert article["off_raw"] is not None
    # kcal_per_base_unit was never named as protected here, so OFF's answer
    # still won for it — this is not accidentally protecting everything.
    assert article["kcal_per_base_unit"] == pytest.approx(3.6)


async def test_an_unprotected_field_is_overwritten_by_the_resync(
        hass: HomeAssistant, entry):
    """The mirror of the test above: without manual_fields, OFF's answer
    wins outright — proving the protection above comes from manual_fields,
    not from some accidental refusal to ever overwrite kcal."""
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9))

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)

    article = await hass.async_add_executor_job(_read)
    assert article["kcal_per_base_unit"] == pytest.approx(3.6)


async def test_a_thinner_off_record_does_not_erase_what_was_already_stored(
        hass: HomeAssistant, entry):
    """Review round 1's ruling: a resync may fill a gap or correct a value,
    but must never erase one. Nothing in the household's 299 products has a
    net weight today — this service is what will finally supply them — so a
    contributor trimming a record months after a fuller scan must not take
    one back."""
    manager = entry.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
            article_id = repo.insert_article(
                conn, product_id=product_id, brand="Bjorg", net_quantity=375,
                nutriscore="a")
            repo.link_barcode(conn, "3229820129488", article_id)
            return article_id

    article_id = await hass.async_add_executor_job(_seed)
    entry.runtime_data.off_client = FakeOffClient({"3229820129488": THIN_RECORD})

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)

    article = await hass.async_add_executor_job(_read)
    assert article["brand"] == "Bjorg"
    assert article["net_quantity"] == 375
    assert article["nutriscore"] == "a"
    # The sync itself still happened — only the erasing is refused.
    assert article["off_synced_at"] is not None


async def test_a_malformed_manual_fields_does_not_abort_the_pass(
        hass: HomeAssistant, entry):
    """Reproduces the bug found in review: an article whose manual_fields
    column holds something unreadable used to raise json.JSONDecodeError
    with nothing around it, killing the background task outright — the
    barcode queued right after it was never even fetched. Now: that one
    article's write is skipped (everything is protected when we cannot tell
    what a human corrected), and the pass reaches the rest."""
    manager = entry.runtime_data.manager

    def _seed() -> tuple[int, int]:
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
            broken = repo.insert_article(
                conn, product_id=product_id, brand="Original",
                manual_fields="{not valid json")
            healthy = repo.insert_article(conn, product_id=product_id)
            repo.link_barcode(conn, "111", broken)
            repo.link_barcode(conn, "222", healthy)
        return broken, healthy

    broken_id, healthy_id = await hass.async_add_executor_job(_seed)
    entry.runtime_data.off_client = FakeOffClient({"111": MUESLI, "222": MUESLI})
    entry.runtime_data.resync_sleeper = _no_wait

    await hass.services.async_call(DOMAIN, "resync_off", {"all": True}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read(article_id: int):
        return repo.get_article(manager.db.read(), article_id)

    broken = await hass.async_add_executor_job(lambda: _read(broken_id))
    healthy = await hass.async_add_executor_job(lambda: _read(healthy_id))

    # The malformed row is left exactly as it was: nothing could be proven
    # safe to overwrite, so the write was skipped entirely (not just the
    # columns manual_fields would normally name).
    assert broken["brand"] == "Original"
    assert broken["off_synced_at"] is None
    # The pass reached the barcode queued after the bad one anyway.
    assert healthy["brand"] == "Bjorg"


async def test_a_failing_card_does_not_stop_the_rest_of_the_pass(
        hass: HomeAssistant, entry):
    """The general case the malformed-manual_fields test above is one
    instance of: any per-card exception (a transient OFF error, a database
    hiccup from a mid-pass reload) must not end a forty-minute pass early."""
    manager = entry.runtime_data.manager

    def _seed() -> tuple[int, int]:
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
            first = repo.insert_article(conn, product_id=product_id)
            second = repo.insert_article(conn, product_id=product_id)
            repo.link_barcode(conn, "111", first)
            repo.link_barcode(conn, "222", second)
        return first, second

    first_id, second_id = await hass.async_add_executor_job(_seed)
    entry.runtime_data.off_client = _FailsOnceOffClient({"222": MUESLI})
    entry.runtime_data.resync_sleeper = _no_wait

    await hass.services.async_call(DOMAIN, "resync_off", {"all": True}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read(article_id: int) -> str | None:
        return repo.get_article(manager.db.read(), article_id)["brand"]

    assert (await hass.async_add_executor_job(lambda: _read(second_id))) == "Bjorg"


async def test_resync_off_honours_the_bulk_interval_between_cards(
        hass: HomeAssistant, entry):
    """The interval that justifies running this as a background task at all:
    every other test in this file resyncs one barcode, which would stay
    green even if the wait were deleted outright."""
    manager = entry.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
            first = repo.insert_article(conn, product_id=product_id)
            second = repo.insert_article(conn, product_id=product_id)
            repo.link_barcode(conn, "111", first)
            repo.link_barcode(conn, "222", second)

    await hass.async_add_executor_job(_seed)
    entry.runtime_data.off_client = FakeOffClient({"111": MUESLI, "222": MUESLI})

    waits: list[float] = []

    async def sleeper(seconds: float) -> None:
        waits.append(seconds)

    entry.runtime_data.resync_sleeper = sleeper

    await hass.services.async_call(DOMAIN, "resync_off", {"all": True}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Exactly one wait, the right length, and — because there is exactly
    # one entry — not before the first card either.
    assert waits == [BULK_INTERVAL]


async def test_resync_off_refuses_a_second_run_while_one_is_in_progress(
        hass: HomeAssistant, entry):
    """OFF's own rate limit is measured per client, not per request
    (off/client.py's own module docstring: one 429 after about twenty calls
    at 1.5 s apart) — two passes running at once would double it. Sets the
    real guard flag directly, rather than driving an actual in-flight pass,
    to test the guard's own logic in isolation from timing — the race
    between two real concurrent calls is what the test below this one
    proves instead."""
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9))

    entry.runtime_data.resync_in_progress = True

    with pytest.raises(HomeAssistantError, match="déjà en cours"):
        await hass.services.async_call(
            DOMAIN, "resync_off", {"article_id": article_id}, blocking=True)

    entry.runtime_data.resync_in_progress = False


async def test_resync_off_allows_a_new_run_once_the_previous_one_is_done(
        hass: HomeAssistant, entry):
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9))

    assert entry.runtime_data.resync_in_progress is False

    # Must not raise: nothing is in progress yet.
    await hass.services.async_call(
        DOMAIN, "resync_off", {"article_id": article_id}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The flag releases once the pass finishes...
    assert entry.runtime_data.resync_in_progress is False

    # ...so a second call afterwards is not refused either.
    await hass.services.async_call(
        DOMAIN, "resync_off", {"article_id": article_id}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.resync_in_progress is False

    def _read():
        return repo.get_article(manager.db.read(), article_id)["brand"]

    assert (await hass.async_add_executor_job(_read)) == "Bjorg"


async def test_two_concurrent_calls_start_exactly_one_pass(
        hass: HomeAssistant, entry, monkeypatch):
    """The bug found in review round 2: the guard used to be claimed only
    after the barcode-list read, an `await` away from the check. Two
    automations firing at the same moment used to both pass the check and
    both start a pass, with `resync_task` left naming only the second.

    A plain `asyncio.gather` of two `hass.services.async_call(...)`s does
    NOT reliably exercise this: the barcode-list read resolves fast enough
    in this harness that the two calls run one to completion before the
    other's check ever runs, regardless of whether the guard has the race
    — confirmed by reverting the fix locally and re-running exactly that
    construction, which still passed. This test instead pauses the first
    call's barcode-list read on a real `threading.Event`, mid-flight —
    genuinely overlapping the two calls' execution, the way two automations
    firing "at the same moment" actually would — and only then issues the
    second call, so the outcome is deterministic rather than a coin flip on
    however this event loop happens to schedule two coroutines today.
    """
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9))

    entered_first_call = threading.Event()
    release_first_call = threading.Event()
    real_barcodes_to_resync = repo.barcodes_to_resync

    def _paused_once(conn, **kwargs):
        # Only the first call pauses — the second (and the real work once
        # released) must run normally, or this would deadlock.
        if not entered_first_call.is_set():
            entered_first_call.set()
            assert release_first_call.wait(timeout=5), "second call never arrived"
        return real_barcodes_to_resync(conn, **kwargs)

    monkeypatch.setattr(repo, "barcodes_to_resync", _paused_once)

    first_call = hass.async_create_task(
        hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                 blocking=True))

    # Block until the first call is provably inside its barcode-list read —
    # past its own check, not yet at the point (old, buggy code) or before
    # the point (fixed code) it claims the slot.
    await hass.async_add_executor_job(entered_first_call.wait, 5)

    with pytest.raises(HomeAssistantError, match="déjà en cours"):
        await hass.services.async_call(
            DOMAIN, "resync_off", {"article_id": article_id}, blocking=True)

    # Let the first call's paused read through, and let it run to completion.
    release_first_call.set()
    await first_call
    await hass.async_block_till_done(wait_background_tasks=True)

    # The refusal did not leave anything stuck: the one pass that did run
    # released the flag, and it actually applied OFF's answer.
    assert entry.runtime_data.resync_in_progress is False

    def _read():
        return repo.get_article(manager.db.read(), article_id)["brand"]

    assert (await hass.async_add_executor_job(_read)) == "Bjorg"


async def test_resync_off_a_code_off_no_longer_knows_is_a_no_op(hass: HomeAssistant, entry):
    """A card OFF answers "not found" for (delisted, mistyped) must not clear
    what is already stored."""
    manager = entry.runtime_data.manager
    with manager.db.write() as conn:
        product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
        article_id = repo.insert_article(conn, product_id=product_id, brand="Bjorg")
        repo.link_barcode(conn, "0000000000000", article_id)

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)["brand"]

    assert (await hass.async_add_executor_job(_read)) == "Bjorg"


async def test_resync_off_refuses_no_target_at_all(hass: HomeAssistant, entry):
    """A call naming nothing to resync is refused instead of quietly
    resyncing nothing."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "resync_off", {}, blocking=True)


async def test_resync_off_refuses_all_explicitly_false_with_nothing_else(
        hass: HomeAssistant, entry):
    """The exact no-op the ruling set out to remove: "all" left at its own
    unchecked (`False`) state in the UI, with no id chosen either, used to
    pass validation and silently resync nothing."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "resync_off", {"all": False}, blocking=True)


async def test_resync_off_refuses_an_id_and_the_catalogue_box_together(
        hass: HomeAssistant, entry):
    """A call naming both an id and "all" used to silently run the
    forty-minute catalogue pass, ignoring the id — refused instead."""
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9))

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "resync_off", {"article_id": article_id, "all": True}, blocking=True)


async def test_resync_off_requires_a_loaded_entry(hass: HomeAssistant, setup_entry):
    """The service stays registered after the entry unloads (it is only ever
    registered once, guarded by has_service) — so this reaches _entry()'s
    own French refusal, not a bare "service not found"."""
    entry = await setup_entry()
    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(HomeAssistantError, match="n'est pas configuré"):
        await hass.services.async_call(DOMAIN, "resync_off", {"all": True}, blocking=True)
