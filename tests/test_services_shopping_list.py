"""Les services de la liste : la porte du vocal, et la lecture d'un ticket."""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.home_stock.storage import repositories as repo


async def _call(hass, service, payload=None, response=False):
    return await hass.services.async_call(
        "home_stock", service, payload or {}, blocking=True,
        return_response=response)


async def test_add_to_shopping_list_accepts_a_product_or_a_text(
        hass: HomeAssistant, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            return repo.insert_product(conn, name="Beurre", base_unit="g")

    product_id = await hass.async_add_executor_job(_seed)
    await _call(hass, "add_to_shopping_list", {"product_id": product_id,
                                               "quantity": 250})
    await _call(hass, "add_to_shopping_list", {"free_text": "Piles"})

    rows = repo.list_items(manager.db.read())
    assert {row["product_name"] or row["free_text"] for row in rows} == \
        {"Beurre", "Piles"}


async def test_add_to_shopping_list_is_the_voice_door(hass: HomeAssistant,
                                                      setup_entry):
    """Une charge minimale — juste un texte — doit passer : « Bleuenn,
    ajoute du beurre à la liste »."""
    entry = await setup_entry(with_article=True)
    await _call(hass, "add_to_shopping_list", {"free_text": "beurre"})
    rows = repo.list_items(entry.runtime_data.manager.db.read())
    assert len(rows) == 1


async def test_add_to_shopping_list_answers_the_line_it_wrote(
        hass: HomeAssistant, setup_entry):
    await setup_entry(with_article=True)
    answer = await _call(hass, "add_to_shopping_list", {"free_text": "Pain"},
                         response=True)
    assert answer["item_id"] and answer["created"] is True


async def test_refresh_shopping_list_returns_nothing_and_writes(
        hass: HomeAssistant, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Lait", base_unit="ml",
                                             min_quantity=2000)
            repo.insert_article(conn, product_id=product_id, is_generic=1)

    await hass.async_add_executor_job(_seed)
    assert await _call(hass, "refresh_shopping_list") is None
    assert len(repo.list_items(manager.db.read())) == 1


async def test_query_shopping_list_answers_without_creating_an_entity(
        hass: HomeAssistant, setup_entry):
    """`SupportsResponse.ONLY`, comme `query_stock` : une entité par ligne de
    liste serait une entité par produit sous son seuil, qui va et vient."""
    await setup_entry(with_article=True)
    before = len(hass.states.async_entity_ids())

    answer = await _call(hass, "query_shopping_list", response=True)

    assert answer == {"items": {}, "count": 0,
                      "estimate": {"amount": 0.0, "confidence": 1.0,
                                   "priced": 0, "total": 0}}
    assert len(hass.states.async_entity_ids()) == before


async def test_query_shopping_list_groups_by_aisle(hass: HomeAssistant, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
            product_id = repo.insert_product(conn, name="Lait", base_unit="ml",
                                             aisle_id=aisles["Crémerie"])
            item_id = repo.insert_list_item(conn, added_at="2026-08-21T09:00:00",
                                            product_id=product_id, quantity=2000.0)
            repo.set_claim(conn, item_id=item_id, origin="manual", quantity=2000.0,
                           detail="ajouté à la main",
                           claimed_at="2026-08-21T09:00:00")
            repo.insert_list_item(conn, added_at="2026-08-21T09:00:00",
                                  free_text="Piles")

    await hass.async_add_executor_job(_seed)
    answer = await _call(hass, "query_shopping_list", response=True)

    assert set(answer["items"]) == {"Crémerie", "Sans rayon"}
    assert answer["count"] == 2
    assert answer["items"]["Crémerie"][0]["reasons"] == ["ajouté à la main"]


async def test_query_shopping_list_hides_what_is_already_in_the_cart(
        hass: HomeAssistant, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            item_id = repo.insert_list_item(conn, added_at="2026-08-21T09:00:00",
                                            free_text="Pain")
            repo.check_list_item(conn, item_id, at="2026-08-21T10:00:00",
                                 session_id=None, line_id=None)
            return item_id

    await hass.async_add_executor_job(_seed)
    assert (await _call(hass, "query_shopping_list", response=True))["count"] == 0


# --- le ticket --------------------------------------------------------------

async def test_read_receipt_retries_the_last_failed_one_when_given_nothing(
        hass: HomeAssistant, setup_entry, monkeypatch):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            receipt_id = repo.insert_receipt(
                conn, media_content_id="media-source://media_source/local/t.jpg",
                captured_at="2026-08-21T20:00:00")
            repo.set_receipt_state(conn, receipt_id, "failed",
                                   error="Le modèle n'a pas répondu.")
            return receipt_id

    receipt_id = await hass.async_add_executor_job(_seed)

    import custom_components.home_stock.websocket_receipts as module
    from custom_components.home_stock.receipt.parse import ParsedLine, ParsedReceipt
    from custom_components.home_stock.receipt.task import ReceiptReadResult

    async def _read(hass_, **kwargs):
        return ReceiptReadResult(
            parsed=ParsedReceipt(store="Leclerc", purchased_on="2026-08-21",
                                 total=1.05,
                                 lines=(ParsedLine(1, "LT DEMI", 1, 1.05, 1.05),)),
            raw="{}", agent_entity_id="ai_task.gemini")

    monkeypatch.setattr(module, "read_receipt", _read)

    answer = await _call(hass, "read_receipt", response=True)

    assert answer["receipt_id"] == receipt_id
    assert answer["state"] == "read" and answer["lines"] == 1


async def test_read_receipt_with_no_pending_receipt_says_so(hass: HomeAssistant,
                                                            setup_entry):
    await setup_entry(with_article=True)
    with pytest.raises(HomeAssistantError, match="Aucun ticket"):
        await _call(hass, "read_receipt")


async def test_read_receipt_on_an_unknown_id_says_so_in_french(
        hass: HomeAssistant, setup_entry):
    await setup_entry(with_article=True)
    with pytest.raises(HomeAssistantError) as refus:
        await _call(hass, "read_receipt", {"receipt_id": 4242})
    assert str(refus.value) == "Ticket 4242 inconnu."
