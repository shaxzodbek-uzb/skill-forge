"""Pure data structures passed between the analyzers, the draft builders, and the writer.

These are deliberately plain dataclasses with no behavior and no I/O — they are the
contract every other module agrees on.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Command:
    """A single CLI subcommand discovered in the source."""

    name: str
    help: str = ""


@dataclass
class SourceSignals:
    """Everything an analyzer extracts from a source, ready to be shaped into a skill.

    Analyzers fill in whatever they can; the draft builders treat every field as
    best-effort. ``name`` and ``summary`` carry the most weight (they drive the skill
    name and the description), the rest enrich the body and the trigger phrases.
    """

    name: str
    summary: str = ""
    kind: str = "generic"
    language: str | None = None
    install: str | None = None
    homepage: str | None = None
    commands: list[Command] = field(default_factory=list)
    api: list[str] = field(default_factory=list)
    usage: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class SkillDraft:
    """A complete skill ready to render and write.

    ``name`` is kebab-case and equals the output directory name; ``description`` already
    fits the discovery budget; ``body`` is the markdown below the frontmatter.
    """

    name: str
    description: str
    body: str
    version: str = "0.1.0"
    license: str | None = None
    signals: SourceSignals | None = None
