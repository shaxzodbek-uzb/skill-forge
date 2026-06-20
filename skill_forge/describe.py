"""Build the skill ``description`` — the single most important field.

The description is the *only* thing an agent reads when deciding whether to load a skill,
so it must say **when** to trigger, not just what the skill is. We compose it
deterministically from the extracted signals and keep it inside the discovery budget
(40–1024 chars). The phrasing is deliberately a little "pushy" because skills are known to
under-trigger when their descriptions are merely descriptive.
"""

from __future__ import annotations

import re

from .config import Settings
from .models import SourceSignals

_WS_RE = re.compile(r"\s+")
_MD_MARKUP_RE = re.compile(r"[`*_]+")


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _plain(text: str) -> str:
    """Strip markdown markup and a dangling connective so the description reads as prose.

    Only used for the description text — ``signals.summary`` stays untouched for the body.
    """
    cleaned = _MD_MARKUP_RE.sub("", text or "")
    cleaned = re.sub(r"^#+\s*", "", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned.rstrip(" .,;:-—")


def _dedupe(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        key = t.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(t.strip())
    return out


def _clamp(text: str, maximum: int) -> str:
    """Trim ``text`` to at most ``maximum`` chars on a sentence then word boundary."""
    if len(text) <= maximum:
        return text
    window = text[:maximum]
    # Prefer to end on a complete sentence.
    last_dot = window.rfind(". ")
    if last_dot >= maximum // 2:
        return window[: last_dot + 1].strip()
    # Otherwise cut on a word boundary — never mid-word.
    last_space = window.rfind(" ")
    if last_space > 0:
        window = window[:last_space]
    return window.rstrip(" ,;:-").strip()


def build_description(signals: SourceSignals, *, settings: Settings | None = None) -> str:
    """Compose a trigger-oriented description for ``signals``, clamped to the budget."""
    settings = settings or Settings()
    name = _plain(signals.name) or "this tool"
    summary = _plain(signals.summary)

    sentences: list[str] = []

    opener = f"Use this skill when working with {name}"
    if summary:
        opener += f" — {summary}"
    sentences.append(opener + ".")

    cmd_names = [c.name for c in signals.commands if c.name]
    if cmd_names:
        shown = ", ".join(cmd_names[:8])
        sentences.append(f"It covers commands such as {shown}.")
    elif signals.api:
        shown = ", ".join(signals.api[:8])
        sentences.append(f"It exposes {shown}.")

    # The name already appears in the opener and tail; keep it out of the mention list
    # so it is not repeated verbatim (and Title-Cased) a third time.
    triggers = _dedupe([*signals.keywords, *cmd_names])
    if triggers:
        shown = ", ".join(triggers[:10])
        sentences.append(
            f"Use it whenever the user mentions {shown}, "
            f"or asks to generate, configure, debug, or work with {name}."
        )

    description = " ".join(sentences)
    description = _clamp(description, settings.max_description)

    if len(description) < settings.min_description:
        pad = f" Applies to {name}-related tasks and questions."
        description = _clamp((description + pad).strip(), settings.max_description)

    return description
