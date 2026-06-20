"""Fallback analyzer for any directory: name + README + language histogram."""

from __future__ import annotations

from pathlib import Path

from ..models import SourceSignals
from .base import (
    clean_section_titles,
    find_readme,
    guess_language,
    parse_markdown,
    read_text,
    tokenize_keywords,
)


def analyze(path: str | Path) -> SourceSignals:
    directory = Path(path)
    name = directory.name
    summary = ""
    usage: list[str] = []
    notes: list[str] = []

    readme = find_readme(directory)
    if readme is not None:
        md = parse_markdown(read_text(readme))
        if md["title"]:
            name = md["title"]
        summary = md["summary"]
        usage = md["code_blocks"][:2]
        cleaned = clean_section_titles([h for level, h in md["headings"] if level == 2])
        notes = cleaned[:8] if len(cleaned) >= 2 else []

    language = guess_language(directory)
    keywords = tokenize_keywords(name, summary, language or "")

    return SourceSignals(
        name=name,
        summary=summary,
        kind="generic",
        language=language,
        usage=usage,
        keywords=keywords,
        notes=notes,
        source=str(directory),
    )
