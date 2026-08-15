"""Refresh a generated skill without discarding hand edits.

``check`` tells you a skill has drifted from its source and says to re-run ``forge`` —
but ``forge --force`` overwrites the file, so every hand edit made since goes with it.
That is the gap this closes: regenerate, and merge section by section.

The merge needs to distinguish *the generator changed this* from *a human changed this*,
and a two-way diff cannot. So ``forge`` records a manifest (``.skill-forge.json``, beside
``SKILL.md``) holding a hash of each section as generated. With it, the answer per section
is unambiguous:

* on disk == as generated  ->  untouched, take the regenerated version
* on disk != as generated  ->  hand-edited, **keep it** and say so
* only in the regenerated  ->  new, add it
* only on disk             ->  hand-written, keep it

Without a manifest — a skill forged before this existed — everything present is treated
as hand-edited. That is the safe direction to be wrong in: update then only *adds* what's
missing and never silently reverts prose someone wrote.

Stdlib only, and pure: :func:`merge` does no I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import parse_frontmatter, render_frontmatter

MANIFEST_NAME = ".skill-forge.json"
#: Bumped when the manifest layout changes, so a stale file is ignored rather than misread.
MANIFEST_VERSION = 1

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _digest(text: str) -> str:
    """Hash a section's meaning, not its incidental whitespace."""
    return hashlib.sha256("\n".join(text.split()).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Section:
    """One ``##``-level section: its heading line and everything under it."""

    title: str
    heading: str
    body: str

    @property
    def text(self) -> str:
        if not self.body:
            return self.heading + "\n"
        # Blank line after the heading — markdown convention, and what the generator
        # itself emits, so a merge doesn't reflow the parts it left alone.
        return f"{self.heading}\n\n{self.body}".rstrip() + "\n"

    @property
    def digest(self) -> str:
        return _digest(self.text)


@dataclass
class Document:
    """A parsed ``SKILL.md``: frontmatter text, a preamble, and its sections."""

    frontmatter: str
    preamble: str
    sections: list[Section] = field(default_factory=list)

    def by_title(self) -> dict[str, Section]:
        return {s.title: s for s in self.sections}


def parse(text: str) -> Document:
    """Split ``SKILL.md`` text into frontmatter, preamble, and top-level sections.

    Sections split on the shallowest heading level present at or below ``##``, so a
    document using ``#`` for its sections is handled the same as one using ``##``.
    """
    frontmatter = ""
    match = _FRONTMATTER.match(text)
    body = text
    if match:
        frontmatter = match.group(1)
        body = text[match.end() :]

    lines = body.splitlines()
    levels = [
        len(m.group(1)) for line in lines if (m := _HEADING.match(line)) and len(m.group(1)) >= 2
    ]
    split_level = min(levels) if levels else 2

    preamble_lines: list[str] = []
    sections: list[Section] = []
    current: tuple[str, str, list[str]] | None = None

    for line in lines:
        m = _HEADING.match(line)
        if m and len(m.group(1)) == split_level:
            if current is not None:
                sections.append(Section(current[0], current[1], "\n".join(current[2]).strip()))
            current = (m.group(2).strip(), line, [])
        elif current is None:
            preamble_lines.append(line)
        else:
            current[2].append(line)

    if current is not None:
        sections.append(Section(current[0], current[1], "\n".join(current[2]).strip()))

    return Document(frontmatter, "\n".join(preamble_lines).strip(), sections)


@dataclass
class Manifest:
    """Hashes of the content as last generated, so edits are detectable."""

    sections: dict[str, str] = field(default_factory=dict)
    description: str = ""
    preamble: str = ""

    @property
    def known(self) -> bool:
        """False when no manifest was found — treat everything as hand-edited."""
        return bool(self.sections or self.description or self.preamble)

    @classmethod
    def from_document(cls, doc: Document, description: str) -> Manifest:
        return cls(
            sections={s.title: s.digest for s in doc.sections},
            description=_digest(description),
            preamble=_digest(doc.preamble),
        )

    @classmethod
    def load(cls, skill_dir: str | Path) -> Manifest:
        path = Path(skill_dir) / MANIFEST_NAME
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()  # absent or unreadable: fall back to "everything is hand-edited"
        if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
            return cls()
        sections = data.get("sections")
        return cls(
            sections=dict(sections) if isinstance(sections, dict) else {},
            description=str(data.get("description") or ""),
            preamble=str(data.get("preamble") or ""),
        )

    def save(self, skill_dir: str | Path) -> Path:
        path = Path(skill_dir) / MANIFEST_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": MANIFEST_VERSION,
            "note": (
                "Written by skill-forge. Records what this skill looked like when it was "
                "generated, so `skill-forge update` can refresh the generated parts "
                "without discarding your edits. Commit it; delete it and update becomes "
                "additive only."
            ),
            "description": self.description,
            "preamble": self.preamble,
            "sections": dict(sorted(self.sections.items())),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path


@dataclass(frozen=True)
class MergeResult:
    """The merged text plus what happened to every part of it."""

    text: str
    refreshed: tuple[str, ...] = ()  # regenerated content taken
    kept: tuple[str, ...] = ()  # hand-edited, left alone
    added: tuple[str, ...] = ()  # new from the generator
    dropped: tuple[str, ...] = ()  # generator no longer emits it, and nobody edited it

    @property
    def changed_titles(self) -> tuple[str, ...]:
        return self.refreshed + self.added + self.dropped


def merge(existing: str, regenerated: str, manifest: Manifest) -> MergeResult:
    """Three-way merge ``regenerated`` into ``existing`` using ``manifest`` as the base.

    Section order follows the regenerated document, with hand-written sections appended
    in their original relative order — so a refresh reads like the generator's output
    rather than shuffling a human's structure around.
    """
    old, new = parse(existing), parse(regenerated)
    old_by_title, new_by_title = old.by_title(), new.by_title()

    refreshed: list[str] = []
    kept: list[str] = []
    added: list[str] = []
    dropped: list[str] = []
    merged: list[Section] = []

    for section in new.sections:
        previous = old_by_title.get(section.title)
        if previous is None:
            merged.append(section)
            added.append(section.title)
            continue
        base = manifest.sections.get(section.title)
        if manifest.known and base is not None and previous.digest == base:
            merged.append(section)  # untouched since generation
            if previous.digest != section.digest:
                refreshed.append(section.title)
        else:
            merged.append(previous)  # hand-edited (or unknown provenance): keep it
            if previous.digest != section.digest:
                kept.append(section.title)

    for section in old.sections:
        if section.title in new_by_title:
            continue
        base = manifest.sections.get(section.title)
        if manifest.known and base is not None and section.digest == base:
            dropped.append(section.title)  # generator stopped emitting it; nobody edited it
        else:
            merged.append(section)  # hand-written or hand-edited: it stays
            kept.append(section.title)

    # Frontmatter is edited as text rather than re-rendered from parsed fields: the flat
    # parser drops the nested `metadata` block, so a round-trip would silently lose the
    # version. `name` is the skill's identity and is never rewritten here; the
    # description is regenerated only when nobody has touched it.
    old_fields, _ = parse_frontmatter(f"---\n{old.frontmatter}\n---\n")
    new_fields, _ = parse_frontmatter(f"---\n{new.frontmatter}\n---\n")

    frontmatter = new.frontmatter
    if old_fields.get("name"):
        frontmatter = _replace_field(frontmatter, "name", old_fields["name"])

    old_description = old_fields.get("description", "")
    new_description = new_fields.get("description", "")
    edited = not (manifest.known and _digest(old_description) == manifest.description)
    if edited:
        if old_description and old_description != new_description:
            frontmatter = _replace_field(frontmatter, "description", old_description)
            kept.append("description")
    elif old_description != new_description:
        refreshed.append("description")

    preamble = new.preamble
    if old.preamble and not (manifest.known and _digest(old.preamble) == manifest.preamble):
        if old.preamble != new.preamble:
            preamble = old.preamble
            kept.append("(preamble)")
    elif old.preamble != new.preamble:
        refreshed.append("(preamble)")

    parts = [f"---\n{frontmatter}\n---", ""]
    if preamble:
        parts += [preamble, ""]
    for section in merged:
        parts += [section.text.rstrip(), ""]
    text = "\n".join(parts).rstrip() + "\n"

    return MergeResult(
        text=text,
        refreshed=tuple(refreshed),
        kept=tuple(kept),
        added=tuple(added),
        dropped=tuple(dropped),
    )


def _replace_field(frontmatter: str, key: str, value: str) -> str:
    """Rewrite one top-level ``key:`` line in a frontmatter block, in place.

    Editing the text rather than re-rendering the whole block keeps everything else
    byte-identical — including the nested ``metadata`` object the flat parser can't
    represent.
    """
    rendered = render_frontmatter({key: value}).splitlines()[1]  # strip the --- fences
    out: list[str] = []
    replaced = False
    for line in frontmatter.splitlines():
        if not replaced and line.startswith(f"{key}:") and not line.startswith(" "):
            out.append(rendered)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.insert(0, rendered)
    return "\n".join(out)


__all__ = [
    "MANIFEST_NAME",
    "MANIFEST_VERSION",
    "Document",
    "Manifest",
    "MergeResult",
    "Section",
    "merge",
    "parse",
]
