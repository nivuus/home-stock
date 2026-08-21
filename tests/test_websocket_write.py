"""The write commands, through a real Home Assistant websocket connection."""
import json

import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock.off.client import OffLookup, OffRecord
from custom_components.home_stock.storage import repositories as repo


class FakeOffClient:
    """Stands in for the cascade. Nothing here reaches the network."""

    def __init__(self, record: OffRecord | None = None, throttled: bool = False):
        self.result = OffLookup(record=record, throttled=throttled)
        self.codes: list[str] = []

    async def lookup(self, code: str) -> OffLookup:
        self.codes.append(code)
        return self.result

    async def lookup_with_retry(self, code: str, **kwargs) -> OffLookup:
        return await self.lookup(code)


class FakeTransport:
    """Stands in for Open Prices. Nothing here reaches the network.

    `calls` records every URL asked for, so a test can prove the fake was
    actually reached instead of the real network silently never firing.
    """

    def __init__(self, status: int = 200, payload: dict | None = None):
        self.status = status
        self.payload = payload if payload is not None else {"items": []}
        self.calls: list[str] = []

    async def get_json(self, url: str, headers: dict, timeout: float):
        self.calls.append(url)
        return self.status, self.payload


MUESLI = OffRecord("3229820129488", "food", {
    "code": "3229820129488",
    "product_name_fr": "Muesli Raisin, Figue, Datte, Abricot",
    "generic_name_fr": "Muesli",
    "brands": "Bjorg",
    "product_quantity": 375,
    "product_quantity_unit": "g",
    "nutriscore_grade": "a",
    "categories_tags": ["en:plant-based-foods", "en:breakfasts", "en:breakfast-cereals"],
    "nutrition_data_per": "100g",
    "nutriments": {"energy-kcal_100g": 360, "proteins_100g": 9, "carbohydrates_100g": 60,
                   "fat_100g": 6, "salt_100g": 0.02},
})


async def test_an_unknown_barcode_comes_back_with_its_off_card(hass: HomeAssistant,
                                                               setup_entry, hass_ws_client):
    entry = await setup_entry()
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    transport = FakeTransport()
    entry.runtime_data.transport = transport
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup",
                            "code": "3229820129488"})
    result = (await client.receive_json())["result"]

    assert result["known"] is False
    assert result["off"]["label"] == "Muesli Raisin, Figue, Datte, Abricot"
    assert result["off"]["net_quantity"] == 375
    assert result["off"]["aisle"] == "Petit-déjeuner"
    assert result["off"]["nutriscore"] == "a"
    # Proves the price cascade went through the fake, not a real socket: a
    # network regression here would otherwise pass silently (Open Prices
    # failures are swallowed on purpose — see off/open_prices.py).
    assert transport.calls


async def test_a_lookup_never_writes(hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry()
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "3229820129488"})
    await client.receive_json()

    def count() -> int:
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM article").fetchone()[0]

    assert await hass.async_add_executor_job(count) == 0


async def test_a_throttled_lookup_says_so_instead_of_pretending(hass: HomeAssistant,
                                                                setup_entry, hass_ws_client):
    entry = await setup_entry()
    entry.runtime_data.off_client = FakeOffClient(throttled=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "123"})
    result = (await client.receive_json())["result"]

    assert result["throttled"] is True
    assert result["off"] is None


async def test_a_lookup_refuses_an_overlong_code(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "x" * 500_000})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_creating_an_article_attaches_it_and_remembers_the_barcode(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry()
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create",
        "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/lookup", "code": "3229820129488"})
    again = (await client.receive_json())["result"]

    assert again["known"] is True
    assert again["article"]["id"] == created["article_id"]
    assert again["product"]["name"] == "Muesli"


async def test_a_created_article_carries_its_nutrition_per_base_unit(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    def kcal() -> float:
        return entry.runtime_data.database.read().execute(
            "SELECT kcal_per_base_unit FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert await hass.async_add_executor_job(kcal) == pytest.approx(3.6)


async def test_a_created_article_keeps_the_serving_off_gives_it(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """build_article_values (off/ingest.py) computes serving_quantity, but
    insert_article filters every keyword argument through ARTICLE_FIELDS —
    a whitelist that used to omit serving_quantity, so the scan path (this
    command) silently dropped it on the floor while services._write_resync
    (which does not filter) wrote it correctly. Pins the scan path against
    the same regression."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)
    off_product = dict(MUESLI.product, serving_quantity=40)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": off_product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    def serving() -> float:
        return entry.runtime_data.database.read().execute(
            "SELECT serving_quantity FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert await hass.async_add_executor_job(serving) == pytest.approx(40)


async def test_the_raw_off_answer_is_kept_verbatim(hass: HomeAssistant, setup_entry,
                                                    hass_ws_client):
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    def raw() -> str:
        return entry.runtime_data.database.read().execute(
            "SELECT off_raw FROM article WHERE id = ?", (created["article_id"],)
        ).fetchone()[0]

    assert json.loads(await hass.async_add_executor_job(raw))["brands"] == "Bjorg"


async def test_editing_an_article_by_hand_protects_it_from_a_resync(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry()
    client = await hass_ws_client(hass)
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food"})
    created = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/article/update",
                            "article_id": created["article_id"],
                            "fields": {"kcal_per_base_unit": 4.0}})
    await client.receive_json()

    def manual() -> str:
        return entry.runtime_data.database.read().execute(
            "SELECT manual_fields FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert "kcal_per_base_unit" in (await hass.async_add_executor_job(manual))


async def test_a_correction_typed_at_creation_is_also_protected_from_a_resync(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """manual_fields must be seeded at creation, not only on a later update —
    otherwise a correction typed on the creation screen is overwritten by the
    article's first OFF resync."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
        "fields": {"kcal_per_base_unit": 4.0},
    })
    created = (await client.receive_json())["result"]

    def manual() -> str:
        return entry.runtime_data.database.read().execute(
            "SELECT manual_fields FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert "kcal_per_base_unit" in (await hass.async_add_executor_job(manual))


async def test_an_implausible_off_label_is_dropped_not_refused(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """The person cannot fix a stranger's Open Food Facts entry: an
    implausible OFF-derived value is dropped and the article is still
    created with everything else, instead of refusing the whole scan."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    off_payload = {**MUESLI.product, "product_name_fr": "x" * 1000}
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli douteux", "base_unit": "g"},
        "off": off_payload, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    assert created["created"] is True
    assert created["off_dropped_fields"] == ["label"]

    def label():
        return entry.runtime_data.database.read().execute(
            "SELECT label FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert await hass.async_add_executor_job(label) is None


async def test_an_implausible_off_nova_is_neutralized_and_still_reported(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """off/mapping.py already refuses an out-of-range nova at the source: the
    article is created normally and nova lands NULL. That neutralisation
    used to be invisible to the panel (round 3) — off/mapping.py's own
    `rejections` now records it, and article_create merges that into
    off_dropped_fields (round 4), so the panel finds out either way."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    off_payload = {**MUESLI.product, "nova_group": 1e30}
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli douteux", "base_unit": "g"},
        "off": off_payload, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    assert created["created"] is True
    assert created["off_dropped_fields"] == ["nova"]

    def nova():
        return entry.runtime_data.database.read().execute(
            "SELECT nova FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert await hass.async_add_executor_job(nova) is None


async def test_a_dropped_nutriscore_is_reported_in_off_dropped_fields(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """off/mapping.py neutralises a genuinely implausible grade before the
    handler ever sees a bad nutriscore value, so _drop_invalid_off_values
    has nothing to catch — map_article's own `rejections` is what surfaces
    it in off_dropped_fields, so the panel can say something was ignored
    instead of a value going silently missing."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    off_payload = {**MUESLI.product, "nutriscore_grade": "zzz"}
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli douteux", "base_unit": "g"},
        "off": off_payload, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    assert created["created"] is True
    assert created["off_dropped_fields"] == ["nutriscore"]

    def nutriscore():
        return entry.runtime_data.database.read().execute(
            "SELECT nutriscore FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert await hass.async_add_executor_job(nutriscore) is None


async def test_an_off_no_grade_sentinel_reports_nothing_dropped(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """"unknown" is OFF's own way of saying "no grade" — 14 of 51 real
    catalogue records carry it. article/create must not tell the user a
    value was rejected when the record simply never had one."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    off_payload = {**MUESLI.product, "nutriscore_grade": "unknown"}
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli sans note", "base_unit": "g"},
        "off": off_payload, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    assert created["created"] is True
    assert created["off_dropped_fields"] == []


async def test_creating_an_article_refuses_an_oversized_off_payload(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A real OFF record is a few kilobytes; nothing should let one scan
    grow the database without bound."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    off_payload = {**MUESLI.product, "ingredients_text_fr": "x" * (300 * 1024)}
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli énorme", "base_unit": "g"},
        "off": off_payload, "off_source": "food",
    })
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def article_count():
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM article").fetchone()[0]

    assert await hass.async_add_executor_job(article_count) == 0


async def test_creating_an_article_refuses_an_overlong_off_source(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off_source": "x" * 500_000,
    })
    answer = await client.receive_json()

    # This field is validated at the top-level command schema, not through
    # _validate_fields — Home Assistant's own generic schema-error message
    # (English, out of scope per round 3's ruling) is what the client sees
    # here, not the _preview()-truncated French one _validate_fields builds.
    assert answer["success"] is False


async def test_creating_an_article_refuses_an_id_larger_than_64_bits(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/create", "code": "1",
                            "product_id": 2**64})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_getting_a_product_refuses_an_id_larger_than_64_bits(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """2**63 passes a bare `int` type check and only fails later, uncaught,
    when sqlite3 binds it as a query parameter — refused at the schema
    instead, like every other id."""
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/get",
                            "product_id": 2**63})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_getting_a_product_refuses_a_boolean_as_an_id(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A bare `int` schema entry accepts JSON `true`, which Python's int()
    resolves to 1 — the bounded validator must refuse it outright instead
    of silently resolving to a real product."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/get",
                            "product_id": True})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_product_update_accepts_the_offline_queues_idempotency_key(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """The catalogue screen writes through FileAttente like every other
    screen (Task 17), which stamps `idempotency_key` on every action
    uniformly — including a product edit. Unlike article/update and
    session/update_line, product/update never uses the key for anything; the
    schema must still accept it instead of refusing the whole write with an
    English voluptuous "extra keys not allowed"."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"name": "Nouveau nom"},
                            "idempotency_key": "cle-test"})
    answer = await client.receive_json()

    assert answer["success"] is True


async def test_an_unknown_column_is_refused_rather_than_written(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """The update path interpolates column names into SQL. The whitelist is
    what keeps that safe."""
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"id = 1; DROP TABLE product; --": 1}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_product_update_refuses_a_non_boolean_active_value(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """SQLite is dynamically typed: without value validation, "oui" lands
    straight in the `active` column and the product silently vanishes from
    every "active only" listing, with no error anywhere."""
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"active": "oui"}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_product_update_refuses_a_non_numeric_min_quantity(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A string in `min_quantity` would silently disable the shortage sensor
    for this product (the SQL comparison against it just never matches)."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"min_quantity": "abc"}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def min_quantity():
        return entry.runtime_data.database.read().execute(
            "SELECT min_quantity FROM product WHERE id = ?", (1,)).fetchone()[0]

    assert await hass.async_add_executor_job(min_quantity) is None


async def test_article_update_refuses_a_non_numeric_kcal(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A string in `kcal_per_base_unit` would make every later stock/add on
    this article fail deep inside movement_values() instead of being caught
    here, where the panel can actually explain what is wrong."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": 1, "fields": {"kcal_per_base_unit": "beaucoup"}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def kcal():
        return entry.runtime_data.database.read().execute(
            "SELECT kcal_per_base_unit FROM article WHERE id = ?", (1,)).fetchone()[0]

    assert await hass.async_add_executor_job(kcal) is None


async def test_article_create_refuses_an_unknown_field_instead_of_dropping_it(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """article/create must refuse a non-whitelisted key exactly like
    article/update and product/update do, instead of silently dropping it."""
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "fields": {"id = 1; DROP TABLE article; --": 1},
    })
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_creating_an_article_without_a_product_target_is_refused_in_french(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/create", "code": "1"})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_creating_a_second_article_under_an_existing_product_name_is_refused(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """The ordinary "I scanned a second size and typed the same name" flow
    must come back as a clear French refusal, not unknown_error plus a
    traceback."""
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli", "base_unit": "g"},
    })
    await client.receive_json()

    await client.send_json({
        "id": 2, "type": "home_stock/article/create", "code": "2",
        "new_product": {"name": "Muesli", "base_unit": "g"},
    })
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "already_exists"
    assert "Muesli" in answer["error"]["message"]


async def test_creating_a_product_refuses_a_value_an_edit_would_refuse(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A brand-new product must not be creatable in a state an edit of that
    same product would refuse. Reproduces the round-2 report verbatim:
    `new_product: {..., "active": "oui"}` used to succeed and the product
    then vanished from products/list (active = 1 required there), while the
    identical value on product/update was already refused."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Fantôme", "base_unit": "g", "active": "oui"},
    })
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def product_count() -> int:
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM product").fetchone()[0]

    assert await hass.async_add_executor_job(product_count) == 0


@pytest.mark.parametrize("new_product", [{}, {"name": "Truc"}, {"base_unit": "g"}])
async def test_creating_a_product_with_a_missing_required_field_is_refused(
        hass: HomeAssistant, setup_entry, hass_ws_client, new_product):
    """{}, a name with no base_unit, and a base_unit with no name each used
    to raise an unhandled TypeError out of insert_product's keyword-only
    signature — "Unknown error" plus a traceback, not a refusal."""
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/create", "code": "1",
                            "new_product": new_product})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_creating_a_product_refuses_an_unknown_field(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Truc", "base_unit": "g", "not_a_column": 1},
    })
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


@pytest.mark.parametrize("bad", ["inf", "-inf", "nan"])
async def test_product_update_refuses_a_non_finite_min_quantity(
        hass: HomeAssistant, setup_entry, hass_ws_client, bad):
    """vol.Coerce(float) alone accepts "inf"/"-inf"/"nan": an infinite
    min_quantity would flip the shortage sensor on permanently."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"min_quantity": bad}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def min_quantity():
        return entry.runtime_data.database.read().execute(
            "SELECT min_quantity FROM product WHERE id = ?", (1,)).fetchone()[0]

    assert await hass.async_add_executor_job(min_quantity) is None


@pytest.mark.parametrize("bad", ["inf", "-inf", "nan"])
async def test_article_update_refuses_a_non_finite_kcal(
        hass: HomeAssistant, setup_entry, hass_ws_client, bad):
    """An infinite kcal_per_base_unit would reach the append-only movement
    journal as Inf on the next stock/add — rendered as `null` by Home
    Assistant's own JSON encoder, hiding the corruption from the panel."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": 1, "fields": {"kcal_per_base_unit": bad}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def kcal():
        return entry.runtime_data.database.read().execute(
            "SELECT kcal_per_base_unit FROM article WHERE id = ?", (1,)).fetchone()[0]

    assert await hass.async_add_executor_job(kcal) is None


async def test_product_update_refuses_an_out_of_range_category_id(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """1e308 coerces to a 309-digit int; sqlite3 raises an uncaught
    OverflowError at bind time if this is not refused first."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"category_id": 1e308}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def category_id():
        return entry.runtime_data.database.read().execute(
            "SELECT category_id FROM product WHERE id = ?", (1,)).fetchone()[0]

    assert await hass.async_add_executor_job(category_id) is None


async def test_product_update_refuses_a_fractional_aisle_id(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """aisle_id: 3.7 must not be truncated and silently filed in aisle 3 —
    a different aisle than the one asked for."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"aisle_id": 3.7}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"

    def aisle_id():
        return entry.runtime_data.database.read().execute(
            "SELECT aisle_id FROM product WHERE id = ?", (1,)).fetchone()[0]

    assert await hass.async_add_executor_job(aisle_id) is None


async def test_article_update_refuses_a_negative_nova(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": 1, "fields": {"nova": -5}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_product_update_refuses_a_negative_days_after_opening(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"days_after_opening": -30}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_product_update_refuses_a_negative_min_quantity(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"min_quantity": -5}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_product_update_refuses_an_empty_name(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A whitespace-only name satisfies the NOT NULL column but names
    nothing a person could find again."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"name": "   "}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_product_update_refuses_a_non_zero_number_for_edible(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """cv.boolean would silently accept 5 as "true"; the stricter validator
    must not."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"edible": 5}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_article_update_refuses_an_overlong_label(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A 500 000-character label is not something a person typed, and the
    refusal message must not echo it back in full."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": 1, "fields": {"label": "x" * 500_000}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"
    assert len(answer["error"]["message"]) < 500


async def test_product_update_refuses_an_overlong_name(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"name": "x" * 500_000}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"
    assert len(answer["error"]["message"]) < 500


async def test_updating_an_article_refuses_an_id_larger_than_64_bits(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": 2**64, "fields": {}})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_updating_a_product_refuses_an_id_larger_than_64_bits(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 2**64, "fields": {}})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_a_dry_run_conversion_reports_without_touching_anything(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry(with_piece_product=True)
    client = await hass_ws_client(hass)

    def snapshot():
        conn = entry.runtime_data.database.read()
        product = conn.execute(
            "SELECT base_unit FROM product WHERE id = 1").fetchone()
        batch = conn.execute(
            "SELECT remaining FROM batch WHERE article_id = 1").fetchone()
        return product["base_unit"], batch["remaining"]

    before = await hass.async_add_executor_job(snapshot)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": 1, "to_unit": "g",
                            "reference_quantity": 500, "dry_run": True})
    report = (await client.receive_json())["result"]

    assert report["applied"] is False
    assert report["to_unit"] == "g"

    after = await hass.async_add_executor_job(snapshot)
    assert after == before


async def test_converting_a_product_already_in_the_target_unit_is_a_success(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A replayed conversion (the panel lost the connection before the ack,
    and replays from its offline queue) must not look like a refusal: the
    product already being in the requested unit is the success case."""
    entry = await setup_entry()
    manager = entry.runtime_data.manager

    def seed_product() -> int:
        with manager.db.write() as conn:
            return repo.insert_product(conn, name="Farine", base_unit="g")

    product_id = await hass.async_add_executor_job(seed_product)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": product_id, "to_unit": "g",
                            "reference_quantity": 500})
    answer = await client.receive_json()

    assert answer["success"] is True
    assert answer["result"]["applied"] is False
    assert answer["result"]["already_converted"] is True


async def test_converting_between_two_non_piece_units_is_still_refused(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """Only the "already at the requested unit" case is a success. A genuine
    ml -> g request on a product that was never "à la pièce" stays refused."""
    entry = await setup_entry()
    manager = entry.runtime_data.manager

    def seed_product() -> int:
        with manager.db.write() as conn:
            return repo.insert_product(conn, name="Lait", base_unit="ml")

    product_id = await hass.async_add_executor_job(seed_product)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": product_id, "to_unit": "g",
                            "reference_quantity": 500})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "conversion_refused"
    # The domain's own English wording must never reach the panel verbatim.
    assert "already stocked in" not in answer["error"]["message"]


async def test_converting_refuses_an_infinite_reference_quantity(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """reference_quantity used to be a bare vol.Coerce(float): "inf" would
    otherwise be echoed straight back in a "success" reply (already_
    converted's shortcut never even reaches plan_conversion's own plausible-
    weight check)."""
    await setup_entry(with_piece_product=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": 1, "to_unit": "g",
                            "reference_quantity": "inf"})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_converting_refuses_an_id_larger_than_64_bits(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": 2**64, "to_unit": "g",
                            "reference_quantity": 500})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_converting_refuses_an_overlong_packaging_name(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A 500 000-character packaging name used to be written verbatim on a
    successful conversion."""
    entry = await setup_entry(with_piece_product=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": 1, "to_unit": "g",
                            "reference_quantity": 500,
                            "packaging_name": "x" * 500_000})
    answer = await client.receive_json()

    assert answer["success"] is False

    def packaging_count():
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM packaging").fetchone()[0]

    assert await hass.async_add_executor_job(packaging_count) == 0


async def test_reordering_aisles_writes_the_new_walking_order(hass: HomeAssistant,
                                                              setup_entry, hass_ws_client):
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    def ids() -> list[int]:
        return [r["id"] for r in entry.runtime_data.database.read().execute(
            "SELECT id FROM aisle ORDER BY position").fetchall()]

    order = await hass.async_add_executor_job(ids)
    reversed_order = list(reversed(order))

    await client.send_json({"id": 1, "type": "home_stock/aisles/reorder",
                            "aisle_ids": reversed_order})
    await client.receive_json()

    assert await hass.async_add_executor_job(ids) == reversed_order


async def test_reordering_with_an_unknown_aisle_id_is_refused(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/aisles/reorder",
                            "aisle_ids": [999999]})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "not_found"


async def test_reordering_refuses_an_aisle_id_larger_than_64_bits(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/aisles/reorder",
                            "aisle_ids": [2**64]})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_reordering_aisles_accepts_the_offline_queues_idempotency_key(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """Same allowance as product/update: the settings screen (Task 17) reorders
    aisles through FileAttente, which always stamps `idempotency_key`."""
    entry = await setup_entry()
    client = await hass_ws_client(hass)

    def ids() -> list[int]:
        return [r["id"] for r in entry.runtime_data.database.read().execute(
            "SELECT id FROM aisle ORDER BY position").fetchall()]

    order = await hass.async_add_executor_job(ids)
    reversed_order = list(reversed(order))

    await client.send_json({"id": 1, "type": "home_stock/aisles/reorder",
                            "aisle_ids": reversed_order, "idempotency_key": "cle-test"})
    answer = await client.receive_json()

    assert answer["success"] is True
    assert await hass.async_add_executor_job(ids) == reversed_order


async def test_storing_directly_creates_a_batch_outside_any_session(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 500, "location_id": 1,
                            "best_before": "2027-01-01", "idempotency_key": "k1"})
    first = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 500, "location_id": 1,
                            "best_before": "2027-01-01", "idempotency_key": "k1"})
    again = (await client.receive_json())["result"]

    assert first["batch_id"] == again["batch_id"]

    def counts() -> tuple[int, int]:
        conn = entry.runtime_data.database.read()
        batches = conn.execute("SELECT COUNT(*) FROM batch").fetchone()[0]
        movements = conn.execute("SELECT COUNT(*) FROM movement").fetchone()[0]
        return batches, movements

    assert await hass.async_add_executor_job(counts) == (1, 1)


async def test_storing_stock_for_an_unknown_article_is_refused_in_french(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 999,
                            "quantity": 100, "location_id": 1})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "not_found"
    assert "999" in answer["error"]["message"]


async def test_storing_a_negative_quantity_is_refused(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": -5, "location_id": 1})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_value"


async def test_storing_stock_refuses_an_infinite_quantity(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """quantity used to be a bare vol.Coerce(float): "inf" answered success
    and landed Inf in batch.remaining/initial and movement.quantity, in a
    table triggers forbid UPDATE/DELETE on — irreparable, not just wrong."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": "inf", "location_id": 1})
    answer = await client.receive_json()

    assert answer["success"] is False

    def counts():
        conn = entry.runtime_data.database.read()
        return (conn.execute("SELECT COUNT(*) FROM batch").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM movement").fetchone()[0])

    assert await hass.async_add_executor_job(counts) == (0, 0)


async def test_storing_stock_refuses_an_infinite_price(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """price_per_base_unit used to be vol.Any(vol.Coerce(float), None): "inf"
    answered success and landed Inf in batch.price_per_base_unit,
    movement.cost, and a price row — all rendered as `null` by Home
    Assistant's JSON encoder, hiding the corruption from the panel."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 100, "location_id": 1,
                            "price_per_base_unit": "inf"})
    answer = await client.receive_json()

    assert answer["success"] is False

    def counts():
        conn = entry.runtime_data.database.read()
        return (conn.execute("SELECT COUNT(*) FROM batch").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM movement").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM price").fetchone()[0])

    assert await hass.async_add_executor_job(counts) == (0, 0, 0)


async def test_storing_stock_at_an_unknown_location_is_refused(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 100, "location_id": 999})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


async def test_storing_stock_refuses_an_id_larger_than_64_bits(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add",
                            "article_id": 2**64, "quantity": 1, "location_id": 1})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_storing_stock_refuses_an_unparseable_best_before(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """"pas une date" used to be accepted and stored verbatim, quietly
    breaking every later comparison against it (the expiry alert window, the
    "to eat soon" todo list, ...)."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 100, "location_id": 1,
                            "best_before": "pas une date"})
    answer = await client.receive_json()

    assert answer["success"] is False

    def batch_count():
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM batch").fetchone()[0]

    assert await hass.async_add_executor_job(batch_count) == 0


async def test_storing_stock_accepts_a_real_iso_date(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 100, "location_id": 1,
                            "best_before": "2027-01-01"})
    answer = await client.receive_json()

    assert answer["success"] is True


async def test_storing_stock_refuses_an_overlong_idempotency_key(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 100, "location_id": 1,
                            "idempotency_key": "x" * 500_000})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_updating_an_unknown_product_is_refused_instead_of_answering_success(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """article/update already got this right by fetching the row first;
    product/update must not silently answer success on zero matched rows."""
    await setup_entry()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 999, "fields": {"name": "Nouveau nom"}})
    answer = await client.receive_json()

    assert answer["success"] is False
    assert answer["error"]["code"] == "not_found"


async def test_open_prices_is_not_divided_by_the_net_weight_of_a_piece_product(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """Piece-tracked yoghurts, `net_quantity` 125, an Open Prices record of
    2,50 € the pack: the suggestion under « Prix payé (€ / unité) » must be
    2,50, not 0,02. Accepting 0,02 wrote a cost 125 times too small into the
    append-only journal, where it can only be offset, never corrected."""
    entry = await setup_entry(with_piece_product=True)
    entry.runtime_data.transport = FakeTransport(payload={"items": [
        {"price": 2.5, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 125}},
    ]})

    def _link() -> None:
        with entry.runtime_data.manager.db.write() as conn:
            repo.link_barcode(conn, "3033490004743", 1)

    await hass.async_add_executor_job(_link)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup",
                            "code": "3033490004743"})
    result = (await client.receive_json())["result"]

    assert result["known"] is True
    assert result["product"]["base_unit"] == "piece"
    assert result["price"]["source"] == "open_prices"
    assert result["price"]["price_per_base_unit"] == pytest.approx(2.5)


async def test_open_prices_still_divides_for_a_weighed_product(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """The other half of the same rule: a `g` product keeps its divisor, so
    the fix above cannot have been "stop dividing everywhere"."""
    entry = await setup_entry(with_article=True)
    entry.runtime_data.transport = FakeTransport(payload={"items": [
        {"price": 2.0, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 1000}},
    ]})

    def _link() -> None:
        with entry.runtime_data.manager.db.write() as conn:
            repo.link_barcode(conn, "3017620422003", 1)

    await hass.async_add_executor_job(_link)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup",
                            "code": "3017620422003"})
    result = (await client.receive_json())["result"]

    assert result["product"]["base_unit"] == "g"
    assert result["price"]["price_per_base_unit"] == pytest.approx(0.002)


async def test_storing_stock_refuses_a_negative_price(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A negative price used to answer success and write a cost of -250 into
    the append-only journal, which sensor.home_stock_stock_value then read
    as -250. It cannot be corrected there, only offset."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 100, "location_id": 1,
                            "price_per_base_unit": -2.5})
    answer = await client.receive_json()

    assert answer["success"] is False

    def batches() -> int:
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM batch").fetchone()[0]

    assert await hass.async_add_executor_job(batches) == 0


async def test_storing_stock_still_accepts_a_free_item(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """Zero is a real observation — a sample, a gift, a second pack for
    free — and the distinction is load-bearing elsewhere in this lot."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 100, "location_id": 1,
                            "price_per_base_unit": 0})
    answer = await client.receive_json()

    assert answer["success"] is True


async def test_the_shops_already_used_can_be_read_without_an_open_session(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """The chips the session-start screen offers. `session/current` carries
    the same list but answers null when no session exists — which is exactly
    when a shopper has to pick a shop."""
    entry = await setup_entry(with_article=True)

    def _seed() -> None:
        with entry.runtime_data.manager.db.write() as conn:
            repo.insert_price(conn, article_id=1, observed_on="2026-08-01",
                              price_per_base_unit=0.004, source="manual", store="Lidl")
            repo.insert_price(conn, article_id=1, observed_on="2026-08-12",
                              price_per_base_unit=0.005, source="manual", store="Leclerc")

    await hass.async_add_executor_job(_seed)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stores/list"})
    result = (await client.receive_json())["result"]

    assert result["stores"] == ["Leclerc", "Lidl"]


# --- Lot 2bis : la portion manuelle, refusée par le validateur partagé ------

async def _portion(client, valeur, product_id=1):
    await client.send_json_auto_id({
        "type": "home_stock/product/update", "product_id": product_id,
        "fields": {"manual_portion": valeur}})
    return await client.receive_json()


async def _lire_portion(hass, entry, product_id=1):
    return await hass.async_add_executor_job(
        lambda: repo.get_product(entry.runtime_data.manager.db.read(),
                                 product_id)["manual_portion"])


async def test_a_manual_portion_is_written_and_cleared(hass, setup_entry,
                                                       hass_ws_client):
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    assert (await _portion(client, 45))["success"]
    assert await _lire_portion(hass, entry) == 45.0
    assert (await _portion(client, None))["success"]
    assert await _lire_portion(hass, entry) is None


async def test_a_manual_portion_is_refused_on_a_piece_product(hass, setup_entry,
                                                              hass_ws_client):
    """Message français, et rien d'écrit : à la pièce une portion vaut une
    pièce."""
    entry = await setup_entry(with_piece_product=True)
    client = await hass_ws_client(hass)

    answer = await _portion(client, 45)
    assert answer["success"] is False
    assert "pièce" in answer["error"]["message"]
    assert await _lire_portion(hass, entry) is None


async def test_a_manual_portion_is_bounded_by_five_thousand_and_by_the_pack(
        hass, setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    client = await hass_ws_client(hass)

    trop_grande = await _portion(client, 6000)
    assert trop_grande["success"] is False
    assert "5000" in trop_grande["error"]["message"]

    # Aucun poids de paquet connu : la seule borne est celle du lot 2.
    assert (await _portion(client, 3000))["success"]

    def _set_net_quantity():
        with manager.db.write() as conn:
            conn.execute("UPDATE article SET net_quantity = 1000 WHERE id = 1")
    await hass.async_add_executor_job(_set_net_quantity)

    au_dessus_du_paquet = await _portion(client, 1200)
    assert au_dessus_du_paquet["success"] is False
    assert "1000" in au_dessus_du_paquet["error"]["message"]
    assert await _lire_portion(hass, entry) == 3000.0
    assert (await _portion(client, 1000))["success"]


async def test_the_manual_portion_goes_through_the_shared_validator(
        hass, setup_entry, hass_ws_client, monkeypatch):
    """La règle vit dans `validators.py`, jamais recopiée ici : si une
    deuxième copie apparaissait dans `websocket_api.py`, ce test passerait
    toujours alors que le service `home_stock.*` de demain serait plus
    faible."""
    from custom_components.home_stock import websocket_api

    appels = []

    def _espion(value, *, base_unit, max_net_quantity):
        appels.append((value, base_unit, max_net_quantity))
        return 45.0

    monkeypatch.setattr(websocket_api.validators, "check_manual_portion", _espion)
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _set_net_quantity():
        with manager.db.write() as conn:
            conn.execute("UPDATE article SET net_quantity = 900 WHERE id = 1")
    await hass.async_add_executor_job(_set_net_quantity)
    client = await hass_ws_client(hass)

    assert (await _portion(client, 45))["success"]
    assert appels == [(45.0, "g", 900.0)]
