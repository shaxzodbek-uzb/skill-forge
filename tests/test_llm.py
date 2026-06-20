"""The optional LLM path must fail with an actionable error when unavailable, and the
deterministic path must never need it."""

from __future__ import annotations

import pytest

from skill_forge import (
    LLMUnavailable,
    SkillDraft,
    SourceSignals,
    forge,
    refine_with_llm,
)
from skill_forge.config import Settings


def test_refine_without_extra_or_key_raises(monkeypatch):
    # Point at an env var guaranteed to be absent so both "no anthropic" and
    # "no key" branches surface the same actionable error type.
    monkeypatch.delenv("SF_TEST_MISSING_KEY", raising=False)
    settings = Settings(anthropic_api_key_env="SF_TEST_MISSING_KEY")
    draft = SkillDraft(name="x", description="d" * 60, body="body")
    with pytest.raises(LLMUnavailable):
        refine_with_llm(draft, SourceSignals(name="x"), settings=settings)


def test_deterministic_forge_needs_no_anthropic(python_project):
    # forge() without llm=True must succeed even if anthropic is not installed.
    draft = forge(python_project)
    assert draft.description and draft.body
