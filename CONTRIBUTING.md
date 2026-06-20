# Contributing to skill-forge

Thanks for helping make Claude skills easier to author. `skill-forge` has one job: take a
source and emit a `SKILL.md` that is **valid by construction** — so the bar for every change
is "the output still lints clean, deterministically, offline."

## Philosophy

- **Deterministic and offline by default.** The `analyze → draft → validate` path must never
  hit the network and must never import or execute the target code. The Python analyzer uses
  `ast` only. The single exception is the explicit `--from-cli` flag.
- **Zero runtime dependencies in the core.** `anthropic` is the only optional extra. If a
  change needs a new hard dependency, it almost certainly belongs behind an extra — or not at
  all. Prefer the standard library.
- **Valid by construction.** If you touch the generators, the property tests in
  `tests/test_forge.py` must still show every fixture rendering to a skill that passes
  `lint_text` with zero errors.
- **The SPEC is the contract.** [`SPEC.md`](SPEC.md) pins the public API and behavior. Change
  the spec in the same PR when you change the contract; don't let them drift.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q
```

CI runs ruff + pytest on Python 3.10–3.13 and a self-forge dogfood step on every push and PR.

## Adding an analyzer

1. Add `skill_forge/analyzers/<kind>.py` exposing `analyze(path) -> SourceSignals`.
2. Register it in `analyzers/__init__.py` (`_ANALYZERS`) and teach `detect()` when to pick it.
3. Add a fixture in `tests/conftest.py` and a test that asserts the extracted signals, plus a
   `test_forge_valid_by_construction` case so the generated skill is proven valid.
4. Keep it pure: no network, no executing the target.

## Reporting issues

Found a source that produces a bad (or invalid) skill? Open an issue with a **minimal repro**
source and the generated `SKILL.md`. A generated skill that fails `skill-forge lint` is a bug
and the most valuable kind of report.

## License

By contributing you agree your work is released under the [MIT License](LICENSE).
