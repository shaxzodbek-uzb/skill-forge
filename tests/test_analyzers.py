"""Tests for source detection and each analyzer."""

from __future__ import annotations

from skill_forge import analyze, detect


def test_detect(python_project, node_project, docs_file, generic_project):
    assert detect(python_project) == "python"
    assert detect(node_project) == "node"
    assert detect(docs_file) == "docs"
    assert detect(generic_project) == "generic"


def test_python_analyzer(python_project):
    s = analyze(python_project)
    assert s.name == "widget"
    assert "widget toolkit" in s.summary.lower()
    assert "make_widget" in s.api and "Widget" in s.api
    assert "_private" not in s.api
    cmd_names = {c.name for c in s.commands}
    assert {"widget", "build", "ship-it"} <= cmd_names
    assert s.language == "Python"
    assert s.install == "pip install widget"
    assert s.keywords


def test_python_single_module(tmp_path):
    mod = tmp_path / "tool.py"
    mod.write_text(
        '"""A handy tool.\n\nMore detail."""\n'
        '__all__ = ["run"]\n'
        "def run():\n    pass\n",
        encoding="utf-8",
    )
    s = analyze(mod, kind="python")
    assert s.name == "tool"
    assert s.summary == "A handy tool."
    assert s.api == ["run"]


def test_node_analyzer(node_project):
    s = analyze(node_project)
    assert s.name == "@acme/gizmo"
    assert "gizmo" in s.summary.lower()
    cmd_names = {c.name for c in s.commands}
    assert {"gizmo", "giz"} <= cmd_names
    assert s.language == "JavaScript"
    assert s.homepage == "https://example.com/gizmo"
    assert s.keywords


def test_docs_analyzer(docs_file):
    s = analyze(docs_file)
    assert s.name == "Cool Guide"
    assert s.summary.startswith("This explains")
    assert "Setup" in s.notes and "Reference" in s.notes
    assert any("cool --help" in u for u in s.usage)


def test_generic_analyzer(generic_project):
    s = analyze(generic_project)
    assert s.name == "Gopher"  # README H1 wins over the dir name
    assert s.language == "Go"
    assert "go service" in s.summary.lower()
