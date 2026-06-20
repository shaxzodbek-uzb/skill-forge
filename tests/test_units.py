"""Unit tests for slug, frontmatter, validate, and describe."""

from __future__ import annotations

import pytest

from skill_forge import (
    Command,
    Settings,
    SourceSignals,
    build_description,
    is_kebab_case,
    lint_text,
    slugify,
)
from skill_forge.frontmatter import parse_frontmatter, render_frontmatter
from skill_forge.validate import DESCRIPTION_MAX, DESCRIPTION_MIN

# --------------------------------------------------------------------------- slug


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("My Cool Tool", "my-cool-tool"),
        ("@acme/gizmo", "gizmo"),
        ("myCoolTool", "my-cool-tool"),
        ("widget.core", "widget-core"),
        ("  spaced  out  ", "spaced-out"),
        ("Café Münch", "cafe-munch"),
    ],
)
def test_slugify(raw, expected):
    assert slugify(raw) == expected
    assert is_kebab_case(slugify(raw))


def test_slugify_rejects_empty():
    with pytest.raises(ValueError):
        slugify("***")


def test_is_kebab_case():
    assert is_kebab_case("a-b-c")
    assert not is_kebab_case("Ab")
    assert not is_kebab_case("a--b")
    assert not is_kebab_case("-a")


# --------------------------------------------------------------------------- frontmatter


def test_frontmatter_roundtrip():
    fields = {"name": "my-skill", "description": "Use when X: do Y", "version": "1.2.3"}
    text = render_frontmatter(fields) + "\n\nbody here\n"
    parsed, body = parse_frontmatter(text)
    assert parsed["name"] == "my-skill"
    assert parsed["description"] == "Use when X: do Y"  # colon survived quoting
    assert parsed["version"] == "1.2.3"
    assert body.strip() == "body here"


def test_frontmatter_skips_empty_values():
    out = render_frontmatter({"name": "x", "license": "", "version": None})
    assert "license" not in out
    assert "version" not in out


def test_parse_no_frontmatter():
    fields, body = parse_frontmatter("no frontmatter here")
    assert fields == {}
    assert body == "no frontmatter here"


# --------------------------------------------------------------------------- validate


# version lives under metadata (spec-correct), so a good skill has no top-level version.
def _good_skill(description: str = "x" * 60, body: str = "Body.") -> str:
    return (
        f"---\nname: my-skill\ndescription: {description}\n"
        f"metadata:\n  version: 0.1.0\n---\n\n{body}\n"
    )


def test_validate_clean():
    assert lint_text(_good_skill(), dir_name="my-skill") == []


def test_validate_malformed_frontmatter():
    problems = lint_text("no frontmatter\n\nbody", dir_name="my-skill")
    assert len(problems) == 1 and problems[0].field == "frontmatter"


def test_validate_name_rules():
    text = "---\nname: My_Skill\ndescription: " + "x" * 60 + "\n---\n\nbody\n"
    fields = [p.field for p in lint_text(text, dir_name="other")]
    assert fields.count("name") == 2  # not kebab + mismatched dir


def test_validate_description_boundaries():
    # exactly MIN and MAX are valid; one over each is not.
    assert lint_text(_good_skill("x" * DESCRIPTION_MIN), dir_name="my-skill") == []
    assert lint_text(_good_skill("x" * DESCRIPTION_MAX), dir_name="my-skill") == []
    short = lint_text(_good_skill("x" * (DESCRIPTION_MIN - 1)), dir_name="my-skill")
    assert any(p.field == "description" for p in short)
    long = lint_text(_good_skill("x" * (DESCRIPTION_MAX + 1)), dir_name="my-skill")
    assert any(p.field == "description" for p in long)


def test_validate_version_optional_and_placement():
    # No version at all is clean (version is optional, not a required spec field).
    no_version = "---\nname: my-skill\ndescription: " + "x" * 60 + "\n---\n\nbody\n"
    assert lint_text(no_version, dir_name="my-skill") == []
    # A top-level version is a placement warning (it belongs under metadata).
    top_level = "---\nname: my-skill\ndescription: " + "x" * 60 + "\nversion: 0.1.0\n---\n\nbody\n"
    problems = lint_text(top_level, dir_name="my-skill")
    assert problems and all(p.severity == "warning" for p in problems)
    assert any(p.field == "version" for p in problems)


def test_validate_empty_body():
    text = (
        "---\nname: my-skill\ndescription: " + "x" * 60
        + "\nmetadata:\n  version: 0.1.0\n---\n\n   \n"
    )
    assert any(p.field == "body" for p in lint_text(text, dir_name="my-skill"))


# --------------------------------------------------------------------------- describe


def test_describe_budget_and_triggers():
    signals = SourceSignals(
        name="widget",
        summary="A widget toolkit",
        commands=[Command("build"), Command("ship-it")],
        keywords=["widget", "gadget"],
    )
    desc = build_description(signals)
    assert DESCRIPTION_MIN <= len(desc) <= DESCRIPTION_MAX
    assert "build" in desc  # at least one command trigger present
    assert not desc.endswith(" ")


def test_describe_clamps_long_summary():
    signals = SourceSignals(name="x", summary="lorem ipsum " * 200)
    desc = build_description(signals)
    assert len(desc) <= DESCRIPTION_MAX
    assert not desc.endswith(("lore", "lor", "ipsu"))  # no mid-word cut


def test_describe_pads_thin_input():
    desc = build_description(SourceSignals(name="ab"))
    assert len(desc) >= DESCRIPTION_MIN


def test_describe_respects_custom_max():
    settings = Settings(max_description=80)
    signals = SourceSignals(name="widget", summary="a " * 100, keywords=["a", "b", "c"])
    assert len(build_description(signals, settings=settings)) <= 80
