"""Source detection and analyzer dispatch.

``detect()`` picks an analyzer kind from a path; ``analyze()`` runs it. The CLI-help
capture lives in :mod:`cli_help` and is intentionally *not* wired into detection — it only
runs on the explicit ``--from-cli`` flag.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import AnalyzerError, SourceNotFound
from ..models import SourceSignals
from ..slug import slugify
from . import docs, generic, node, python

_DOC_SUFFIXES = {".md", ".markdown", ".rst", ".txt"}

_ANALYZERS = {
    "python": python.analyze,
    "node": node.analyze,
    "docs": docs.analyze,
    "generic": generic.analyze,
}


def detect(source: str | Path) -> str:
    """Return the analyzer kind for ``source`` (``python|node|docs|generic``)."""
    p = Path(source)
    if not p.exists():
        raise SourceNotFound(f"source does not exist: {p}")
    if p.is_file():
        if p.suffix == ".py":
            return "python"
        if p.suffix.lower() in _DOC_SUFFIXES:
            return "docs"
        return "docs"
    if (p / "package.json").is_file():
        return "node"
    if any((p / m).is_file() for m in ("pyproject.toml", "setup.py", "setup.cfg")):
        return "python"
    if list(p.glob("*.py")) or list(p.glob("*/*.py")):
        return "python"
    return "generic"


def analyze(source: str | Path, *, kind: str | None = None) -> SourceSignals:
    """Dispatch to the matching analyzer and return its signals."""
    p = Path(source)
    if not p.exists():
        raise SourceNotFound(f"source does not exist: {p}")
    chosen = kind or detect(p)
    func = _ANALYZERS.get(chosen)
    if func is None:
        raise AnalyzerError(f"unknown analyzer kind: {chosen!r}")
    signals = func(p)
    if not signals.name or not signals.name.strip():
        raise AnalyzerError(f"could not determine a name from {p}")
    try:
        slugify(signals.name)
    except ValueError as exc:
        raise AnalyzerError(
            f"could not derive a usable skill name from {p} (name {signals.name!r}); "
            "pass --name to set one explicitly"
        ) from exc
    return signals
