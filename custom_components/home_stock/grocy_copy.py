"""Where a Grocy copy may live, and how it is opened.

Every import and the migration check read a COPY of grocy.db that the
procedure places under the configuration directory. Two rules, kept here
once for all of them:

- `resolve_grocy_copy` turns the relative name a caller gave (already checked
  by `validators.grocy_database_path`) into an absolute path, following links,
  and refuses anything that ends up outside the configuration directory.
- `open_grocy_copy` opens that file read-only through a properly encoded
  SQLite URI, so no character of the file name (`#`, `?`, `%`) can change
  which file is opened or drop the read-only mode.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class GrocyCopyOutsideConfig(ValueError):
    """The Grocy copy resolves to a file outside the configuration directory."""


def resolve_grocy_copy(config_dir: str, relative: str) -> str:
    """The absolute, link-free path of a Grocy copy under `config_dir`."""
    root = Path(config_dir).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise GrocyCopyOutsideConfig(
            "grocy database path must stay inside the configuration directory")
    return str(target)


def open_grocy_copy(path: str) -> sqlite3.Connection:
    """Open a Grocy copy read-only. Grocy is never written to."""
    # Path.as_uri() percent-encodes every reserved character of the name;
    # SQLite decodes them back, so the query string is ours alone.
    uri = f"{Path(path).absolute().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn
