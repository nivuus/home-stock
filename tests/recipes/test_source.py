"""Le client TheMealDB : jamais de levée, jamais de reprise.

Les deux fixtures sont de vraies réponses de l'API, capturées une fois à la
main puis versionnées. Le dépôt ne versionne aucun script d'appel.
"""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.recipes.source import (
    BULK_INTERVAL,
    TIMEOUT,
    MealDbClient,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "recipes"
LOOKUP = json.loads((FIXTURES / "themealdb_lookup.json").read_text(encoding="utf-8"))
SEARCH = json.loads((FIXTURES / "themealdb_search.json").read_text(encoding="utf-8"))
FILTER = json.loads((FIXTURES / "themealdb_filter.json").read_text(encoding="utf-8"))


class _Transport:
    """Un transport scripté. Il enregistre ce qu'on lui demande — c'est ce qui
    prouve qu'on n'a essayé qu'UNE fois."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = 0
        self.urls: list[str] = []
        self.headers: list[dict] = []
        self.timeouts: list[float] = []

    async def get_json(self, url, headers, timeout):
        self.calls += 1
        self.urls.append(url)
        self.headers.append(headers)
        self.timeouts.append(timeout)
        response = self._responses.pop(0) if self._responses else (200, {"meals": None})
        if isinstance(response, BaseException):
            raise response
        return response


def _client(*responses, key="1"):
    transport = _Transport(*responses)
    return MealDbClient(transport, key=key, user_agent="home_stock/test"), transport


# --- ce que la source sait faire -------------------------------------------

async def test_lookup_reads_the_captured_card():
    client, _ = _client((200, LOOKUP))
    card = await client.lookup("52772")
    assert card["idMeal"] == "52772"
    assert card["strMeal"] == "Teriyaki Chicken Casserole"
    # Les vingt paires existent toujours, la plupart vides : c'est la forme
    # que `recipes/mapping` devra digérer à la tâche suivante.
    assert card["strIngredient1"] == "soy sauce"
    assert (card["strIngredient20"] or "").strip() == ""


async def test_search_maps_the_summary_fields():
    client, transport = _client((200, SEARCH))
    hits = await client.search("chicken")
    assert len(hits) == len(SEARCH["meals"])
    first = hits[0]
    assert first.source_ref == SEARCH["meals"][0]["idMeal"]
    assert first.name == SEARCH["meals"][0]["strMeal"]
    assert first.image_url.startswith("https://")
    assert "search.php?s=chicken" in transport.urls[0]


async def test_by_ingredient_asks_the_filter_route():
    """`filter.php?i=` répond à la seule question qu'un garde-manger permet de
    poser : qu'est-ce que je peux faire avec ça."""
    client, transport = _client((200, FILTER))
    hits = await client.by_ingredient("chicken breast")
    assert len(hits) == len(FILTER["meals"])
    assert "filter.php?i=chicken%20breast" in transport.urls[0]


async def test_the_filter_route_has_no_category_and_that_is_not_an_error():
    """`filter.php` rend une forme RÉDUITE, sans `strCategory`. Une lecture par
    indexation planterait sur la moitié des routes de la même API."""
    assert "strCategory" not in FILTER["meals"][0]
    client, _ = _client((200, FILTER))
    hits = await client.by_ingredient("chicken breast")
    assert hits[0].category is None
    assert hits[0].name and hits[0].source_ref


async def test_the_key_from_the_options_lands_in_the_url():
    """La clé réglée dans les options atteint bien la route.

    La version n'est plus figée ici : « 9973533 » n'est pas la clé de test
    publique, donc elle part sur v2 — c'est `base_url_for` qui en décide, et
    les tests de bascule plus bas qui tiennent cette règle."""
    client, transport = _client((200, SEARCH), key="9973533")
    await client.search("chicken")
    assert "/9973533/search.php" in transport.urls[0]


async def test_the_user_agent_and_the_timeout_are_sent():
    client, transport = _client((200, SEARCH))
    await client.search("chicken")
    assert transport.headers[0]["User-Agent"] == "home_stock/test"
    assert transport.timeouts[0] == TIMEOUT


# --- tout ce qui tourne mal rend vide, et ne lève jamais --------------------

@pytest.mark.parametrize("response", [
    TimeoutError(),
    ConnectionResetError(),
    ValueError("truncated JSON"),
    (404, None),
    (500, None),
    (200, None),
    (200, ["pas un dict"]),
    (200, {"meals": None}),
    (200, {"meals": "pas une liste"}),
    (200, {}),
])
async def test_nothing_ever_raises_and_a_failure_reads_as_empty(response):
    """Timeout, connexion coupée, JSON tronqué, 404, 500, charge inattendue :
    pour l'appelant, c'est le même fait — la source n'a pas répondu. Laisser
    l'un d'eux s'échapper transformerait un écran de navigation en trace de
    pile."""
    client, _ = _client(response)
    assert await client.search("x") == []

    client, _ = _client(response)
    assert await client.by_ingredient("x") == []

    client, _ = _client(response)
    assert await client.lookup("52772") is None


async def test_meals_null_is_an_empty_search_not_an_error():
    """TheMealDB rend `{"meals": null}` quand il ne trouve rien. C'est une
    recherche vide, pas une panne — et l'appelant ne doit pas pouvoir les
    distinguer, sinon il affichera « erreur » sur une recherche infructueuse."""
    client, _ = _client((200, {"meals": None}))
    assert await client.search("plat qui n'existe pas") == []


async def test_a_row_without_an_id_is_dropped_not_crashed_on():
    client, _ = _client((200, {"meals": [
        {"strMeal": "Sans identifiant"},
        {"idMeal": "1", "strMeal": "Bon"},
        "pas un objet",
        {"idMeal": "2"},
    ]}))
    hits = await client.search("x")
    assert [h.source_ref for h in hits] == ["1"]


async def test_lookup_of_a_non_dict_first_meal_is_none():
    client, _ = _client((200, {"meals": ["pas un objet"]}))
    assert await client.lookup("52772") is None


@pytest.mark.parametrize("method, argument", [
    ("search", "x"), ("by_ingredient", "x"), ("lookup", "52772"),
])
async def test_only_one_attempt_is_ever_made(method, argument):
    """Aucune reprise : une source de découverte qui rejoue trois fois retarde
    un dîner pour rien."""
    client, transport = _client(TimeoutError())
    await getattr(client, method)(argument)
    assert transport.calls == 1


async def test_a_query_is_escaped_rather_than_pasted():
    client, transport = _client((200, SEARCH))
    await client.search("poulet & riz/curry")
    assert "&" not in transport.urls[0].split("?", 1)[1].removeprefix("s=")
    assert "poulet%20%26%20riz/curry" in transport.urls[0] or "%26" in transport.urls[0]


# --- l'intervalle des imports en lot ---------------------------------------

async def test_the_bulk_interval_is_respected_between_two_lookups():
    """Même dispositif que BULK_INTERVAL pour Open Food Facts : horloge et
    dormeur injectés, aucune attente réelle dans les tests."""
    now = [1000.0]
    slept: list[float] = []

    async def sleeper(seconds):
        slept.append(seconds)
        now[0] += seconds

    client = MealDbClient(_Transport(), user_agent="t",
                          clock=lambda: now[0], sleeper=sleeper)
    await client.wait_for_bulk()
    assert slept == []                     # le premier appel n'attend pas

    now[0] += 2.0
    await client.wait_for_bulk()
    assert slept == [pytest.approx(BULK_INTERVAL - 2.0)]


async def test_a_slow_call_does_not_add_a_wait_on_top():
    """Si l'appel précédent a déjà pris plus que l'intervalle, on repart tout
    de suite : l'intervalle est un plancher entre départs, pas une pénalité."""
    now = [1000.0]
    slept: list[float] = []

    async def sleeper(seconds):
        slept.append(seconds)

    client = MealDbClient(_Transport(), user_agent="t",
                          clock=lambda: now[0], sleeper=sleeper)
    await client.wait_for_bulk()
    now[0] += BULK_INTERVAL + 5.0
    await client.wait_for_bulk()
    assert slept == []


@pytest.mark.network
async def test_the_real_contract_has_not_moved():
    """Désactivé par défaut, comme le test réseau du lot 1 pour OFF. Il ne
    tourne qu'à la main : `./scripts/test.sh -m network`."""
    import aiohttp

    class _Real:
        async def get_json(self, url, headers, timeout):
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=timeout) as r:
                    return r.status, await r.json(content_type=None)

    client = MealDbClient(_Real(), user_agent="home_stock/network-test")
    card = await client.lookup("52772")
    assert card is not None
    assert card["strMeal"] == "Teriyaki Chicken Casserole"
    assert all(f"strIngredient{i}" in card for i in range(1, 21))


# --- la version de route se déduit de la clé --------------------------------

async def test_the_public_test_key_stays_on_v1():
    """« 1 » est la clé de test publique, et v2 la refuse : une installation
    sans abonnement doit rester sur la route qui lui répond."""
    client, transport = _client((200, SEARCH), key="1")
    await client.search("pasta")
    assert transport.urls[0].startswith("https://www.themealdb.com/api/json/v1/1/")


async def test_a_premium_key_goes_to_v2():
    """Une clé qui n'est pas « 1 » est une clé d'abonné, et le catalogue
    élargi ne vit que sur v2 : mesuré le 2026-08-22, `filter.php?i=chicken`
    rend 20 fiches sur v1 contre 21 sur v2 avec la MÊME clé. Rester sur v1
    avec une clé payante, c'est payer sans rien recevoir."""
    client, transport = _client((200, SEARCH), key="65432107")
    await client.search("pasta")
    assert transport.urls[0].startswith(
        "https://www.themealdb.com/api/json/v2/65432107/")


async def test_every_route_follows_the_same_version():
    """Les trois routes, pas seulement la recherche : une seule d'entre elles
    restée sur v1 rendrait un import incomplet sans le dire."""
    client, transport = _client((200, FILTER), (200, LOOKUP), key="65432107")
    await client.by_ingredient("chicken")
    await client.lookup("52772")
    assert all(url.startswith("https://www.themealdb.com/api/json/v2/")
               for url in transport.urls), transport.urls


async def test_the_key_is_still_quoted_into_the_route():
    """La bascule ne doit pas défaire ce que le lot 3 tenait : la clé reste
    dans le chemin, la valeur cherchée reste échappée."""
    client, transport = _client((200, SEARCH), key="65432107")
    await client.search("pâtes fraîches")
    assert "p%C3%A2tes%20fra%C3%AEches" in transport.urls[0]
