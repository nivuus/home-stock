"""Shared fixtures. The custom integration must be enabled for every test."""
import json
import sqlite3
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.off.client import OffLookup
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/home_stock during tests."""
    yield


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Give every test its own config directory.

    Left at the plugin's default, `hass_config_dir` resolves to a single fixed
    `testing_config` folder shared by the whole pytest run: home_stock.db (and
    its UNIQUE constraints on names) would then leak between unrelated tests
    that both create a "Frigo" location, in file order, silently making the
    suite order-dependent. `hass_tmp_config_dir` is the plugin's own fixture
    for this, copying the base config into a fresh tmp_path per test.
    """
    return hass_tmp_config_dir


class _LandmineSession:
    """Stands in for the real aiohttp session async_setup_entry hands to
    AiohttpTransport. Its .get() fails the test loudly instead of quietly
    reaching prices.openfoodfacts.org or world.openfoodfacts.org.

    Every path that could make a real request goes through setup_entry(),
    which always replaces entry.runtime_data.off_client and .transport with
    an inert or fake double before a test touches them (see _InertOffClient/
    _InertTransport below, and FakeOffClient/FakeTransport in
    tests/test_websocket_write.py) — so .get() firing here means one of
    those replacements was skipped, which is itself the bug to catch.
    """

    def get(self, *args, **kwargs):
        # pytest.fail() raises `Failed`, a BaseException — Home Assistant's
        # async_response wrapper only catches `Exception`, so a `Failed`
        # raised this deep escapes it uncaught, the websocket connection
        # handler task dies without ever calling send_result/send_error, and
        # the test's `receive_json()` hangs forever waiting for an answer
        # that will never come (confirmed: reproducing the regression with
        # `pytest.fail` here needed pytest-timeout to even notice, 20s
        # later, instead of failing on its own). `AssertionError` is a
        # plain `Exception`: the wrapper catches it, answers a normal error
        # frame, and the test's own assertions fail fast against that
        # frame instead of hanging.
        raise AssertionError(
            "a test reached the real aiohttp session: off_client/transport "
            "was not replaced with a fake before use"
        )


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Proof, not an argument: async_setup_entry's only source of a real
    session is homeassistant.helpers.aiohttp_client.async_get_clientsession.
    Patched in two places, deliberately redundant:

    - `custom_components.home_stock.async_get_clientsession`, the name
      `__init__.py` bound at import time (`from ... import
      async_get_clientsession`) — patching the source module attribute alone
      does not reach an already-bound name like this one.
    - `homeassistant.helpers.aiohttp_client.async_get_clientsession`, the
      source attribute itself — catches any *other* call site, including one
      that imports it fresh inside a function body (exactly the shape the
      original bug in websocket_api.py had, and confirmed by temporarily
      reintroducing it: without this second patch the regression reached a
      real aiohttp session and only failed on an unrelated event-loop error,
      not on this guard).

    Either transport ever making a real request now surfaces as an
    immediate test failure, instead of staying invisible behind
    latest_price()'s own "a suggestion must never fail a scan" exception
    handling.
    """
    monkeypatch.setattr(
        "custom_components.home_stock.async_get_clientsession",
        lambda hass: _LandmineSession(),
    )
    monkeypatch.setattr(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        lambda hass: _LandmineSession(),
    )


class _InertOffClient:
    """The off_client setup_entry() installs by default: answers "not found"
    and never reaches the network. A test that needs a real-looking OFF
    answer replaces entry.runtime_data.off_client with its own fake — see
    FakeOffClient in tests/test_websocket_write.py."""

    async def lookup(self, code: str) -> OffLookup:
        return OffLookup()

    async def lookup_with_retry(self, code: str, **kwargs) -> OffLookup:
        return await self.lookup(code)


class _InertTransport:
    """The transport setup_entry() installs by default: an empty Open Prices
    answer, never a real request. A test that needs to observe the calls (or
    a specific price) replaces entry.runtime_data.transport with its own
    fake — see FakeTransport in tests/test_websocket_write.py."""

    async def get_json(self, url: str, headers: dict, timeout: float):
        return 200, {"items": []}


@pytest.fixture
def setup_entry(hass):
    """Set up the home_stock integration for a test, and optionally seed it.

    Returns an async callable rather than being one itself: a plain function
    importable across test files broke under --import-mode=importlib the
    moment tests/__init__.py would exist, so this now works the way pytest
    is meant to share fixtures — dependency injection, no import.

    Called with no arguments, this is exactly what every lot 0 test already
    did by hand: add a bare MockConfigEntry and let the integration load.
    Every entry it returns gets an off_client and a transport that are inert
    by default — neither one reaches the network — so no test has to
    remember to swap them out just to stay silent; only a test that actually
    cares what OFF or Open Prices answered needs to install its own fake.

    `with_article` adds a location and a g-based article with no batch yet —
    ready for home_stock/stock/add. `with_piece_product` adds a piece-based
    product with one open batch — ready for home_stock/product/convert_unit.
    Both insert their location/product/article first, so with either flag
    alone the seeded row lands on id 1, matching the ids the tests hardcode.
    """
    async def _setup_entry(*, with_article: bool = False,
                           with_piece_product: bool = False) -> MockConfigEntry:
        entry = MockConfigEntry(domain=DOMAIN, data={})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entry.runtime_data.off_client = _InertOffClient()
        entry.runtime_data.transport = _InertTransport()

        if not (with_article or with_piece_product):
            return entry

        manager = entry.runtime_data.manager

        def _seed() -> tuple[int | None, int | None]:
            piece_article_id = piece_location_id = None
            with manager.db.write() as conn:
                if with_article:
                    location_id = repo.insert_location(conn, name="Placard", kind="pantry")
                    product_id = repo.insert_product(
                        conn, name="Article prêt à ranger", base_unit="g")
                    repo.insert_article(conn, product_id=product_id)
                if with_piece_product:
                    piece_location_id = repo.insert_location(
                        conn, name="Frigo courses", kind="fridge")
                    piece_product_id = repo.insert_product(
                        conn, name="Yaourts nature", base_unit="piece")
                    piece_article_id = repo.insert_article(
                        conn, product_id=piece_product_id, net_quantity=125)
            return piece_article_id, piece_location_id

        piece_article_id, piece_location_id = await hass.async_add_executor_job(_seed)
        if with_piece_product:
            await hass.async_add_executor_job(lambda: manager.add_stock(
                article_id=piece_article_id, quantity=6, location_id=piece_location_id,
                occurred_at="2026-08-18T10:00:00"))
        # Mirror what both production write paths (the services, the todo
        # entity) do: refresh the coordinator after writing directly through
        # the manager, bypassing both of those paths.
        await entry.runtime_data.coordinator.async_request_refresh()
        # ...and then let it actually land. `async_request_refresh` is
        # DEBOUNCED: awaiting it only schedules the refresh, so without this
        # every test built on this fixture started with a refresh still in
        # flight, and the listener it eventually calls
        # (ExpirationEventEntity._handle_coordinator_update, which spawns a
        # claim task) ran at whatever await point the test reached first —
        # usually right after its own add_stock. The batch was then already
        # claimed when the test came to claim it, and the assertion read
        # `count == 2` instead of 3, or `[] != ["approaching"]`. It tripped
        # roughly one run in five, on a different test each time, which is
        # what a shared un-drained task looks like from the outside.
        await hass.async_block_till_done()
        return entry

    return _setup_entry


# --- lot 7 : les tables Grocy figées ----------------------------------------

_FIXTURES_GROCY = (
    "recipes", "recipes_pos", "stock", "products", "meal_plan",
    "meal_plan_sections", "shopping_list", "quantity_unit_conversions",
    "quantity_units", "locations", "stock_log", "chores_log", "chores",
    "product_groups", "product_barcodes", "userfields", "userfield_values",
    "shopping_locations", "inline_images", "recipes_phantoms",
)

# Les tables vides de Grocy : SELECT * ne donne pas leurs colonnes, et une
# table absente du schéma reconstruit ferait échouer une lecture légitime.
_COLONNES_TABLES_VIDES = {"shopping_locations": ("id", "name")}


@pytest.fixture(scope="session")
def grocy_reel() -> dict[str, list[dict]]:
    """Les tables Grocy figées le 2026-08-21. Lecture seule, jamais réécrites."""
    base = Path(__file__).parent / "fixtures" / "grocy"
    return {nom: json.loads((base / f"{nom}.json").read_text("utf-8"))
            for nom in _FIXTURES_GROCY}


def _affinity(values) -> str:
    """Le type SQLite d'une colonne, déduit de ce que la fixture y met."""
    for value in values:
        if isinstance(value, bool):
            return "INTEGER"
        if isinstance(value, int):
            return "INTEGER"
        if isinstance(value, float):
            return "REAL"
        if isinstance(value, str):
            return "TEXT"
    return "TEXT"


def _build_grocy_db(path, tables: dict[str, list[dict]]) -> None:
    conn = sqlite3.connect(str(path))
    try:
        for nom, lignes in tables.items():
            colonnes = list(lignes[0]) if lignes else list(
                _COLONNES_TABLES_VIDES.get(nom, ()))
            if not colonnes:
                continue
            declaration = ", ".join(
                f'"{col}" {_affinity(l[col] for l in lignes)}' for col in colonnes)
            conn.execute(f'CREATE TABLE "{nom}" ({declaration})')
            conn.executemany(
                f'INSERT INTO "{nom}" VALUES ({", ".join("?" * len(colonnes))})',
                [tuple(ligne[col] for col in colonnes) for ligne in lignes])
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def grocy_reel_db(tmp_path, grocy_reel) -> str:
    """Une base SQLite reconstruite depuis les fixtures.

    Reconstruite, et pas copiée : le schéma minimal qu'on écrit ici est
    exactement ce que les imports lisent, donc une colonne lue et non
    déclarée devient une erreur de test au lieu d'un import qui « marche
    parce que la vraie base l'avait ».
    """
    chemin = tmp_path / "grocy_reel.db"
    tables = {nom: lignes for nom, lignes in grocy_reel.items()
              if nom not in ("inline_images", "recipes_phantoms")}
    # Les 166 copies fantômes vivent dans la MÊME table `recipes` que les 102
    # vraies : c'est la seule façon que le filtre de l'import ait quelque
    # chose à écarter. Rangées à part dans les fixtures pour que les tests de
    # volumétrie continuent de compter 102 recettes.
    tables["recipes"] = tables["recipes"] + grocy_reel["recipes_phantoms"]
    _build_grocy_db(chemin, tables)
    return str(chemin)
