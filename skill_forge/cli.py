"""The ``skill-forge`` command-line interface (argparse, stdlib only)."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

from . import __version__
from .analyzers import analyze
from .analyzers.cli_help import capture_cli_help
from .config import Settings
from .errors import SkillForgeError, SourceNotFound
from .generate import draft_from_signals, forge_from_signals
from .models import SourceSignals
from .skill import render_skill, write_skill
from .update import Manifest, merge, parse
from .validate import lint_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-forge",
        description="Generate a valid Claude SKILL.md from a codebase, package, or doc.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    forge_p = sub.add_parser("forge", help="generate and write a skill")
    forge_p.add_argument("source", nargs="?", help="path to a directory, package, or doc")
    forge_p.add_argument("-o", "--outdir", default=None, help="output dir (default .claude/skills)")
    forge_p.add_argument("--name", default=None, help="override the skill name (kebab-case)")
    forge_p.add_argument(
        "--kind", default=None, choices=["python", "node", "docs", "generic"], help="force analyzer"
    )
    forge_p.add_argument(
        "--from-cli", default=None, metavar="CMD", help='capture a CLI tool\'s --help'
    )
    forge_p.add_argument("--llm", action="store_true", help="refine prose with Claude")
    forge_p.add_argument("--stdout", action="store_true", help="print the skill, do not write")
    forge_p.add_argument("--force", action="store_true", help="overwrite an existing SKILL.md")
    forge_p.add_argument("--version-str", default=None, help="version for the generated skill")

    lint_p = sub.add_parser("lint", help="validate SKILL.md files")
    lint_p.add_argument("path", help="a SKILL.md, a skill dir, or a skills/ root")

    check_p = sub.add_parser("check", help="fail if the existing skill drifted from the source")
    check_p.add_argument("source", help="path to the source the skill was generated from")
    check_p.add_argument("-o", "--outdir", default=None, help="where the skill lives")
    check_p.add_argument("--name", default=None, help="skill name (defaults to the source slug)")
    check_p.add_argument(
        "--kind", default=None, choices=["python", "node", "docs", "generic"], help="force analyzer"
    )

    update_p = sub.add_parser(
        "update", help="regenerate a skill from its source, keeping your edits"
    )
    update_p.add_argument("source", help="path to the source the skill was generated from")
    update_p.add_argument("-o", "--outdir", default=None, help="where the skill lives")
    update_p.add_argument("--name", default=None, help="skill name (defaults to the source slug)")
    update_p.add_argument(
        "--kind", default=None, choices=["python", "node", "docs", "generic"], help="force analyzer"
    )
    update_p.add_argument(
        "--diff", action="store_true", help="print the merge as a diff and write nothing"
    )

    sub.add_parser("version", help="print the skill-forge version")
    return parser


def _signals_for(args, settings: Settings) -> SourceSignals:
    if args.from_cli:
        return capture_cli_help(args.from_cli)
    if not args.source:
        raise SkillForgeError("provide a source path or use --from-cli")
    return analyze(args.source, kind=args.kind)


def _cmd_forge(args) -> int:
    settings = Settings.from_env()
    if args.version_str:
        settings.default_version = args.version_str
    signals = _signals_for(args, settings)
    draft = forge_from_signals(signals, name=args.name, llm=args.llm, settings=settings)

    if args.stdout:
        sys.stdout.write(render_skill(draft))
        return 0

    outdir = args.outdir or settings.default_outdir
    path = write_skill(draft, outdir, force=args.force)
    # Record what was generated so `update` can later tell a generator change from a
    # hand edit. Without it, update can only ever add.
    Manifest.from_document(parse(render_skill(draft)), draft.description).save(path.parent)
    problems = lint_path(path)[0]
    verdict = "valid" if problems.ok else f"{len(problems.errors)} error(s)"
    print(f"✓ wrote {path}  ({verdict}, description {len(draft.description)} chars)")
    for p in problems.warnings:
        print(f"  ! {p.field}: {p.message}")
    return 0


def _cmd_lint(args) -> int:
    results = lint_path(args.path)
    failures = 0
    for result in results:
        if result.ok:
            extra = f"  ({len(result.warnings)} warning(s))" if result.warnings else ""
            print(f"✓ {result.name}{extra}")
        else:
            failures += 1
            print(f"✗ {result.name}")
        for p in result.problems:
            mark = "-" if p.severity == "error" else "!"
            print(f"  {mark} {p.field}: {p.message}")
    print()
    if failures:
        print(f"✗ {failures} of {len(results)} skill(s) have errors")
        return 1
    print(f"✓ all {len(results)} skill(s) valid")
    return 0


def _cmd_check(args) -> int:
    settings = Settings.from_env()
    signals = analyze(args.source, kind=args.kind)
    draft = draft_from_signals(signals, name=args.name, settings=settings)
    rendered = render_skill(draft)

    outdir = args.outdir or settings.default_outdir
    target = Path(outdir) / draft.name / "SKILL.md"
    if not target.is_file():
        raise SourceNotFound(f"no existing skill to check at {target}")

    existing = target.read_text(encoding="utf-8")
    if existing == rendered:
        print(f"✓ {target} is in sync with {args.source}")
        return 0

    diff = difflib.unified_diff(
        existing.splitlines(keepends=True),
        rendered.splitlines(keepends=True),
        fromfile=f"{target} (on disk)",
        tofile=f"{target} (regenerated)",
    )
    sys.stdout.writelines(diff)
    print(f"\n✗ {target} has drifted from {args.source} — run `skill-forge update {args.source}`")
    return 1


def _cmd_update(args) -> int:
    settings = Settings.from_env()
    signals = analyze(args.source, kind=args.kind)
    draft = draft_from_signals(signals, name=args.name, settings=settings)
    regenerated = render_skill(draft)

    outdir = args.outdir or settings.default_outdir
    skill_dir = Path(outdir) / draft.name
    target = skill_dir / "SKILL.md"
    if not target.is_file():
        raise SourceNotFound(
            f"no existing skill at {target} — create one first with `skill-forge forge`"
        )

    existing = target.read_text(encoding="utf-8")
    manifest = Manifest.load(skill_dir)
    result = merge(existing, regenerated, manifest)

    if args.diff:
        sys.stdout.writelines(
            difflib.unified_diff(
                existing.splitlines(keepends=True),
                result.text.splitlines(keepends=True),
                fromfile=f"{target} (on disk)",
                tofile=f"{target} (updated)",
            )
        )

    if result.text == existing:
        print(f"✓ {target} is already up to date with {args.source}")
        if not manifest.known:
            print("  ! no .skill-forge.json — update can only add, not refresh")
        return 0

    if not args.diff:
        target.write_text(result.text, encoding="utf-8")
        # Re-baseline against the freshly generated content, not the merged file: the
        # kept sections are still hand-edited and must stay detectable as such.
        merged_manifest = Manifest.from_document(parse(regenerated), draft.description)
        for title in result.kept:
            if title in manifest.sections:
                merged_manifest.sections[title] = manifest.sections[title]
        merged_manifest.save(skill_dir)
        print(f"✓ updated {target}")

    for label, titles in (
        ("refreshed", result.refreshed),
        ("added", result.added),
        ("kept your edits", result.kept),
        ("removed", result.dropped),
    ):
        if titles:
            print(f"  {label}: {', '.join(titles)}")
    if not manifest.known:
        print("  ! no .skill-forge.json — treated everything present as hand-edited")

    problems = lint_path(target)[0]
    for p in problems.problems:
        print(f"  {'-' if p.severity == 'error' else '!'} {p.field}: {p.message}")
    return 0 if problems.ok else 1


def _harden_streams() -> None:
    """Never let a unicode glyph (✓ ✗ —) abort the process on a non-UTF-8 console."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # TextIOWrapper, Python 3.7+
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _harden_streams()
    parser = _build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "forge": _cmd_forge,
        "lint": _cmd_lint,
        "check": _cmd_check,
        "update": _cmd_update,
        "version": lambda _a: (print(f"skill-forge {__version__}") or 0),
    }
    handler = handlers[args.command]
    try:
        return handler(args)
    except SkillForgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
