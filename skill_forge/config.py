"""Runtime settings.

A plain dataclass read from the environment — no pydantic, no dependencies. The core
needs no configuration at all; these knobs exist mainly for the optional ``--llm`` path
and for tuning output defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Tunable defaults. Override via ``SKILL_FORGE_*`` environment variables."""

    anthropic_api_key_env: str = "ANTHROPIC_API_KEY"
    model_id: str = "claude-haiku-4-5"
    default_outdir: str = ".claude/skills"
    default_version: str = "0.1.0"
    max_description: int = 1024
    min_description: int = 40

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings, applying ``SKILL_FORGE_*`` overrides where present."""
        s = cls()
        s.model_id = os.environ.get("SKILL_FORGE_MODEL_ID", s.model_id)
        s.default_outdir = os.environ.get("SKILL_FORGE_OUTDIR", s.default_outdir)
        s.default_version = os.environ.get("SKILL_FORGE_VERSION", s.default_version)
        return s
