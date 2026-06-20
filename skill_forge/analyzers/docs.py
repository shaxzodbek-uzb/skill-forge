"""Analyze a single documentation file (markdown / rst / txt)."""

from __future__ import annotations

from pathlib import Path

from ..models import SourceSignals
from .base import clean_section_titles, parse_markdown, read_text, tokenize_keywords


def analyze(path: str | Path) -> SourceSignals:
    file = Path(path)
    md = parse_markdown(read_text(file))

    name = md["title"] or file.stem
    # A sentence-like H1 makes a useless 50+ char skill name; fall back to the file stem.
    if name and len(name.split()) > 6:
        name = file.stem
    summary = md["summary"]
    headings = [h for level, h in md["headings"] if level == 2]
    cleaned = clean_section_titles(headings)
    notes = cleaned[:10] if len(cleaned) >= 2 else []
    usage = md["code_blocks"][:3]
    # Headings carry stronger trigger signal than prose; seed from them before the summary.
    keywords = tokenize_keywords(name, " ".join(cleaned), summary)

    return SourceSignals(
        name=name,
        summary=summary,
        kind="docs",
        usage=usage,
        keywords=keywords,
        notes=notes,
        source=str(file),
    )
