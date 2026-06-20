"""Assemble the markdown body of a generated skill from extracted signals.

The body uses imperative voice, follows the standard skill anatomy (title, when-to-use,
overview, then source-specific sections), and stays well under the 500-line guideline.
"""

from __future__ import annotations

import re

from .models import SourceSignals

_LANG_FENCE = {
    "Python": "python",
    "JavaScript": "javascript",
    "TypeScript": "typescript",
    "Shell": "bash",
}
_MAX_SNIPPETS = 3
_MAX_SNIPPET_LINES = 40


def _humanize(name: str) -> str:
    name = name.strip()
    # Keep names that already carry intentional casing or spaces.
    if " " in name or any(c.isupper() for c in name):
        return name
    words = re.split(r"[-_]+", name)
    return " ".join(w.capitalize() for w in words if w) or name


_SHELL_HINTS = (
    "$", "pip ", "npm ", "npx ", "uv ", "uvx ", "cd ", "git ", "curl ", "export ", "sudo "
)
_PY_HINTS = ("import ", "from ", "def ", "class ", "print(", "async ", "@")
_JS_HINTS = ("const ", "let ", "var ", "require(", "=>", "function ", "console.")


def _snippet_lang(snippet: str, signals: SourceSignals) -> str:
    """Best-effort fence language for one snippet, preferring its own shape over the
    project's dominant language (README install/usage blocks are usually shell)."""
    for raw in snippet.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(_SHELL_HINTS):
            return "bash"
        if line.startswith(_PY_HINTS):
            return "python"
        if line.startswith(_JS_HINTS) or line.endswith(";"):
            return "javascript"
        # A bare command invocation (words, no call/assignment) reads as shell.
        if " " in line and "(" not in line and "=" not in line.split("#", 1)[0]:
            return "bash"
        break
    return _LANG_FENCE.get(signals.language or "", "")


def _when_to_use_bullets(signals: SourceSignals) -> list[str]:
    """Derive concrete trigger bullets from the signals (commands, else API), plus a
    trigger-phrase line from keywords. Empty when there is nothing specific to say."""
    bullets: list[str] = []
    if signals.commands:
        for cmd in signals.commands[:8]:
            help_text = re.sub(r"\s+", " ", cmd.help or "").strip()
            tail = f" — {help_text}" if help_text else ""
            bullets.append(f"- When the user wants to run `{cmd.name}`{tail}.")
    elif signals.api:
        for symbol in signals.api[:8]:
            bullets.append(f"- When the user is working with `{symbol}`.")
    if signals.keywords:
        bullets.append(f"- Trigger phrases: {', '.join(signals.keywords[:8])}.")
    return bullets


def build_body(signals: SourceSignals) -> str:
    """Return the markdown body (no frontmatter) for ``signals``."""
    title = _humanize(signals.name)
    summary = (signals.summary or "").strip()
    out: list[str] = [f"# {title}", ""]

    out.append(summary if summary else f"Working with {title}.")
    out.append("")

    out.append("## When to use")
    out.append("")
    out.append(f"Reach for this skill when a task involves {title}.")
    out.append("")
    when = _when_to_use_bullets(signals)
    if when:
        out.extend(when)
        out.append("")

    overview: list[str] = []
    if signals.language:
        overview.append(f"- **Language:** {signals.language}")
    if signals.install:
        overview.append(f"- **Install:** `{signals.install}`")
    if signals.homepage:
        overview.append(f"- **Homepage:** {signals.homepage}")
    if overview:
        out.append("## Overview")
        out.append("")
        out.extend(overview)
        out.append("")

    if signals.commands:
        out.append("## Commands")
        out.append("")
        for cmd in signals.commands:
            help_text = re.sub(r"\s+", " ", cmd.help or "").strip()
            out.append(f"- `{cmd.name}`" + (f" — {help_text}" if help_text else ""))
        out.append("")

    if signals.api:
        out.append("## API")
        out.append("")
        for symbol in signals.api:
            out.append(f"- `{symbol}`")
        out.append("")

    if signals.usage:
        out.append("## Usage")
        out.append("")
        for snippet in signals.usage[:_MAX_SNIPPETS]:
            lines = snippet.strip("\n").splitlines()[:_MAX_SNIPPET_LINES]
            out.append(f"```{_snippet_lang(snippet, signals)}")
            out.extend(lines)
            out.append("```")
            out.append("")

    if signals.notes:
        out.append("## Related topics")
        out.append("")
        for note in signals.notes:
            clean_note = re.sub(r"[`*_]+", "", re.sub(r"\s+", " ", note)).strip()
            out.append(f"- {clean_note}")
        out.append("")

    source = signals.source or "the provided source"
    if not source.startswith("`"):
        source = f"`{source}`"
    out.append("---")
    out.append("")
    out.append(
        f"> Generated by skill-forge from {source}. Review and edit before publishing — "
        "a generated skill is a strong first draft, not a substitute for judgment."
    )
    out.append("")

    return "\n".join(out).rstrip() + "\n"
