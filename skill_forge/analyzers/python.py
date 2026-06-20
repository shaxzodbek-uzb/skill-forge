"""Analyze a Python package, project, or single module.

Uses :mod:`ast` only — the target source is parsed, never imported or executed. Pulls the
project name/summary/keywords from ``pyproject.toml`` (or ``setup.cfg``), the public API
from ``__all__`` / top-level defs, console entry points from ``[project.scripts]``, and
subcommands from argparse / click / typer call sites.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from ..models import Command, SourceSignals
from .base import clean_section_titles, find_readme, parse_markdown, read_text, tokenize_keywords

_SKIP_DIRS = {"tests", "test", "docs", "examples", "build", "dist", ".venv", "venv", "__pycache__"}


def analyze(path: str | Path) -> SourceSignals:
    p = Path(path)
    if p.is_file():
        return _analyze_module(p)
    return _analyze_project(p)


def _analyze_module(file: Path) -> SourceSignals:
    text = read_text(file)
    api, commands = _scan_python(text)
    summary = _module_summary(text)
    return SourceSignals(
        name=file.stem,
        summary=summary,
        kind="python",
        language="Python",
        api=api,
        commands=commands,
        keywords=tokenize_keywords(file.stem, summary, " ".join(api)),
        source=str(file),
    )


def _analyze_project(directory: Path) -> SourceSignals:
    meta = _load_project_meta(directory)
    name = meta.get("name", "") or directory.name
    summary = meta.get("description", "")
    keywords_meta = meta.get("keywords", [])
    scripts = meta.get("scripts", {})
    homepage = meta.get("homepage")

    commands = [Command(name=key) for key in scripts]
    api: list[str] = []
    usage: list[str] = []
    notes: list[str] = []

    pkg_init = _find_package_init(directory, name)
    if pkg_init is not None:
        mod_api, mod_commands = _scan_python(read_text(pkg_init))
        api = mod_api
        commands = _merge_commands(commands, mod_commands)

    # Look for a CLI module to enrich subcommands.
    for cli_name in ("cli.py", "__main__.py", "main.py", "console.py"):
        cli_file = (pkg_init.parent / cli_name) if pkg_init else (directory / cli_name)
        if cli_file.is_file():
            _, cli_commands = _scan_python(read_text(cli_file))
            commands = _merge_commands(commands, cli_commands)

    readme = find_readme(directory)
    if readme is not None:
        md = parse_markdown(read_text(readme))
        if not summary:
            summary = md["summary"]
        if not name:
            name = md["title"]
        usage = md["code_blocks"][:3]
        cleaned = clean_section_titles([h for level, h in md["headings"] if level == 2])
        notes = cleaned[:8] if len(cleaned) >= 2 else []

    install = f"pip install {name}" if name else None
    keywords = tokenize_keywords(
        name,
        " ".join(keywords_meta),
        " ".join(c.name for c in commands),
        " ".join(api),
        summary,
    )

    return SourceSignals(
        name=name,
        summary=summary,
        kind="python",
        language="Python",
        install=install,
        homepage=homepage,
        commands=commands,
        api=api,
        usage=usage,
        keywords=keywords,
        notes=notes,
        source=str(directory),
    )


# --------------------------------------------------------------------------- ast scanning


def _module_summary(text: str) -> str:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return ""
    doc = ast.get_docstring(tree)
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip()


def _scan_python(text: str) -> tuple[list[str], list[Command]]:
    """Return (public api names, subcommands) from a Python source string via ast."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return [], []

    api = _public_api(tree)
    commands = _subcommands(tree)
    return api, commands


def _public_api(tree: ast.Module) -> list[str]:
    # Prefer an explicit __all__, including augmented `__all__ += [...]` extensions.
    declared: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            declared = _string_list(node.value)
        elif (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
            and isinstance(node.op, ast.Add)
        ):
            declared.extend(_string_list(node.value))
    if declared:
        return declared[:20]
    # Otherwise, public top-level defs and classes.
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
    return names[:20]


def _subcommands(tree: ast.Module) -> list[Command]:
    found: dict[str, Command] = {}

    for node in ast.walk(tree):
        # argparse: subparsers.add_parser("name", help="...")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_parser":
                name = _first_string_arg(node)
                if name:
                    found.setdefault(name, Command(name=name, help=_keyword_string(node, "help")))

        # click / typer: @app.command(...) / @cli.command("name") / @click.command(...)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                cmd = _command_from_decorator(deco, node.name)
                if cmd is not None:
                    found.setdefault(cmd.name, cmd)

    return list(found.values())


def _command_from_decorator(deco: ast.expr, func_name: str) -> Command | None:
    target = deco.func if isinstance(deco, ast.Call) else deco
    attr = None
    if isinstance(target, ast.Attribute):
        attr = target.attr
    elif isinstance(target, ast.Name):
        attr = target.id
    if attr not in {"command"}:
        return None
    name = func_name.replace("_", "-")
    if isinstance(deco, ast.Call):
        explicit = _first_string_arg(deco)
        if explicit:
            name = explicit
    return Command(name=name)


def _first_string_arg(call: ast.Call) -> str:
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return ""


def _keyword_string(call: ast.Call, key: str) -> str:
    for kw in call.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return ""


def _string_list(node: ast.expr) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return []
    out: list[str] = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
    return out


def _merge_commands(base: list[Command], extra: list[Command]) -> list[Command]:
    by_name = {c.name: c for c in base}
    for c in extra:
        if c.name not in by_name:
            by_name[c.name] = c
        elif not by_name[c.name].help and c.help:
            by_name[c.name] = c
    return list(by_name.values())


def _find_package_init(directory: Path, name: str) -> Path | None:
    """Find the import package's __init__.py (prefer one matching the dist name)."""
    candidates: list[Path] = []
    underscored = name.replace("-", "_") if name else ""
    direct = directory / underscored / "__init__.py"
    if underscored and direct.is_file():
        return direct
    # src/ layout
    src_direct = directory / "src" / underscored / "__init__.py"
    if underscored and src_direct.is_file():
        return src_direct
    for base in (directory, directory / "src"):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.name in _SKIP_DIRS or not child.is_dir():
                continue
            if (child / "__init__.py").is_file():
                candidates.append(child / "__init__.py")
    return candidates[0] if candidates else None


# --------------------------------------------------------------------------- project metadata


def _load_project_meta(directory: Path) -> dict:
    pyproject = directory / "pyproject.toml"
    if pyproject.is_file():
        data = _read_toml(pyproject)
        project = data.get("project", {}) if isinstance(data, dict) else {}
        urls = project.get("urls", {}) if isinstance(project, dict) else {}
        homepage = None
        if isinstance(urls, dict):
            homepage = urls.get("Homepage") or urls.get("homepage") or urls.get("Repository")
        return {
            "name": project.get("name", ""),
            "description": project.get("description", ""),
            "keywords": project.get("keywords", []) or [],
            "scripts": project.get("scripts", {}) or {},
            "homepage": homepage,
        }
    setup_cfg = directory / "setup.cfg"
    if setup_cfg.is_file():
        return _read_setup_cfg(setup_cfg)
    return {}


def _read_toml(path: Path) -> dict:
    text = read_text(path)
    try:
        import tomllib

        return tomllib.loads(text)
    except ModuleNotFoundError:
        return _toml_fallback(text)
    except Exception:
        return {}


def _toml_fallback(text: str) -> dict:
    """Tiny [project] reader for Python 3.10 (no tomllib). Handles the fields we use,
    including multi-line PEP 621 arrays like ``keywords = [\\n  "a",\\n  "b",\\n]``."""
    project: dict = {}
    scripts: dict = {}
    section = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Consume continuation lines for a multi-line array value.
        if value.startswith("[") and "]" not in value:
            while i < len(lines) and "]" not in value:
                value += " " + lines[i].strip()
                i += 1
        if section == "project":
            if key in {"name", "description"}:
                project[key] = _toml_str(value)
            elif key == "keywords":
                project["keywords"] = _toml_str_list(value)
        elif section == "project.scripts":
            scripts[key] = _toml_str(value)
    if scripts:
        project["scripts"] = scripts
    return {"project": project}


def _toml_str(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _toml_str_list(value: str) -> list[str]:
    return re.findall(r"['\"]([^'\"]+)['\"]", value)


def _read_setup_cfg(path: Path) -> dict:
    import configparser

    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError):
        return {}
    meta = parser["metadata"] if parser.has_section("metadata") else {}
    keywords = meta.get("keywords", "") if meta else ""
    return {
        "name": meta.get("name", "") if meta else "",
        "description": meta.get("description", "") if meta else "",
        "keywords": [k.strip() for k in re.split(r"[,\n]", keywords) if k.strip()],
        "scripts": {},
        "homepage": meta.get("url") if meta else None,
    }
