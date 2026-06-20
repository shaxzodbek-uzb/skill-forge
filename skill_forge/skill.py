"""Render a :class:`SkillDraft` to ``SKILL.md`` text and write it to disk."""

from __future__ import annotations

from pathlib import Path

from .errors import SkillForgeError
from .frontmatter import render_frontmatter
from .models import SkillDraft
from .slug import is_kebab_case


def render_skill(draft: SkillDraft) -> str:
    """Return the full ``SKILL.md`` text (frontmatter + body) for ``draft``."""
    fields = {
        "name": draft.name,
        "description": draft.description,
        "version": draft.version,
    }
    if draft.license:
        fields["license"] = draft.license
    return render_frontmatter(fields) + "\n\n" + draft.body.rstrip() + "\n"


def write_skill(draft: SkillDraft, outdir: str | Path, *, force: bool = False) -> Path:
    """Write ``draft`` to ``<outdir>/<name>/SKILL.md`` and return the path.

    Refuses to overwrite an existing ``SKILL.md`` unless ``force`` is set. The skill name
    is kebab-validated first, so the join can never escape ``outdir``.
    """
    if not is_kebab_case(draft.name):
        raise SkillForgeError(f"refusing to write skill with non-kebab name: {draft.name!r}")
    skill_dir = Path(outdir) / draft.name
    target = skill_dir / "SKILL.md"
    if target.exists() and not force:
        raise SkillForgeError(f"{target} already exists — pass force=True / --force to overwrite")
    skill_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(render_skill(draft), encoding="utf-8")
    return target
