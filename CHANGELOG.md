# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release of `skill-forge`, a CLI that generates a valid Claude `SKILL.md` from a
  codebase, package, or doc.
- **Deterministic, offline, zero-dependency core** — `analyze → draft → validate` uses only
  the standard library and never executes the target code.
- **Valid by construction** — every generated skill passes the bundled linter; the tool
  refuses to write a skill that does not lint clean.
- Analyzers:
  - **Python** — `pyproject.toml` / `setup.cfg`, `__all__` / public defs via `ast`, and
    argparse / click / typer subcommands.
  - **Node** — `package.json` (name, description, keywords, `bin`) + README, TS/JS detection.
  - **Docs** — a single markdown/rst/txt file (title, summary, headings, code blocks).
  - **Generic** — README + a language histogram of the file tree.
  - **CLI help** — `--from-cli "<cmd>"` captures and parses a tool's `--help` (no shell,
    timeout-guarded, explicit opt-in).
- CLI subcommands: `forge`, `lint`, `check` (CI drift guard), and `version`.
- Optional `--llm` refinement via Claude (the only extra, lazily imported and fail-safe:
  it never produces a worse skill than the offline path).
- GitHub Actions CI: ruff + pytest on Python 3.10–3.13, plus a self-forge dogfood step.
