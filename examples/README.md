# Examples

Runnable demos of `skill-forge`. From the repo root, after `pip install -e .`:

```bash
bash examples/demo.sh
```

## What `demo.sh` does

1. **Generate from a Python project** — forges a skill from a tiny sample package
   (`examples/sample_tool`) to `--stdout` so you can read it.
2. **Generate from a doc** — forges a skill straight from this repo's `README.md`.
3. **Lint** — runs the bundled validator over a generated skill.
4. **Drift check** — writes a skill, then shows `skill-forge check` passing (in sync).

Everything here is offline and deterministic — no API key required. Add `--llm` to any
`forge` call (with `pip install 'skill-forge[anthropic]'` and `ANTHROPIC_API_KEY` set) to see
the optional Claude refinement.

## `sample_tool`

A minimal click-based CLI package used as a forge target. Note how the generated skill picks
up the `hello` and `bye` subcommands, the `__all__` exports (`greet`, `farewell`), and the
`pyproject.toml` metadata — without ever importing or running the code.
