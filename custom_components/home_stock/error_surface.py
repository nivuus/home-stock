"""What each surface makes of an error: translated by key where it can be.

A `domain.errors.TranslatedError` carries a key and placeholders; the
sentences are in `translations/<lang>.json` under `exceptions`.

- Services raise `ServiceValidationError` with the key: Home Assistant's
  frontend shows it in the person's own language, and `str()` gives the
  English sentence for the log, as Home Assistant does for its own errors.
- Websocket commands send the key and placeholders too, so a client that
  localises can, and a sentence in Home Assistant's configured language for
  the panel, which shows the message as it comes. The server does not know
  the language of the person behind a websocket connection.

Any other exception keeps the older path (`messages.french_error`), whose
English-to-French table is what remains to be converted.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.translation import (
    async_get_cached_translations,
    async_get_translations,
)

from .const import DOMAIN
from .domain.errors import TranslatedError
from .messages import french_error

# Home Assistant's own language for exception text when none matches.
_FALLBACK_LANGUAGE = "en"


async def _async_load(hass: HomeAssistant) -> None:
    for language in {hass.config.language, _FALLBACK_LANGUAGE}:
        await async_get_translations(hass, language, "exceptions", {DOMAIN})


async def async_load_error_translations(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cache the sentences of the instance's language and the English fallback,
    and again whenever the instance's language changes."""
    await _async_load(hass)

    async def _reload(event: Event) -> None:
        if "language" in event.data:
            await _async_load(hass)

    entry.async_on_unload(hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _reload))


@callback
def localized_message(hass: HomeAssistant, err: TranslatedError) -> str:
    """The sentence in Home Assistant's language, else in English."""
    key = f"component.{DOMAIN}.exceptions.{err.translation_key}.message"
    for language in (hass.config.language, _FALLBACK_LANGUAGE):
        cached = async_get_cached_translations(hass, language, "exceptions", DOMAIN)
        if template := cached.get(key):
            return template.format(**err.placeholders)
    # Translations not loaded at all (the entry is not set up): the code's
    # own English sentence is still exact.
    return str(err)


def service_error(err: TranslatedError) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN, translation_key=err.translation_key,
        translation_placeholders=err.placeholders)


@callback
def send_domain_error(connection: Any, msg_id: int, err: Exception) -> None:
    """Answer a websocket command with the error, translated when it can be."""
    if isinstance(err, TranslatedError):
        connection.send_error(
            msg_id, err.code, localized_message(connection.hass, err),
            translation_key=err.translation_key, translation_domain=DOMAIN,
            translation_placeholders=err.placeholders)
        return
    connection.send_error(msg_id, *french_error(err))
