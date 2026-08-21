"""Recipe and article pictures: three families, only one of which dies.

Pure, apart from one file write isolated at the end of the module. No hass,
no network, no SQLite — and no HTTP view either.

**The decision, taken once for both.** Lot 0 planned "an HTTP view for article
pictures"; it was never written, and it is now abandoned. Since lot 4 the
component serves no HTTP view at all — uploading a receipt goes through
`/api/media_source/local_source/upload`, which Home Assistant provides — and
lot 5 settled "under media/, never under www/". Recipe and article pictures
follow the same rule, and the panel resolves them with the NATIVE
`media_source/resolve_media` command.

Ruled out, and they stay ruled out: `config/www/` (served WITHOUT
authentication to the whole house network); an HTTP view of our own (writing,
authenticating and testing what HA already gives); data-URIs in the database
(3.65 MB of base64 re-read on every open); leaving the Grocy URLs in place —
that is the whole problem.

**Who copies what.** The Home Assistant container only mounts `config/` and
`media/`: it does NOT see `/opt/nivuus/Grocy/config/data/storage/`. The 55
`recipepictures` and the 33 `productpictures` are copied BY THE OWNER, gesture
3 of the shutdown procedure. This module only decodes the 62 data-URIs — that
data is in the database it already reads — and rewrites the URLs.

The 112 Unsplash references stay where they are. The criterion is "does it die
with the container?", and Unsplash does not depend on it. **No code here ever
fetches them, and no test does either.**
"""
from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path
from typing import Iterable, Mapping, NamedTuple

GROCY_HOST = "grocy.allanic.me"
DATA_URI_PREFIX = "data:image"

_IMG_SRC = re.compile(r"<img[^>]*?\ssrc\s*=\s*([\"'])(.*?)\1", re.DOTALL)


class PictureNameError(ValueError):
    """A Grocy picture name that does not decode, or an empty payload.

    Both are anomalies, not shrugs: a name that does not decode means the URL
    is not what we think it is, and a zero-byte file would pass every database
    check and display nothing.
    """


class Reference(NamedTuple):
    """One `src` found in a description."""

    family: str                 # "inline" | "grocy" | "external"
    src: str
    filename: str | None        # renseigné pour la famille "grocy"


def nom_de_fichier(url: str) -> str:
    """The file name behind a Grocy picture URL.

    Grocy base64-encodes the name in the path, with no API key. The decoding
    is done by the code, never copied by hand into a fixture.
    """
    segment = url.rstrip("/").rsplit("/", 1)[-1]
    try:
        decoded = base64.b64decode(segment, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as err:
        raise PictureNameError(
            f"nom d'image Grocy indécodable : {segment!r}") from err
    if not decoded:
        raise PictureNameError(f"nom d'image Grocy vide : {segment!r}")
    return decoded


def nom_inline(recipe_id: int, rank: int) -> str:
    """Deterministic, so a replay rewrites the SAME file instead of piling up
    a new one per run — §8.8's idempotence, applied to the file system."""
    return f"recette-{recipe_id}-inline-{rank}.jpg"


def media_id(dossier: str, filename: str) -> str:
    """The media_source identifier of a file under media/.

    Never a `/local/` path: lot 5 settled that www/ is served WITHOUT
    authentication to the whole network.
    """
    return f"media-source://media_source/local/{dossier}/{filename}"


def references(description: str | None) -> list[Reference]:
    """Every `<img src>` of a description, sorted into its family."""
    if not description:
        return []
    trouvees: list[Reference] = []
    for _, src in _IMG_SRC.findall(description):
        if src.startswith(DATA_URI_PREFIX):
            trouvees.append(Reference("inline", src, None))
        elif GROCY_HOST in src:
            trouvees.append(Reference("grocy", src, nom_de_fichier(src)))
        else:
            trouvees.append(Reference("external", src, None))
    return trouvees


def reecrire(description: str, mapping: Mapping[str, str]) -> str:
    """Replace the `src` values that were brought home. Unsplash is untouched.

    Substitution is driven by the mapping, not by a pattern: what is not in it
    stays exactly as it was, byte for byte.
    """
    sortie = description
    for ancien, nouveau in mapping.items():
        sortie = sortie.replace(ancien, nouveau)
    return sortie


def reconcilier(references: Iterable[str],
                fichiers: Iterable[str]) -> tuple[set[str], set[str]]:
    """(missing, orphans). The missing one blocks; the orphan just says so."""
    attendus = set(references)
    presents = set(fichiers)
    return attendus - presents, presents - attendus


def ecrire_inline(payload: str, chemin: str) -> int:
    """Decode a data-URI and write it. Returns the number of bytes written.

    The ONLY function of the `grocy/` package that touches the file system.
    It takes an already-resolved path and NEVER builds one itself — that is
    `validators.picture_dir`'s job.
    """
    _, _, encoded = payload.partition("base64,")
    encoded = encoded.strip()
    if not encoded:
        raise PictureNameError(f"charge utile vide pour {chemin}")
    try:
        octets = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as err:
        raise PictureNameError(f"charge utile indécodable pour {chemin}") from err
    if not octets:
        raise PictureNameError(f"charge utile vide pour {chemin}")
    Path(chemin).write_bytes(octets)
    return len(octets)
