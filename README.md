# skill-forge

**Point it at your code. Get a valid Claude skill. No API key required.**

`skill-forge` turns a codebase, package, or doc into a well-formed Claude
[`SKILL.md`](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) — and the
skill it writes is **valid by construction**.

```bash
pip install claude-skill-forge       # the CLI it installs is `skill-forge`
skill-forge forge ./my-tool          # writes .claude/skills/my-tool/SKILL.md
```

[![CI](https://github.com/shaxzodbek-uzb/skill-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/shaxzodbek-uzb/skill-forge/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/claude-skill-forge)](https://pypi.org/project/claude-skill-forge/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Dependencies](https://img.shields.io/badge/runtime%20deps-0-brightgreen)

---

## Why

Writing a good skill is fiddly: the frontmatter has to be exactly right, the `name` has to
match its directory, and the `description` — the one field an agent actually reads to
decide *whether to load the skill* — has to say **when** to trigger, inside a tight
character budget. Get any of it wrong and the skill is silently undiscoverable.

Most "ask an LLM to write my SKILL.md" approaches are non-reproducible, need an API key,
and still emit invalid frontmatter. `skill-forge` is different on two axes:

1. **Offline & deterministic by default.** It reads your source with static analysis — no
   code execution, no network, no key — and emits the skill. Same input → same output.
   The optional `--llm` flag only *refines* the prose; it never owns the structure.
2. **Valid by construction.** Every generated skill passes the built-in linter (the same
   rules a skill must satisfy to be discoverable). `skill-forge` refuses to write a skill
   that doesn't lint clean, so you never ship a broken one.

It's the *forge* half of a pair: **forge generates, `skillcheck` checks.** The linter is
bundled here too (`skill-forge lint`) so the tool stands alone.

## Install

The package is published on PyPI as **`claude-skill-forge`**; it installs a CLI named
`skill-forge` (and the import package is `skill_forge`).

```bash
pip install claude-skill-forge               # core: zero runtime dependencies
pip install 'claude-skill-forge[anthropic]'  # adds the optional --llm refiner
```

## Quickstart (30 seconds)

```bash
# From a Python/Node project, a package, or a single doc:
skill-forge forge ./my-tool                 # -> .claude/skills/my-tool/SKILL.md
skill-forge forge ./README.md               # generate from docs
skill-forge forge ./pkg --name my-skill     # override the skill name
skill-forge forge ./my-tool --stdout        # preview, don't write
skill-forge forge ./my-tool --llm           # sharpen the prose with Claude

# Validate any skill / folder of skills (the bundled checker):
skill-forge lint .claude/skills

# CI drift guard — fail if the skill no longer matches the code:
skill-forge check ./my-tool --name my-tool
```

### What it extracts

| Source | What it reads |
| --- | --- |
| **Python** | `pyproject.toml` / `setup.cfg` (name, description, keywords, `[project.scripts]`), `__all__` and public defs/classes via `ast`, and argparse / click / typer subcommands — **never importing or running your code** |
| **Node** | `package.json` (name, description, keywords, `bin`), TS/JS detection, README |
| **Docs** | A markdown/rst/txt file: H1 title, first paragraph, section headings, fenced code blocks |
| **Any directory** | README + a language histogram of the file tree |
| **A CLI tool** | `skill-forge forge --from-cli "mytool"` captures and parses `mytool --help` |

The result is a complete `SKILL.md`: trigger-oriented `description`, a `## When to use`
section, an overview, and `## Commands` / `## API` / `## Usage` sections built from what was
found.

## Use it from Python

```python
from skill_forge import forge, render_skill, write_skill

draft = forge("./my-tool")          # a validated SkillDraft
print(render_skill(draft))          # the SKILL.md text
write_skill(draft, ".claude/skills")
```

## The `--llm` refiner (optional)

`--llm` sends the *extracted signals* (not your source) to Claude to sharpen the
description's trigger phrasing and tighten the body. It is fail-safe: if the model is
unavailable it tells you how to fix it, and if its output is anything but a valid
improvement, `skill-forge` keeps the deterministic draft. You never get a worse skill than
the offline path. Set `ANTHROPIC_API_KEY` and install the extra to use it.

## CI: catch stale skills

`skill-forge check` regenerates the skill in memory and diffs it against the one on disk,
exiting non-zero if they differ — so a skill that drifted from the code it describes fails
the build:

```yaml
- run: pip install claude-skill-forge
- run: skill-forge check ./my-tool --name my-tool
```

## What this is **not**

- **Not a replacement for judgment.** Generated skills are a strong *first draft*. The body
  is assembled from your structure, not written from deep understanding — read it, trim it,
  and add the hard-won "do this, not that" guidance only you know.
- **Not a runtime.** It writes `SKILL.md` files; it does not execute skills.
- **Not magic prose.** The offline path is deterministic and a little formulaic by design.
  Reach for `--llm` when you want the description polished.
- **It does not run your code.** The only time it executes anything is the explicit
  `--from-cli` flag, which runs `<cmd> --help` with no shell and a timeout.

## Configuration

Environment overrides (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `SKILL_FORGE_OUTDIR` | `.claude/skills` | Default output directory |
| `SKILL_FORGE_VERSION` | `0.1.0` | Version stamped on generated skills |
| `SKILL_FORGE_MODEL_ID` | `claude-haiku-4-5` | Model used by `--llm` |
| `ANTHROPIC_API_KEY` | — | Required for `--llm` |

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

The design is pinned in [`SPEC.md`](SPEC.md) — the single source of truth for the public
API and behavior. See [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a PR.

## License

MIT — see [LICENSE](LICENSE).
