"""skill-forge — turn a codebase, package, or doc into a valid Claude SKILL.md.

The deterministic path (analyze → draft → validate) is offline and dependency-free; the
optional ``--llm`` refinement is the only thing that needs the ``anthropic`` extra.
"""

from __future__ import annotations

from .analyzers import analyze, detect
from .config import Settings
from .describe import build_description
from .errors import (
    AnalyzerError,
    InvalidSkill,
    LLMUnavailable,
    SkillForgeError,
    SourceNotFound,
)
from .generate import draft_from_signals, forge
from .llm import refine_with_llm
from .models import Command, SkillDraft, SourceSignals
from .skill import render_skill, write_skill
from .slug import is_kebab_case, slugify
from .templates import build_body
from .validate import LintResult, Problem, lint_path, lint_skill_file, lint_text

__version__ = "0.1.0"

__all__ = [
    "forge",
    "draft_from_signals",
    "SkillDraft",
    "SourceSignals",
    "Command",
    "Settings",
    "render_skill",
    "write_skill",
    "analyze",
    "detect",
    "build_description",
    "build_body",
    "lint_text",
    "lint_skill_file",
    "lint_path",
    "LintResult",
    "Problem",
    "slugify",
    "is_kebab_case",
    "refine_with_llm",
    "SkillForgeError",
    "SourceNotFound",
    "AnalyzerError",
    "InvalidSkill",
    "LLMUnavailable",
    "__version__",
]
