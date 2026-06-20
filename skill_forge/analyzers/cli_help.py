"""Build signals by capturing a CLI tool's ``--help`` output.

This is the *one* place skill-forge runs an external process, and it only happens when the
user explicitly passes ``--from-cli "<command>"``. The command is split with :func:`shlex.split`
(no shell), ``--help`` is appended, and the call is timeout-guarded. We never auto-detect
or auto-run anything.
"""

from __future__ import annotations

import re
import shlex
import subprocess

from ..errors import AnalyzerError
from ..models import Command, SourceSignals
from .base import tokenize_keywords

_USAGE_RE = re.compile(r"^\s*usage:", re.IGNORECASE)
_SECTION_RE = re.compile(r"^\s*(commands|subcommands|available commands)\b", re.IGNORECASE)
_ITEM_RE = re.compile(r"^\s{1,6}([a-z][\w-]*)\s{2,}(.+?)\s*$")
_CHOICES_RE = re.compile(r"\{([a-z][\w,-]+)\}")


def capture_cli_help(command: str, *, timeout: float = 10.0) -> SourceSignals:
    """Run ``<command> --help`` (no shell) and parse it into signals."""
    parts = shlex.split(command)
    if not parts:
        raise AnalyzerError("empty --from-cli command")
    if parts[-1].startswith("-"):
        raise AnalyzerError(
            "--from-cli expects a program name, optionally a subcommand — not a flag: "
            f"got {command!r}. Try `--from-cli \"{parts[0]}\"`."
        )
    try:
        proc = subprocess.run(  # noqa: S603 - args are a parsed list, shell=False
            [*parts, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AnalyzerError(f"command not found: {parts[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AnalyzerError(f"`{parts[0]} --help` timed out after {timeout}s") from exc

    text = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if not text.strip():
        raise AnalyzerError(f"`{parts[0]} --help` produced no output")

    name = parts[-1] if len(parts) > 1 else parts[0].rsplit("/", 1)[-1]
    summary, commands, notes = _parse_help(text)
    keywords = tokenize_keywords(name, summary, " ".join(c.name for c in commands))

    return SourceSignals(
        name=name,
        summary=summary,
        kind="cli",
        commands=commands,
        keywords=keywords,
        notes=notes,
        usage=[text.strip()] if not commands else [],
        source=f"`{command} --help`",
    )


def _parse_help(text: str) -> tuple[str, list[Command], list[str]]:
    lines = text.splitlines()
    summary = ""
    commands: dict[str, Command] = {}
    notes: list[str] = []
    in_commands = False

    for line in lines:
        if _USAGE_RE.match(line):
            in_commands = False
            for group in _CHOICES_RE.findall(line):
                for choice in group.split(","):
                    choice = choice.strip()
                    if choice:
                        commands.setdefault(choice, Command(name=choice))
            continue
        if _SECTION_RE.match(line):
            in_commands = True
            continue
        if in_commands:
            item = _ITEM_RE.match(line)
            if item:
                name, help_text = item.group(1), item.group(2).strip()
                commands.setdefault(name, Command(name=name, help=help_text))
            elif line.strip() == "":
                in_commands = False
            continue
        stripped = line.strip()
        if not summary and stripped and not stripped.startswith("-"):
            summary = stripped

    return summary, list(commands.values()), notes
