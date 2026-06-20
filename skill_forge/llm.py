"""Optional Claude refinement of a draft.

This module is never imported on the deterministic path. It lazily imports ``anthropic``
and fails closed: any problem with the model's *output* falls back to the deterministic
draft (never worse), while a missing extra, missing key, or transport error raises
:class:`LLMUnavailable` so the user gets an actionable message.
"""

from __future__ import annotations

import json
import os
import re

from .config import Settings
from .errors import LLMUnavailable
from .models import SkillDraft, SourceSignals
from .skill import render_skill
from .validate import lint_text

_SYSTEM = (
    "You sharpen Claude SKILL.md drafts. You are given extracted signals about a source "
    "and a deterministic first-draft skill. Improve only the prose: make the description "
    "say clearly WHEN to trigger (mention concrete user phrases and tasks) and tighten the "
    "body. Keep the description under 1024 characters. Do not invent capabilities that are "
    "not in the signals. Reply with ONLY a JSON object: "
    '{"description": "...", "body": "..."} and nothing else.'
)


def _build_user_prompt(draft: SkillDraft, signals: SourceSignals) -> str:
    facts = {
        "name": signals.name,
        "summary": signals.summary,
        "language": signals.language,
        "install": signals.install,
        "commands": [{"name": c.name, "help": c.help} for c in signals.commands],
        "api": signals.api,
        "keywords": signals.keywords,
    }
    return (
        "SIGNALS:\n"
        + json.dumps(facts, indent=2, ensure_ascii=False)
        + "\n\nCURRENT DESCRIPTION:\n"
        + draft.description
        + "\n\nCURRENT BODY:\n"
        + draft.body
    )


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def refine_with_llm(
    draft: SkillDraft, signals: SourceSignals, settings: Settings | None = None
) -> SkillDraft:
    """Refine ``draft`` with Claude, falling back to ``draft`` if the output is unusable."""
    settings = settings or Settings()
    try:
        import anthropic
    except ImportError as exc:
        raise LLMUnavailable(
            "the --llm option needs the anthropic extra: pip install 'skill-forge[anthropic]'"
        ) from exc

    api_key = os.environ.get(settings.anthropic_api_key_env)
    if not api_key:
        raise LLMUnavailable(
            f"set {settings.anthropic_api_key_env} in the environment to use --llm"
        )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=settings.model_id,
            max_tokens=2000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_user_prompt(draft, signals)}],
        )
    except Exception as exc:  # transport / auth / rate-limit — actionable, surface it
        raise LLMUnavailable(f"LLM refinement call failed: {exc}") from exc

    text = "".join(
        getattr(block, "text", "")
        for block in message.content
        if getattr(block, "type", "") == "text"
    )
    data = _extract_json(text)
    if not data:
        return draft

    candidate = SkillDraft(
        name=draft.name,
        description=(data.get("description") or draft.description).strip(),
        body=(data.get("body") or draft.body).strip() + "\n",
        version=draft.version,
        license=draft.license,
        signals=signals,
    )
    problems = lint_text(render_skill(candidate), dir_name=candidate.name)
    if any(p.severity == "error" for p in problems):
        return draft  # model produced something invalid — keep the deterministic draft
    return candidate
