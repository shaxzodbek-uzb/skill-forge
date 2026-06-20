"""Kebab-case helpers.

The skill ``name`` and its directory name must be identical kebab-case strings for the
skill to be discoverable, so slugging is a correctness concern, not a cosmetic one.
"""

from __future__ import annotations

import re
import unicodedata

_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Split camelCase / PascalCase boundaries before lowercasing.
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def is_kebab_case(name: str) -> bool:
    """True iff ``name`` is lowercase alphanumerics joined by single hyphens."""
    return bool(_KEBAB_RE.match(name))


def slugify(text: str) -> str:
    """Turn an arbitrary source name into a kebab-case slug.

    Drops a leading package scope (``@org/pkg`` -> ``pkg``), splits camelCase, transliterates
    non-ASCII to ASCII, lowercases, and joins the remaining word characters with single
    hyphens. Raises ``ValueError`` if nothing usable remains.
    """
    raw = text.strip()
    # Drop an npm-style scope: "@scope/name" -> "name".
    if raw.startswith("@") and "/" in raw:
        raw = raw.split("/", 1)[1]
    # Split camelCase so "myCoolTool" -> "my Cool Tool".
    raw = _CAMEL_RE.sub(" ", raw)
    # Transliterate accents to ASCII (é -> e); drop anything that does not survive.
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw = raw.lower()
    parts = re.findall(r"[a-z0-9]+", raw)
    if not parts:
        raise ValueError(f"cannot derive a kebab-case slug from {text!r}")
    return "-".join(parts)
