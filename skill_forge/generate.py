"""Orchestrate analysis → draft → validation.

``forge()`` is the one call most users need: point it at a source, get back a validated
:class:`SkillDraft`. The deterministic path imports no third-party package; ``--llm`` is
applied only when explicitly requested.
"""

from __future__ import annotations

from pathlib import Path

from .analyzers import analyze
from .config import Settings
from .describe import build_description
from .errors import InvalidSkill
from .models import SkillDraft, SourceSignals
from .skill import render_skill
from .slug import slugify
from .templates import build_body
from .validate import lint_text


def draft_from_signals(
    signals: SourceSignals, *, name: str | None = None, settings: Settings | None = None
) -> SkillDraft:
    """Build a deterministic draft from ``signals`` (no LLM, no validation)."""
    settings = settings or Settings()
    if name is not None:
        skill_name = name
    else:
        try:
            skill_name = slugify(signals.name)
        except ValueError as exc:
            raise InvalidSkill(
                f"could not derive a usable skill name from {signals.name!r}; pass name= explicitly"
            ) from exc
    return SkillDraft(
        name=skill_name,
        description=build_description(signals, settings=settings),
        body=build_body(signals),
        version=settings.default_version,
        signals=signals,
    )


def validate_draft(draft: SkillDraft) -> SkillDraft:
    """Return ``draft`` if it lints clean, else raise :class:`InvalidSkill`."""
    problems = lint_text(render_skill(draft), dir_name=draft.name)
    errors = [p for p in problems if p.severity == "error"]
    if errors:
        raise InvalidSkill(
            "generated skill failed validation: " + "; ".join(p.message for p in errors)
        )
    return draft


def forge_from_signals(
    signals: SourceSignals,
    *,
    name: str | None = None,
    llm: bool = False,
    settings: Settings | None = None,
) -> SkillDraft:
    """Draft from pre-extracted signals, optionally refine with the LLM, then validate."""
    settings = settings or Settings()
    draft = draft_from_signals(signals, name=name, settings=settings)
    if llm:
        from .llm import refine_with_llm

        draft = refine_with_llm(draft, signals, settings=settings)
    return validate_draft(draft)


def forge(
    source: str | Path,
    *,
    name: str | None = None,
    kind: str | None = None,
    llm: bool = False,
    settings: Settings | None = None,
) -> SkillDraft:
    """Analyze ``source`` and return a validated :class:`SkillDraft`."""
    signals = analyze(source, kind=kind)
    return forge_from_signals(signals, name=name, llm=llm, settings=settings)
