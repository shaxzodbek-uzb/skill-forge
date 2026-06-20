"""Analyze a Node.js package from ``package.json`` (+ README)."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Command, SourceSignals
from .base import clean_section_titles, find_readme, parse_markdown, read_text, tokenize_keywords


def analyze(path: str | Path) -> SourceSignals:
    directory = Path(path)
    pkg_file = directory / "package.json"
    data: dict = {}
    if pkg_file.is_file():
        try:
            data = json.loads(read_text(pkg_file)) or {}
        except json.JSONDecodeError:
            data = {}

    name = data.get("name") or directory.name
    summary = data.get("description", "")
    keywords_meta = data.get("keywords", []) or []
    homepage = data.get("homepage")

    commands = _bin_commands(data.get("bin"), name)
    is_ts = (directory / "tsconfig.json").is_file() or bool(data.get("types"))
    language = "TypeScript" if is_ts else "JavaScript"

    usage: list[str] = []
    notes: list[str] = []
    readme = find_readme(directory)
    if readme is not None:
        md = parse_markdown(read_text(readme))
        if not summary:
            summary = md["summary"]
        if not name:
            name = md["title"]
        usage = md["code_blocks"][:3]
        cleaned = clean_section_titles([h for level, h in md["headings"] if level == 2])
        notes = cleaned[:8] if len(cleaned) >= 2 else []

    install = f"npm install {name}" if name else None
    keywords = tokenize_keywords(
        name,
        " ".join(str(k) for k in keywords_meta),
        " ".join(c.name for c in commands),
        summary,
    )

    return SourceSignals(
        name=name,
        summary=summary,
        kind="node",
        language=language,
        install=install,
        homepage=homepage if isinstance(homepage, str) else None,
        commands=commands,
        usage=usage,
        keywords=keywords,
        notes=notes,
        source=str(directory),
    )


def _bin_commands(bin_field: object, pkg_name: str) -> list[Command]:
    if isinstance(bin_field, str):
        short = pkg_name.split("/")[-1] if pkg_name else pkg_name
        return [Command(name=short)] if short else []
    if isinstance(bin_field, dict):
        return [Command(name=str(k)) for k in bin_field]
    return []
