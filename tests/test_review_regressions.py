"""Regression tests for issues found in the adversarial review. Each maps to a confirmed
finding so the fix stays fixed."""

from __future__ import annotations

import pytest

from skill_forge import (
    AnalyzerError,
    Command,
    InvalidSkill,
    SkillForgeError,
    SourceSignals,
    analyze,
    build_body,
    build_description,
    draft_from_signals,
    forge,
)
from skill_forge.analyzers.cli_help import capture_cli_help
from skill_forge.analyzers.python import _scan_python, _toml_fallback
from skill_forge.cli import main
from skill_forge.frontmatter import parse_frontmatter, render_frontmatter


# #1 — render/parse must round-trip values that trip _quote's escaping.
@pytest.mark.parametrize("value", ['"hello', "a\\b", "Use X: do Y", "ends with #", "plain"])
def test_frontmatter_escaping_roundtrip(value):
    text = render_frontmatter({"name": value}) + "\nbody\n"
    parsed, _ = parse_frontmatter(text)
    assert parsed["name"] == value


# #2 — the 3.10 TOML fallback must read multi-line PEP 621 arrays (with comments).
def test_toml_fallback_multiline_keywords():
    text = (
        '[project]\nname = "demo"\n'
        'keywords = [\n  "alpha",\n  "beta",  # inline\n  "gamma",\n]\n'
    )
    project = _toml_fallback(text)["project"]
    assert project["keywords"] == ["alpha", "beta", "gamma"]
    assert project["name"] == "demo"


# #3 — augmented __all__ extends the public API.
def test_augmented_all_collected():
    src = '__all__ = ["run"]\n__all__ += ["build", "deploy"]\ndef run():\n    pass\n'
    api, _ = _scan_python(src)
    assert api == ["run", "build", "deploy"]


# #4 — a syntactically broken module degrades gracefully (no raise, empty api).
def test_broken_python_degrades(tmp_path):
    mod = tmp_path / "broken.py"
    mod.write_text("def (:\n  not python at all\n", encoding="utf-8")
    signals = analyze(mod, kind="python")
    assert signals.name == "broken"
    assert signals.api == []


# #5 — a non-sluggable source name surfaces a clean SkillForgeError, never a traceback.
def test_nonsluggable_source_errors(tmp_path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text("# 🎉🎉🎉\n\nEmoji only.\n", encoding="utf-8")
    with pytest.raises(SkillForgeError):
        forge(doc)
    rc = main(["forge", str(doc), "--stdout"])
    assert rc == 1
    assert "could not derive a usable skill name" in capsys.readouterr().err


def test_nonsluggable_draft_from_signals_raises():
    with pytest.raises(InvalidSkill):
        draft_from_signals(SourceSignals(name="🎉"))


# #8 — --from-cli must reject a trailing flag (it would become the skill name).
def test_from_cli_rejects_trailing_flag():
    with pytest.raises(AnalyzerError):
        capture_cli_help("git --version")


def test_cli_from_cli_flag_clean_error(capsys):
    rc = main(["forge", "--from-cli", "git --version", "--stdout"])
    assert rc == 1
    assert "not a flag" in capsys.readouterr().err


# #10 — the description must not leak raw markdown markup.
def test_description_strips_markdown():
    desc = build_description(
        SourceSignals(
            name="tool", summary="A **bold** tool with `code` and _emphasis_", keywords=["a"]
        )
    )
    assert "**" not in desc
    assert "`" not in desc
    assert "_emphasis_" not in desc


# #9 / #11 — boilerplate headings are dropped from Related topics and from keywords.
def test_docs_notes_and_keywords_filtered(tmp_path):
    doc = tmp_path / "guide.md"
    doc.write_text(
        "# Single Source of Truth\n\nThe canonical reference.\n\n"
        "## Installation\n\nx\n\n## License\n\ny\n\n## Migrations\n\nz\n\n## Rollbacks\n\nw\n",
        encoding="utf-8",
    )
    s = analyze(doc)
    assert "Installation" not in s.notes and "License" not in s.notes
    assert "Migrations" in s.notes and "Rollbacks" in s.notes
    assert "single" not in s.keywords and "source" not in s.keywords


def test_docs_only_boilerplate_headings_yields_no_notes(tmp_path):
    doc = tmp_path / "g.md"
    doc.write_text(
        "# Thing\n\nA thing.\n\n## Installation\n\nx\n\n## License\n\ny\n", encoding="utf-8"
    )
    assert analyze(doc).notes == []


# spec alignment — generated skills put version under metadata, never top-level (skillspec
# and Anthropic's spec agree: `version` is not a recognized top-level frontmatter field).
def test_generated_version_is_under_metadata(python_project):
    from skill_forge import render_skill

    text = render_skill(forge(python_project))
    fields, _ = parse_frontmatter(text)
    assert "version" not in fields  # not a top-level key
    assert "metadata:\n  version: 0.1.0" in text  # nested under metadata
    # and the bundled linter is clean on our own output (no version-placement warning).
    from skill_forge import lint_text

    assert lint_text(text, dir_name="widget") == []


# spec alignment — a metadata value YAML would read as a number/bool (e.g. a `1.0`
# version) is quoted so it stays a string; skillspec's metadata-type rule and the
# Agent Skills spec require metadata to be a string-valued map.
def test_yaml_typed_metadata_value_is_quoted():
    from skill_forge.frontmatter import render_frontmatter

    text = render_frontmatter({"name": "x", "metadata": {"version": "1.0"}})
    assert 'version: "1.0"' in text
    assert "version: 1.0\n" not in text
    # a semver is not a YAML number and stays bare (no needless quoting / churn).
    semver = render_frontmatter({"name": "x", "metadata": {"version": "0.1.0"}})
    assert "version: 0.1.0" in semver
    assert '"0.1.0"' not in semver


# #13 — When-to-use is derived from signals, not static boilerplate.
def test_when_to_use_is_signal_driven():
    body = build_body(
        SourceSignals(
            name="widget", commands=[Command("build", "compile it")], keywords=["widget", "ci"]
        )
    )
    assert "run `build`" in body
    assert "Trigger phrases:" in body
