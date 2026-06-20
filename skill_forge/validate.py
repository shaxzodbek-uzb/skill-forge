"""The bundled SKILL.md linter.

These are the rules a skill must satisfy to be discoverable and portable — the same
checks the standalone ``skillcheck`` enforces. ``skill-forge`` runs them on every draft
it generates (valid by construction) and exposes them via ``skill-forge lint`` so the
tool stands alone.

One intentional difference from the strictest reference linter: a missing ``version`` is
a *warning*, not an error, because the official skill schema requires only ``name`` and
``description``. Everything ``skill-forge`` generates includes a semver ``version``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import SourceNotFound
from .frontmatter import parse_frontmatter
from .slug import is_kebab_case

DESCRIPTION_MIN = 40
DESCRIPTION_MAX = 1024

_BLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")


@dataclass(frozen=True)
class Problem:
    """A single lint finding."""

    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass
class LintResult:
    """The findings for one skill."""

    name: str
    path: str | None
    problems: list[Problem]

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == "error"]

    @property
    def warnings(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def lint_text(text: str, *, dir_name: str | None = None) -> list[Problem]:
    """Validate a ``SKILL.md`` string and return the list of problems (empty == clean)."""
    if not _BLOCK_RE.match(text):
        return [
            Problem(
                "frontmatter",
                "missing or malformed YAML frontmatter "
                "(must open and close with --- on their own lines)",
            )
        ]

    fields, body = parse_frontmatter(text)
    problems: list[Problem] = []

    name = fields.get("name", "")
    if not name:
        problems.append(Problem("name", "frontmatter missing required field: name"))
    else:
        if not is_kebab_case(name):
            problems.append(
                Problem("name", f"name '{name}' is not kebab-case (lowercase, digits, hyphens)")
            )
        if dir_name is not None and name != dir_name:
            problems.append(Problem("name", f"name '{name}' does not match directory '{dir_name}'"))

    description = fields.get("description", "")
    if not description:
        problems.append(Problem("description", "frontmatter missing required field: description"))
    else:
        length = len(description)
        if length < DESCRIPTION_MIN:
            problems.append(
                Problem(
                    "description",
                    f"description is too short ({length} chars; aim for >= {DESCRIPTION_MIN}) "
                    "— it should say WHEN to use the skill",
                )
            )
        elif length > DESCRIPTION_MAX:
            problems.append(
                Problem(
                    "description",
                    f"description is too long ({length} chars; keep <= {DESCRIPTION_MAX} "
                    "to fit the discovery budget)",
                )
            )

    version = fields.get("version", "")
    if not version:
        problems.append(
            Problem("version", "frontmatter missing recommended field: version", severity="warning")
        )
    elif not _SEMVER_RE.match(version):
        problems.append(Problem("version", f"version '{version}' is not semver-like (e.g. 1.0.0)"))

    if body.strip() == "":
        problems.append(Problem("body", "body below the frontmatter is empty"))

    return problems


def lint_skill_file(path: str | Path) -> LintResult:
    """Lint a single ``SKILL.md`` file; the directory name is inferred from its parent."""
    p = Path(path)
    if not p.is_file():
        raise SourceNotFound(f"not a file: {p}")
    dir_name = p.parent.name
    problems = lint_text(p.read_text(encoding="utf-8"), dir_name=dir_name)
    return LintResult(name=dir_name, path=str(p), problems=problems)


def lint_path(path: str | Path) -> list[LintResult]:
    """Lint a ``SKILL.md`` file, a single skill directory, or a ``skills/`` root.

    Raises :class:`SourceNotFound` if no ``SKILL.md`` can be found.
    """
    p = Path(path)
    if p.is_file():
        return [lint_skill_file(p)]
    if p.is_dir():
        own = p / "SKILL.md"
        if own.is_file():
            return [lint_skill_file(own)]
        found = sorted(p.glob("*/SKILL.md"))
        if not found:
            raise SourceNotFound(f"no SKILL.md found under {p} or {p}/*/SKILL.md")
        return [lint_skill_file(f) for f in found]
    raise SourceNotFound(f"path does not exist: {p}")
