"""Exception types for skill-forge.

All errors derive from :class:`SkillForgeError` so callers (and the CLI) can catch the
whole family with one ``except`` and print a clean, traceback-free message.
"""

from __future__ import annotations


class SkillForgeError(Exception):
    """Base class for every error this package raises."""


class SourceNotFound(SkillForgeError):
    """The given source path or command does not exist or cannot be read."""


class AnalyzerError(SkillForgeError):
    """An analyzer could not extract usable signals from the source."""


class InvalidSkill(SkillForgeError):
    """A generated draft failed validation and must not be written."""


class LLMUnavailable(SkillForgeError):
    """``--llm`` was requested but the optional ``anthropic`` extra or API key is missing."""
