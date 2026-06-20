"""Read and write the flat YAML frontmatter block of a ``SKILL.md``.

Skills use flat ``key: value`` scalar frontmatter only. We render and parse it with the
standard library so the package keeps zero runtime dependencies, and we keep the parser
byte-compatible with the reference linter (open and close with ``---`` on their own
lines, flat scalars, one layer of matching quotes stripped).
"""

from __future__ import annotations

import re

_BLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_FIELD_RE = re.compile(r"^([A-Za-z0-9_-]+):\s?(.*)$")
# Characters that make a bare scalar ambiguous to a real YAML parser.
_NEEDS_QUOTE_START = set("!&*[]{}#|>@%\"'?,-")
# A bare scalar a YAML parser would coerce to a non-string (number / bool / null).
_YAML_NUMBER_RE = re.compile(r"^[-+]?(\.\d+|\d+\.?\d*)([eE][-+]?\d+)?$")
_YAML_TYPED_WORDS = frozenset(
    {"true", "false", "yes", "no", "on", "off", "y", "n", "null", "none", "~"}
)


def _needs_quote(value: str) -> bool:
    if value == "":
        return True
    if value != value.strip():
        return True
    if ":" in value or "#" in value:
        return True
    return value[0] in _NEEDS_QUOTE_START


def _is_yaml_typed(value: str) -> bool:
    """True if a bare scalar would parse as a number, bool, or null (not a string)."""
    return value.lower() in _YAML_TYPED_WORDS or bool(_YAML_NUMBER_RE.match(value))


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _scalar(value: str) -> str:
    return _quote(value) if _needs_quote(value) else value


def _metadata_scalar(value: str) -> str:
    """Render a ``metadata`` value, which the spec defines as a string.

    A value a YAML parser would otherwise read as a number/bool/null (e.g. a
    ``1.0`` version) is quoted so it stays a string and passes string-map linters.
    """
    return _quote(value) if _needs_quote(value) or _is_yaml_typed(value) else value


def render_frontmatter(fields: dict[str, object]) -> str:
    """Render ``key: value`` frontmatter between ``---`` lines, preserving order.

    Most values are flat scalars. A value that is a ``dict`` is rendered as a one-level
    nested block (used for the spec's ``metadata`` object, e.g. ``metadata: {version}``).
    ``None`` and empty values (and empty nested dicts) are skipped. A scalar is
    double-quoted when it would otherwise confuse a YAML parser (contains a colon, hash,
    leading indicator character, or surrounding whitespace).
    """
    lines = ["---"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        if isinstance(value, dict):
            nested = {k: str(v) for k, v in value.items() if v is not None and v != ""}
            if not nested:
                continue
            lines.append(f"{key}:")
            for sub_key, sub_value in nested.items():
                lines.append(f"  {sub_key}: {_metadata_scalar(sub_value)}")
            continue
        lines.append(f"{key}: {_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split ``text`` into ``(frontmatter dict, body)``.

    Returns ``({}, text)`` when there is no well-formed leading frontmatter block.
    """
    match = _BLOCK_RE.match(text)
    if not match:
        return {}, text
    raw, body = match.group(1), match.group(2)
    fields: dict[str, str] = {}
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        field_match = _FIELD_RE.match(line)
        if not field_match:
            continue
        key = field_match.group(1)
        value = field_match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote = value[0]
            value = value[1:-1]
            if quote == '"':
                # Exact inverse of _quote(): unescape quotes, then backslashes.
                value = value.replace('\\"', '"').replace("\\\\", "\\")
        fields[key] = value
    return fields, body
