"""`skill-forge update`: refresh a generated skill without discarding hand edits.

The whole feature turns on one question — *did the generator change this, or did a
human?* — which a two-way diff cannot answer. These tests pin the manifest-based answer
and, just as importantly, the safe fallback when there is no manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_forge.cli import main
from skill_forge.update import (
    MANIFEST_NAME,
    MANIFEST_VERSION,
    Manifest,
    merge,
    parse,
)

GENERATED = """\
---
name: mytool
description: Use this skill when working with mytool.
metadata:
  version: 0.1.0
---

Preamble text.

## When to use

Reach for this skill when a task involves mytool.

## Notes

Generated note.
"""

REGENERATED = """\
---
name: mytool
description: Use this skill when working with mytool and friends.
metadata:
  version: 0.2.0
---

New preamble text.

## When to use

Reach for this skill when a task involves mytool or tsvtool.

## Notes

Regenerated note.

## Configuration

Set MYTOOL_THREADS.
"""


def _manifest_of(text: str) -> Manifest:
    doc = parse(text)
    from skill_forge.frontmatter import parse_frontmatter

    fields, _ = parse_frontmatter(text)
    return Manifest.from_document(doc, fields.get("description", ""))


# -- parsing -----------------------------------------------------------------


def test_parse_splits_frontmatter_preamble_and_sections():
    doc = parse(GENERATED)
    assert "name: mytool" in doc.frontmatter
    assert doc.preamble == "Preamble text."
    assert [s.title for s in doc.sections] == ["When to use", "Notes"]


def test_parse_handles_a_document_with_no_frontmatter():
    doc = parse("## Only\n\nBody.\n")
    assert doc.frontmatter == ""
    assert [s.title for s in doc.sections] == ["Only"]


def test_the_h1_title_belongs_to_the_preamble_not_a_section():
    """In a SKILL.md `#` is the document title; sections start at `##`."""
    doc = parse("# Mytool\n\nIntro.\n\n## A\n\nx\n")
    assert [s.title for s in doc.sections] == ["A"]
    assert doc.preamble.startswith("# Mytool")


def test_splitting_uses_the_shallowest_section_level_present():
    """A body whose sections are `###` splits there rather than finding nothing."""
    doc = parse("# T\n\n### One\n\na\n\n### Two\n\nb\n")
    assert [s.title for s in doc.sections] == ["One", "Two"]


def test_deeper_headings_stay_inside_their_section():
    doc = parse("## A\n\n### A.1\n\ntext\n\n## B\n\nx\n")
    assert [s.title for s in doc.sections] == ["A", "B"]
    assert "A.1" in doc.sections[0].body


def test_digest_ignores_incidental_whitespace():
    a = parse("## A\n\none  two\n").sections[0]
    b = parse("## A\n\none two\n").sections[0]
    assert a.digest == b.digest


# -- merging with a manifest -------------------------------------------------


def test_untouched_sections_are_refreshed():
    result = merge(GENERATED, REGENERATED, _manifest_of(GENERATED))
    assert "Regenerated note." in result.text
    assert "Notes" in result.refreshed


def test_hand_edited_sections_are_kept():
    edited = GENERATED.replace(
        "Reach for this skill when a task involves mytool.",
        "Reach for this when converting at scale.",
    )
    result = merge(edited, REGENERATED, _manifest_of(GENERATED))
    assert "Reach for this when converting at scale." in result.text
    assert "tsvtool" not in result.text
    assert "When to use" in result.kept


def test_new_sections_are_added():
    result = merge(GENERATED, REGENERATED, _manifest_of(GENERATED))
    assert "Set MYTOOL_THREADS." in result.text
    assert "Configuration" in result.added


def test_hand_written_sections_survive():
    extended = GENERATED + "\n## Gotchas\n\nWatch the null handling.\n"
    result = merge(extended, REGENERATED, _manifest_of(GENERATED))
    assert "Watch the null handling." in result.text
    assert "Gotchas" in result.kept


def test_a_section_the_generator_dropped_is_removed_when_untouched():
    trimmed = REGENERATED.replace("## Notes\n\nRegenerated note.\n\n", "")
    result = merge(GENERATED, trimmed, _manifest_of(GENERATED))
    assert "Generated note." not in result.text
    assert "Notes" in result.dropped


def test_a_section_the_generator_dropped_is_kept_when_edited():
    edited = GENERATED.replace("Generated note.", "My own note.")
    trimmed = REGENERATED.replace("## Notes\n\nRegenerated note.\n\n", "")
    result = merge(edited, trimmed, _manifest_of(GENERATED))
    assert "My own note." in result.text
    assert "Notes" in result.kept


# -- frontmatter -------------------------------------------------------------


def test_an_untouched_description_is_refreshed():
    result = merge(GENERATED, REGENERATED, _manifest_of(GENERATED))
    assert "mytool and friends" in result.text
    assert "description" in result.refreshed


def test_a_hand_written_description_is_kept():
    edited = GENERATED.replace(
        "Use this skill when working with mytool.",
        "Use when the user needs CSV to Parquet conversion.",
    )
    result = merge(edited, REGENERATED, _manifest_of(GENERATED))
    assert "Use when the user needs CSV to Parquet conversion." in result.text
    assert "description" in result.kept


def test_the_name_is_never_rewritten():
    renamed = GENERATED.replace("name: mytool", "name: my-tool")
    result = merge(renamed, REGENERATED, _manifest_of(GENERATED))
    assert "name: my-tool" in result.text


def test_nested_metadata_survives_the_merge():
    """A flat frontmatter round-trip would drop the metadata block entirely."""
    result = merge(GENERATED, REGENERATED, _manifest_of(GENERATED))
    assert "metadata:" in result.text
    assert "version:" in result.text


# -- merging with no manifest ------------------------------------------------


def test_without_a_manifest_nothing_generated_is_overwritten():
    """The safe direction to be wrong: additive only."""
    result = merge(GENERATED, REGENERATED, Manifest())
    assert "Generated note." in result.text  # not refreshed
    assert "Reach for this skill when a task involves mytool." in result.text
    assert result.refreshed == ()


def test_without_a_manifest_new_sections_are_still_added():
    result = merge(GENERATED, REGENERATED, Manifest())
    assert "Set MYTOOL_THREADS." in result.text
    assert "Configuration" in result.added


def test_without_a_manifest_nothing_is_dropped():
    trimmed = REGENERATED.replace("## Notes\n\nRegenerated note.\n\n", "")
    result = merge(GENERATED, trimmed, Manifest())
    assert "Generated note." in result.text
    assert result.dropped == ()


def test_merging_identical_content_is_a_no_op():
    result = merge(GENERATED, GENERATED, _manifest_of(GENERATED))
    assert result.text == GENERATED
    assert result.changed_titles == ()


# -- the manifest file -------------------------------------------------------


def test_manifest_round_trips(tmp_path):
    manifest = _manifest_of(GENERATED)
    manifest.save(tmp_path)
    loaded = Manifest.load(tmp_path)
    assert loaded.sections == manifest.sections
    assert loaded.description == manifest.description
    assert loaded.known is True


def test_a_missing_manifest_loads_as_unknown(tmp_path):
    assert Manifest.load(tmp_path).known is False


def test_a_corrupt_manifest_loads_as_unknown_rather_than_raising(tmp_path):
    (tmp_path / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    assert Manifest.load(tmp_path).known is False


def test_a_manifest_from_another_version_is_ignored(tmp_path):
    (tmp_path / MANIFEST_NAME).write_text(
        json.dumps({"version": MANIFEST_VERSION + 99, "sections": {"A": "x"}}), encoding="utf-8"
    )
    assert Manifest.load(tmp_path).known is False


def test_the_manifest_explains_itself(tmp_path):
    _manifest_of(GENERATED).save(tmp_path)
    data = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert "skill-forge update" in data["note"]


# -- CLI ---------------------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    source = tmp_path / "mytool"
    source.mkdir()
    (source / "README.md").write_text(
        "# mytool\n\nA tool for converting CSV files.\n", encoding="utf-8"
    )
    return tmp_path, source


def _skill(tmp_path: Path) -> Path:
    return tmp_path / "skills" / "mytool" / "SKILL.md"


def test_forge_writes_a_manifest(project, capsys):
    tmp_path, source = project
    assert main(["forge", str(source), "-o", str(tmp_path / "skills")]) == 0
    assert (_skill(tmp_path).parent / MANIFEST_NAME).is_file()


def test_update_refreshes_generated_content_and_keeps_edits(project, capsys):
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    capsys.readouterr()

    skill = _skill(tmp_path)
    edited = skill.read_text(encoding="utf-8").replace(
        "## When to use", "## When to use\n\nMY OWN GUIDANCE.\n\n<!--kept-->"
    )
    skill.write_text(edited, encoding="utf-8")

    (source / "README.md").write_text(
        "# mytool\n\nA fast tool for converting CSV and TSV files.\n", encoding="utf-8"
    )
    assert main(["update", str(source), "-o", str(tmp_path / "skills")]) == 0

    after = skill.read_text(encoding="utf-8")
    assert "MY OWN GUIDANCE." in after  # the edit survived
    assert "CSV and TSV" in after  # the regenerated prose landed
    assert "kept your edits" in capsys.readouterr().out


def test_update_diff_writes_nothing(project, capsys):
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    (source / "README.md").write_text("# mytool\n\nSomething else entirely.\n", encoding="utf-8")
    capsys.readouterr()

    before = _skill(tmp_path).read_text(encoding="utf-8")
    assert main(["update", str(source), "-o", str(tmp_path / "skills"), "--diff"]) == 0
    assert _skill(tmp_path).read_text(encoding="utf-8") == before
    assert "---" in capsys.readouterr().out


def test_update_on_an_unchanged_source_is_a_no_op(project, capsys):
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    capsys.readouterr()
    assert main(["update", str(source), "-o", str(tmp_path / "skills")]) == 0
    assert "already up to date" in capsys.readouterr().out


def test_update_without_an_existing_skill_is_an_error(project, capsys):
    tmp_path, source = project
    assert main(["update", str(source), "-o", str(tmp_path / "skills")]) == 1
    assert "skill-forge forge" in capsys.readouterr().err


def test_update_warns_when_there_is_no_manifest(project, capsys):
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    (_skill(tmp_path).parent / MANIFEST_NAME).unlink()
    (source / "README.md").write_text("# mytool\n\nQuite different now.\n", encoding="utf-8")
    capsys.readouterr()

    main(["update", str(source), "-o", str(tmp_path / "skills")])
    assert "no .skill-forge.json" in capsys.readouterr().out


def test_check_points_at_update(project, capsys):
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    (source / "README.md").write_text("# mytool\n\nDrifted.\n", encoding="utf-8")
    capsys.readouterr()

    assert main(["check", str(source), "-o", str(tmp_path / "skills")]) == 1
    assert "skill-forge update" in capsys.readouterr().out


def test_an_updated_skill_still_lints_clean(project, capsys):
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    (source / "README.md").write_text(
        "# mytool\n\nA fast tool for converting CSV and TSV files.\n", encoding="utf-8"
    )
    main(["update", str(source), "-o", str(tmp_path / "skills")])
    capsys.readouterr()
    assert main(["lint", str(tmp_path / "skills")]) == 0


def test_updating_twice_is_stable(project, capsys):
    """The second update must find nothing to do — no oscillation between passes."""
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    (source / "README.md").write_text("# mytool\n\nA different summary.\n", encoding="utf-8")
    main(["update", str(source), "-o", str(tmp_path / "skills")])
    first = _skill(tmp_path).read_text(encoding="utf-8")
    capsys.readouterr()

    main(["update", str(source), "-o", str(tmp_path / "skills")])
    assert _skill(tmp_path).read_text(encoding="utf-8") == first
    assert "already up to date" in capsys.readouterr().out


def test_an_edit_stays_kept_across_repeated_updates(project, capsys):
    """Re-baselining must not silently adopt a hand edit as generated content."""
    tmp_path, source = project
    main(["forge", str(source), "-o", str(tmp_path / "skills")])
    skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8").replace("## When to use", "## When to use\n\nMINE.\n"),
        encoding="utf-8",
    )
    for summary in ("First change.", "Second change.", "Third change."):
        (source / "README.md").write_text(f"# mytool\n\n{summary}\n", encoding="utf-8")
        main(["update", str(source), "-o", str(tmp_path / "skills")])
    capsys.readouterr()
    assert "MINE." in skill.read_text(encoding="utf-8")
