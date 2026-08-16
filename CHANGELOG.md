# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-16

### Added

- **`skill-forge update`** — regenerate a skill from a changed source without
  discarding hand edits. Until now the only way to pick up new source material
  was to re-run `forge` and overwrite, which threw away every refinement made to
  the generated skill; the alternative was to merge by hand.
- A three-way merge against `.skill-forge.json`, a manifest written by `forge`
  recording a digest of each section as generated. A section still matching its
  digest is replaced with the newly generated text; a section you have edited is
  kept as yours. The frontmatter `description` follows the same rule — it is
  regenerated only if nobody has touched it.
- `update --diff` shows what would change without writing.
- `check` now points at `update` rather than `forge`, so the CI drift guard
  suggests the command that preserves edits.

### Notes

- A skill forged before 0.2.0 has no manifest. `update` still works, but treats
  everything already present as hand-edited: it adds new sections and refreshes
  nothing, and prints a note saying so. That is the safe direction to be wrong
  in — guessing which sections were generated would silently overwrite the ones
  it guessed wrong about. Re-run `forge` once to start the manifest.

## [0.1.2] - 2026-06-20

### Fixed

- **Metadata values are always emitted as strings.** A `metadata` value that a YAML
  parser would coerce to a number, boolean, or null — most commonly a `version` like
  `1.0` (a float) — is now quoted (`version: "1.0"`). Previously such values were written
  bare, so a numeric-looking `--version-str` produced `metadata.version: 1.0`, which the
  sibling linter [`skillspec`](https://github.com/shaxzodbek-uzb/skillspec) flagged as a
  non-string metadata value. Semantic versions like `0.1.0` (not a YAML number) are
  unaffected. This closes the last gap in the "forge → check" agreement.

## [0.1.1] - 2026-06-20

### Changed

- **Spec-correct `version` placement.** Generated skills now write the version under
  `metadata` (`metadata.version`) instead of a top-level `version:` field. Anthropic's
  Agent Skills spec recognizes only `name`, `description`, `license`, `allowed-tools`,
  `mode`, `disable-model-invocation`, and `metadata` at the top level — `version` is not a
  top-level field. This makes skill-forge's output pass its sibling linter
  [`skillspec`](https://github.com/shaxzodbek-uzb/skillspec) cleanly (forge → check now
  agree).
- The bundled linter (`skill-forge lint`) no longer treats a missing `version` as a
  problem (it is optional), and now warns when `version` appears as a top-level field,
  pointing to `metadata.version` — matching `skillspec`.

### Added

- `render_frontmatter` supports a one-level nested block (used for the `metadata` object).

## [0.1.0] - 2026-06-20

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
