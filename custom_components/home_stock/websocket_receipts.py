"""Les six commandes du ticket, dans leur propre module.

Même décision qu'aux lots 3 et 5 : `websocket_api.py` fait déjà plus de
1 250 lignes, et deux lots qui l'allongent en parallèle sont un conflit de
fusion sur presque chaque bloc. Le lot 4 y ajoute exactement deux lignes —
un import et un appel — et tout le reste vit ici.

Les helpers partagés (`_runtime`, `_read`, `_send_domain_error`,
`_send_not_loaded`) sont IMPORTÉS de `websocket_api`, jamais recopiés : deux
copies d'un traducteur d'erreurs sont deux vocabulaires dans six mois.
"""
from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import CONF_RECEIPT_AGENT, MATCH_STATES
from .domain.matching import receipt_candidates
from .receipt.task import read_receipt
from .storage import repositories as repo
from .validators import bounded_int, bounded_text, media_path
from .websocket_api import (
    _read,
    _runtime,
    _send_domain_error,
    _send_not_loaded,
)

_id: Final = vol.All(bounded_int, vol.Range(min=0))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


def _media(value: Any) -> str:
    """Le chemin de la photo, validé comme tout chemin de média.

    `validators.media_path` refuse déjà l'absolu, le `..` et tout ce qui vit
    sous `www/` — servi sur `/local/` SANS authentification. Un ticket porte
    un magasin, une heure et des habitudes.
    """
    # `media-source://media_source/local/...` est ce que rend le téléversement
    # de Home Assistant ; c'est le suffixe qui est un chemin.
    prefix = "media-source://media_source/local/"
    text = bounded_text(value)
    if not text:
        raise vol.Invalid("a receipt needs a photo")
    tail = text[len(prefix):] if text.startswith(prefix) else text
    media_path(tail)
    return text


def _view(conn, receipt_id: int) -> dict[str, Any]:
    """Le ticket tel que l'écran le lit : lignes lues, lignes de panier, écart."""
    receipt = repo.get_receipt(conn, receipt_id)
    if receipt is None:
        raise LookupError(f"unknown receipt {receipt_id}")
    cart = (repo.list_lines(conn, receipt["session_id"])
            if receipt["session_id"] else [])
    lines = []
    for line in receipt["lines"]:
        candidates = receipt_candidates(label=line["label"], lines=cart,
                                        unit_price=line["unit_price"])
        lines.append({**line, "candidates": [
            {"line_id": match.line_id, "label": match.label, "score": match.score}
            for match in candidates[:5]]})
    summed = sum(line["total_price"] or 0.0 for line in receipt["lines"])
    total = receipt["total"]
    return {
        **receipt, "lines": lines, "cart_lines": cart,
        "lines_total": round(summed, 2),
        "total_gap": None if total is None else round(total - summed, 2),
    }


async def _answer(hass, connection, msg, receipt_id: int, **extra) -> None:
    runtime = _runtime(hass)
    view = await _read(hass, partial(_view, runtime.manager.db.read(), receipt_id))
    connection.send_result(msg["id"], {**view, **extra})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/receipt/submit",
    vol.Required("media_content_id"): _media,
    vol.Optional("session_id"): _id,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def receipt_submit(hass, connection, msg) -> None:
    """Enregistre la photo et lance la lecture.

    La photo est enregistrée AVANT la lecture : si le modèle ne répond pas,
    la pièce justificative est déjà là et `home_stock.read_receipt`
    réessaiera. L'inverse perdrait la photo à chaque échec.
    """
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    manager = runtime.manager
    key = msg.get("idempotency_key")

    def _record() -> int:
        with manager.db.write() as conn:
            if key:
                existing = conn.execute(
                    "SELECT br.id FROM receipt br WHERE br.media_content_id = ?"
                    "   AND br.captured_at IS NOT NULL AND br.error IS NOT ?"
                    " ORDER BY br.id LIMIT 1",
                    (msg["media_content_id"], "__jamais__")).fetchone()
                if existing is not None:
                    return int(existing["id"])
            session = repo.current_session(conn)
            session_id = msg.get("session_id") or (
                int(session["id"]) if session else None)
            store_id = session["store_id"] if session else None
            return repo.insert_receipt(
                conn, media_content_id=msg["media_content_id"],
                captured_at=_now(), session_id=session_id, store_id=store_id)

    receipt_id = await hass.async_add_executor_job(_record)
    already = await _read(hass, partial(repo.get_receipt,
                                        manager.db.read(), receipt_id))
    if already["state"] == "pending":
        await _perform_read(hass, runtime, receipt_id)
    await runtime.coordinator.async_request_refresh()
    await _answer(hass, connection, msg, receipt_id)


async def _perform_read(hass: HomeAssistant, runtime, receipt_id: int) -> None:
    """Faire lire la photo, et écrire ce qui en revient. Ne lève jamais."""
    manager = runtime.manager
    conn = manager.db.read()
    receipt = await _read(hass, partial(repo.get_receipt, conn, receipt_id))
    session_id = receipt["session_id"]
    cart = await _read(hass, partial(
        repo.list_lines, conn, session_id)) if session_id else []
    session = await _read(hass, partial(
        repo.get_session, conn, session_id)) if session_id else None
    labels = [line["article_label"] or line["product_name"] for line in cart]
    started = (session["started_at"][:10] if session else _now()[:10])
    # Même chemin qu'au lot 3 pour `recipe_agent` : l'entrée chargée, pas
    # une référence conservée dans le runtime — changer l'option prend effet
    # au rechargement, sans redémarrer Home Assistant.
    entries = hass.config_entries.async_loaded_entries("home_stock")
    agent = entries[0].options.get(CONF_RECEIPT_AGENT) if entries else None

    result = await read_receipt(
        hass, agent_entity_id=agent,
        media_content_id=receipt["media_content_id"],
        session_labels=labels, session_started_on=started, today=_now()[:10])

    def _write() -> None:
        with manager.db.write() as write_conn:
            attempts = (receipt["attempts"] or 0) + 1
            if result.parsed is None:
                repo.set_receipt_state(
                    write_conn, receipt_id, "failed", error=result.error,
                    attempts=attempts, agent_entity_id=result.agent_entity_id,
                    raw=result.raw)
                return
            parsed = result.parsed
            lines = []
            for line in parsed.lines:
                candidates = receipt_candidates(
                    label=line.label, lines=cart, unit_price=line.unit_price)
                best = candidates[0] if candidates else None
                auto = best is not None and _is_auto(candidates)
                lines.append({
                    "position": line.position, "label": line.label,
                    "quantity": line.quantity, "unit_price": line.unit_price,
                    "total_price": line.total_price,
                    "line_id": best.line_id if auto else None,
                    "match_state": "auto" if auto else "unmatched",
                })
            repo.replace_receipt_lines(write_conn, receipt_id, lines)
            repo.set_receipt_state(
                write_conn, receipt_id, "read", error=None, attempts=attempts,
                read_at=_now(), purchased_on=parsed.purchased_on,
                total=parsed.total, agent_entity_id=result.agent_entity_id,
                raw=result.raw)

    await hass.async_add_executor_job(_write)


def _is_auto(candidates) -> bool:
    """Les seuils du lot 1, tels quels : `preselect` est le seul arbitre."""
    from .domain.matching import preselect
    return preselect(candidates) is not None


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/receipt/get",
    vol.Required("receipt_id"): _id,
})
@websocket_api.async_response
async def receipt_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        await _answer(hass, connection, msg, msg["receipt_id"])
    except LookupError as err:
        _send_domain_error(connection, msg["id"], err)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/receipt/list",
    vol.Optional("states"): [bounded_text],
})
@websocket_api.async_response
async def receipt_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    rows = await _read(hass, partial(repo.list_receipts, runtime.manager.db.read(),
                                     states=msg.get("states")))
    connection.send_result(msg["id"], {"receipts": rows})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/receipt/retry",
    vol.Required("receipt_id"): _id,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def receipt_retry(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        await _perform_read(hass, runtime, msg["receipt_id"])
        await runtime.coordinator.async_request_refresh()
        await _answer(hass, connection, msg, msg["receipt_id"])
    except LookupError as err:
        _send_domain_error(connection, msg["id"], err)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/receipt/discard",
    vol.Required("receipt_id"): _id,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def receipt_discard(hass, connection, msg) -> None:
    """Abandonner n'est pas effacer la preuve : la photo et les lignes lues
    restent en place, seul l'état change."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    manager = runtime.manager

    def _discard() -> None:
        with manager.db.write() as conn:
            repo.set_receipt_state(conn, msg["receipt_id"], "discarded")

    await hass.async_add_executor_job(_discard)
    await runtime.coordinator.async_request_refresh()
    try:
        await _answer(hass, connection, msg, msg["receipt_id"])
    except LookupError as err:
        _send_domain_error(connection, msg["id"], err)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/receipt/line/match",
    vol.Required("line_id"): _id,
    vol.Required("shopping_line_id"): vol.Any(_id, None),
    vol.Required("state"): vol.In(MATCH_STATES),
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def receipt_line_match(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    manager = runtime.manager
    try:
        await hass.async_add_executor_job(partial(
            manager.match_receipt_line, msg["line_id"],
            line_id=msg["shopping_line_id"], state=msg["state"]))
    except ValueError as err:
        _send_domain_error(connection, msg["id"], err)
        return

    def _owner() -> int | None:
        row = manager.db.read().execute(
            "SELECT rl.receipt_id FROM receipt_line rl WHERE rl.id = ?",
            (msg["line_id"],)).fetchone()
        return int(row["receipt_id"]) if row else None

    receipt_id = await hass.async_add_executor_job(_owner)
    if receipt_id is None:
        _send_domain_error(connection, msg["id"],
                           LookupError(f"unknown receipt {msg['line_id']}"))
        return
    await _answer(hass, connection, msg, receipt_id)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/receipt/apply",
    vol.Required("receipt_id"): _id,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def receipt_apply(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        result = await hass.async_add_executor_job(partial(
            runtime.manager.apply_receipt, msg["receipt_id"]))
    except (LookupError, ValueError) as err:
        _send_domain_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    await _answer(hass, connection, msg, msg["receipt_id"],
                  applied=result["applied"], skipped=result["skipped"],
                  corrected_movements=result["corrected_movements"])


def async_register_receipt_commands(hass: HomeAssistant) -> None:
    for command in (receipt_submit, receipt_get, receipt_list, receipt_retry,
                    receipt_discard, receipt_line_match, receipt_apply):
        websocket_api.async_register_command(hass, command)
