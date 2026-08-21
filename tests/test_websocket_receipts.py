"""Les commandes du ticket, pilotées exactement comme le panneau les pilote."""
import json
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock.receipt import task as receipt_task
from custom_components.home_stock.storage import repositories as repo

FIXTURES = Path(__file__).parent / "fixtures" / "receipts"
PHOTO = "media-source://media_source/local/home_stock/receipts/t.jpg"


async def _send(client, id_, type_, **payload):
    await client.send_json({"id": id_, "type": type_, **payload})
    return await client.receive_json()


@pytest.fixture
def lecture(monkeypatch):
    """Le double : rien ne sort du processus."""
    state = {"answer": json.loads((FIXTURES / "propre.json").read_text(encoding="utf-8")),
             "error": None, "calls": 0}

    async def _read_receipt(hass, **kwargs):
        state["calls"] += 1
        state["seen"] = kwargs
        if state["error"] is not None:
            return receipt_task.ReceiptReadResult(
                error=state["error"], agent_entity_id="ai_task.gemini")
        from custom_components.home_stock.receipt.parse import parse
        parsed = parse(state["answer"],
                       session_started_on=kwargs["session_started_on"],
                       today=kwargs["today"])
        return receipt_task.ReceiptReadResult(
            parsed=parsed, raw=json.dumps(state["answer"], ensure_ascii=False),
            agent_entity_id="ai_task.gemini")

    import custom_components.home_stock.websocket_receipts as module
    monkeypatch.setattr(module, "read_receipt", _read_receipt)
    return state


async def _trip(hass, entry):
    """Un voyage ouvert avec une ligne scannée."""
    manager = entry.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            repo.update_article_fields(conn, 1, {"label": "Lait demi-écrémé 1 L"})
            store_id = repo.upsert_store(conn, name="Leclerc")
            session_id = repo.open_session(conn, started_at="2026-08-21T19:00:00",
                                           store="Leclerc", store_id=store_id)
            repo.add_line(conn, session_id=session_id, article_id=1, quantity=1000,
                          unit_price=0.0009, scanned_at="2026-08-21T19:05:00",
                          idempotency_key=None, price_source="open_prices")
            return session_id

    return await hass.async_add_executor_job(_seed)


async def test_submitting_records_the_receipt_and_starts_the_read(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)

    answer = await _send(client, 1, "home_stock/receipt/submit",
                         media_content_id=PHOTO)

    assert answer["success"] is True
    assert answer["result"]["state"] == "read"
    assert lecture["calls"] == 1
    assert len(answer["result"]["lines"]) == 5


async def test_submitting_the_same_key_twice_returns_the_first_receipt(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)

    first = await _send(client, 1, "home_stock/receipt/submit",
                        media_content_id=PHOTO, idempotency_key="photo-1")
    again = await _send(client, 2, "home_stock/receipt/submit",
                        media_content_id=PHOTO, idempotency_key="photo-1")

    assert again["result"]["id"] == first["result"]["id"]
    assert lecture["calls"] == 1


@pytest.mark.parametrize("media_id", [
    "www/tickets/t.jpg",
    "/etc/passwd",
    "../config/secrets.yaml",
])
async def test_a_dangerous_media_id_is_refused(hass: HomeAssistant, setup_entry,
                                               hass_ws_client, lecture, media_id):
    """Tout ce qui vit dans `www/` est servi sur `/local/` SANS
    authentification, et un ticket porte un magasin, une heure et des
    habitudes."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    refused = await _send(client, 1, "home_stock/receipt/submit",
                          media_content_id=media_id)
    assert refused["success"] is False
    assert lecture["calls"] == 0


async def test_get_returns_the_lines_face_to_face(hass: HomeAssistant, setup_entry,
                                                  hass_ws_client, lecture):
    """Lignes lues d'un côté, lignes de panier de l'autre, et l'écart au
    total. C'est l'écran."""
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    submitted = await _send(client, 1, "home_stock/receipt/submit",
                            media_content_id=PHOTO)

    answer = await _send(client, 2, "home_stock/receipt/get",
                         receipt_id=submitted["result"]["id"])

    result = answer["result"]
    assert len(result["lines"]) == 5
    assert len(result["cart_lines"]) == 1
    assert "total_gap" in result
    assert result["lines"][0]["candidates"]


async def test_retry_increments_attempts_and_keeps_the_photo(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    lecture["error"] = "Le modèle n'a pas répondu."
    submitted = await _send(client, 1, "home_stock/receipt/submit",
                            media_content_id=PHOTO)
    assert submitted["result"]["state"] == "failed"
    assert submitted["result"]["attempts"] == 1

    lecture["error"] = None
    retried = await _send(client, 2, "home_stock/receipt/retry",
                          receipt_id=submitted["result"]["id"])

    assert retried["result"]["state"] == "read"
    assert retried["result"]["attempts"] == 2
    assert retried["result"]["media_content_id"] == PHOTO


async def test_discard_leaves_the_photo_and_the_lines_in_place(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    """Abandonner n'est pas effacer la preuve."""
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    submitted = await _send(client, 1, "home_stock/receipt/submit",
                            media_content_id=PHOTO)

    discarded = await _send(client, 2, "home_stock/receipt/discard",
                            receipt_id=submitted["result"]["id"])

    assert discarded["result"]["state"] == "discarded"
    assert discarded["result"]["media_content_id"] == PHOTO
    assert len(discarded["result"]["lines"]) == 5


async def test_matching_by_hand_accepts_null_to_ignore_a_line(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    submitted = await _send(client, 1, "home_stock/receipt/submit",
                            media_content_id=PHOTO)
    line_id = submitted["result"]["lines"][0]["id"]

    answer = await _send(client, 2, "home_stock/receipt/line/match",
                         line_id=line_id, shopping_line_id=None, state="ignored")

    assert answer["success"] is True
    matched = next(line for line in answer["result"]["lines"]
                   if line["id"] == line_id)
    assert matched["match_state"] == "ignored" and matched["line_id"] is None


async def test_apply_needs_a_read_receipt(hass: HomeAssistant, setup_entry,
                                          hass_ws_client, lecture):
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    lecture["error"] = "Le modèle n'a pas répondu."
    submitted = await _send(client, 1, "home_stock/receipt/submit",
                            media_content_id=PHOTO)

    refused = await _send(client, 2, "home_stock/receipt/apply",
                          receipt_id=submitted["result"]["id"])

    assert refused["success"] is False
    assert "pas été lu" in refused["error"]["message"]


async def test_applying_corrects_the_cart_line(hass: HomeAssistant, setup_entry,
                                               hass_ws_client, lecture):
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    submitted = await _send(client, 1, "home_stock/receipt/submit",
                            media_content_id=PHOTO)
    receipt_id = submitted["result"]["id"]
    milk = next(line for line in submitted["result"]["lines"]
                if line["label"] == "LT DEMI ECR 1L")
    cart_line_id = (await _send(client, 2, "home_stock/receipt/get",
                                receipt_id=receipt_id))["result"]["cart_lines"][0]["id"]
    await _send(client, 3, "home_stock/receipt/line/match", line_id=milk["id"],
                shopping_line_id=cart_line_id, state="confirmed")

    applied = await _send(client, 4, "home_stock/receipt/apply", receipt_id=receipt_id)

    assert applied["result"]["applied"] == 1
    assert applied["result"]["state"] == "applied"


async def test_every_write_command_accepts_an_idempotency_key(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    """Le contrat de la file hors ligne. Le téléversement d'une photo et le
    rapprochement d'une ligne sont des ÉCRITURES comme les autres, et se font
    typiquement là où le réseau est le plus mauvais."""
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    submitted = await _send(client, 1, "home_stock/receipt/submit",
                            media_content_id=PHOTO, idempotency_key="a")
    receipt_id = submitted["result"]["id"]
    line_id = submitted["result"]["lines"][0]["id"]

    for number, (command, payload) in enumerate([
            ("home_stock/receipt/line/match",
             {"line_id": line_id, "shopping_line_id": None, "state": "ignored"}),
            ("home_stock/receipt/retry", {"receipt_id": receipt_id}),
            ("home_stock/receipt/apply", {"receipt_id": receipt_id}),
            ("home_stock/receipt/discard", {"receipt_id": receipt_id}),
    ], start=10):
        answer = await _send(client, number, command,
                             idempotency_key=f"clef-{number}", **payload)
        assert answer["success"] is True, command


async def test_an_unknown_receipt_is_refused_in_french(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    refused = await _send(client, 1, "home_stock/receipt/get", receipt_id=4242)
    assert refused["success"] is False
    assert refused["error"]["message"] == "Ticket 4242 inconnu."


async def test_the_pending_sensor_publishes_the_last_error_in_french(
        hass: HomeAssistant, setup_entry, hass_ws_client, lecture):
    entry = await setup_entry(with_article=True)
    await _trip(hass, entry)
    client = await hass_ws_client(hass)
    lecture["error"] = "Le modèle n'a pas pu lire le ticket."
    await _send(client, 1, "home_stock/receipt/submit", media_content_id=PHOTO)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_stock_receipts_pending")
    assert state.state == "1"
    assert state.attributes["last_error"] == "Le modèle n'a pas pu lire le ticket."


async def test_the_pending_sensor_is_zero_with_no_receipt(hass: HomeAssistant,
                                                          setup_entry):
    await setup_entry(with_article=True)
    state = hass.states.get("sensor.home_stock_receipts_pending")
    assert state.state == "0"
    assert state.attributes["last_error"] is None
