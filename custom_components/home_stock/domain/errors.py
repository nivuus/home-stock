"""Errors a person reads, carried as a translation key and placeholders.

The domain and application layers stay free of Home Assistant and of any
language: an error names WHAT went wrong (`translation_key`) and the values
the sentence needs (`placeholders`). The surfaces turn that into words:
the services raise Home Assistant's `ServiceValidationError` with the key,
which the frontend shows in the person's own language, and the websocket
commands send the key along with a sentence in Home Assistant's language
(`error_surface.py`). The sentences live in `translations/<lang>.json`, under
`exceptions`.

`str(error)` remains an English sentence for the log. Each class also derives
from the built-in type its call sites used to raise, so existing `except`
clauses keep catching exactly what they caught.
"""
from __future__ import annotations


class TranslatedError(Exception):
    """An error with a translation key; `code` is the websocket error code."""

    code = "invalid_value"

    def __init__(self, message: str, *, translation_key: str,
                 **placeholders: object) -> None:
        super().__init__(message)
        self.translation_key = translation_key
        self.placeholders = {name: str(value) for name, value in placeholders.items()}


class NotFoundError(TranslatedError, LookupError, ValueError):
    """Something named by id does not exist (or no longer does)."""

    code = "not_found"


class InvalidValueError(TranslatedError, ValueError):
    """A value that cannot be used as given."""

    code = "invalid_value"


class InvalidFieldError(TranslatedError, ValueError):
    """Two fields that do not go together."""

    code = "invalid_field"
