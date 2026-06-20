"""Shared fixtures: small on-disk sources for each analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """A Python project with pyproject, a package with __all__, a click CLI, and a README."""
    root = tmp_path / "widget"
    pkg = root / "widget"
    pkg.mkdir(parents=True)

    (root / "pyproject.toml").write_text(
        '[project]\n'
        'name = "widget"\n'
        'description = "A widget toolkit for building widgets fast."\n'
        'keywords = ["widget", "gadget", "toolkit"]\n'
        '\n[project.scripts]\n'
        'widget = "widget.cli:main"\n',
        encoding="utf-8",
    )
    (pkg / "__init__.py").write_text(
        '"""Widget toolkit for building widgets."""\n'
        '__all__ = ["make_widget", "Widget"]\n'
        "def make_widget():\n    return Widget()\n"
        "class Widget:\n    pass\n"
        "def _private():\n    pass\n",
        encoding="utf-8",
    )
    (pkg / "cli.py").write_text(
        "import click\n"
        "@click.group()\n"
        "def cli():\n    pass\n"
        "@cli.command()\n"
        "def build():\n    pass\n"
        '@cli.command("ship-it")\n'
        "def ship():\n    pass\n"
        "def main():\n    cli()\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Widget\n\n"
        "A widget toolkit for building widgets fast.\n\n"
        "## Installation\n\n"
        "```bash\npip install widget\n```\n\n"
        "## Usage\n\n"
        "```bash\nwidget build\n```\n\n"
        "## Notes\n\nSome notes here.\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def node_project(tmp_path: Path) -> Path:
    root = tmp_path / "gizmo"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "@acme/gizmo",
                "description": "A gizmo CLI for gizmo things.",
                "keywords": ["gizmo", "cli", "acme"],
                "bin": {"gizmo": "./bin/gizmo.js", "giz": "./bin/giz.js"},
                "homepage": "https://example.com/gizmo",
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Gizmo\n\nThe gizmo command line.\n\n## API\n\nstuff\n", encoding="utf-8"
    )
    return root


@pytest.fixture
def docs_file(tmp_path: Path) -> Path:
    doc = tmp_path / "guide.md"
    doc.write_text(
        "# Cool Guide\n\n"
        "This explains the cool thing you can do with the tool.\n\n"
        "## Setup\n\nInstall it.\n\n"
        "## Reference\n\n```bash\ncool --help\n```\n",
        encoding="utf-8",
    )
    return doc


@pytest.fixture
def generic_project(tmp_path: Path) -> Path:
    root = tmp_path / "gopher"
    root.mkdir()
    (root / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    (root / "util.go").write_text("package main\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Gopher\n\nA small Go service that does one thing well.\n\n## Build\n\ngo build\n",
        encoding="utf-8",
    )
    return root
