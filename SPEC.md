# skill-forge — Canonical Build Spec (single source of truth)

> Every builder reads THIS file and implements exactly the signatures, names, and
> behaviors below. Do not invent extra public API. Match names character-for-character.
> When in doubt, prefer fewer moving parts and **stdlib over dependencies**.

## What it is (positioning)

A CLI that turns a **codebase, package, or doc** into a well-formed Claude
**`SKILL.md`** skill — and that skill is **valid by construction**. Two ideas no
existing "AI writes your skill" tool combines:

1. **Offline & deterministic by default.** `skill-forge forge ./my-tool` reads the
   source with static analysis (no code execution, no network, no API key) and emits a
   complete `SKILL.md`. Same input → same output. The optional `--llm` flag only
   *refines* the prose; it never owns the structure.
2. **Valid by construction.** Every generated skill passes the built-in linter
   (`skill-forge lint`) — the same rules a skill must satisfy to be discoverable:
   well-formed frontmatter, kebab-case `name` that matches its directory, a
   `description` inside the discovery budget (40–1024 chars), a `metadata.version`, and a
   non-empty body. Forge that emits an invalid skill is worthless, so validation runs on
   every generated draft and the CLI refuses to write garbage.

Plus a **drift check** (`skill-forge check`) that regenerates and diffs against an
existing skill — a CI guard that catches a skill gone stale versus the code it
describes — and **portable output** (plain `SKILL.md`, works in Claude Code, Cursor,
Cline, and any agent that reads skills).

It is the *forge* half of a pair: **forge generates, `skillcheck` checks.** The linter
here is bundled so the tool stands alone, and its rules are kept identical to the
standalone checker.

Tagline: *"Point it at your code. Get a valid Claude skill. No API key required."*

## Package layout

```
skill_forge/
  __init__.py            # public exports (see below) + __version__
  errors.py              # exception types
  models.py              # Command, SourceSignals, SkillDraft (pure dataclasses)
  config.py              # Settings (plain dataclass, env SKILL_FORGE_*; no pydantic)
  slug.py                # slugify(), is_kebab_case()
  frontmatter.py         # render_frontmatter(), parse_frontmatter() (flat scalars, stdlib)
  describe.py            # build_description(signals) — the trigger-oriented description
  templates.py           # build_body(signals) — the deterministic markdown body
  generate.py            # forge(source, ...) -> SkillDraft  (analyze -> draft -> validate)
  skill.py               # render_skill(draft) -> str ; write_skill(draft, outdir) -> Path
  validate.py            # Problem, LintResult, lint_text/lint_skill_file/lint_path
  llm.py                 # refine_with_llm(...) optional Claude refinement (lazy anthropic)
  analyzers/
    __init__.py          # analyze(source, kind=None) -> SourceSignals ; detect()
    base.py              # Analyzer protocol + shared text helpers
    python.py            # PythonAnalyzer (ast + pyproject; NO exec)
    node.py              # NodeAnalyzer (package.json + README)
    docs.py              # DocsAnalyzer (markdown/rst/txt headings + code blocks)
    generic.py           # GenericAnalyzer (dir name + README + file histogram)
    cli_help.py          # capture_cli_help(cmd) -> SourceSignals (explicit opt-in only)
  cli.py                 # `skill-forge` entry point (argparse, stdlib)
tests/                   # pytest; everything offline, no network, no anthropic needed
examples/                # runnable demos
```

PyPI distribution name `claude-skill-forge` (the bare `skill-forge` was blocked by PyPI's
name-similarity guard); CLI command `skill-forge`; import package `skill_forge`. Python >=3.10.
License MIT (holder: "Shaxzodbek Qambaraliyev / Blaze"). **Zero runtime dependencies** for the
core; `anthropic` is the only optional extra (for `--llm`).

## Core types & exact signatures

### errors.py
```python
class SkillForgeError(Exception): ...
class SourceNotFound(SkillForgeError):
    """The given source path/command does not exist or cannot be read."""
class AnalyzerError(SkillForgeError):
    """An analyzer could not extract usable signals from the source."""
class InvalidSkill(SkillForgeError):
    """A draft failed validation and cannot be written."""
class LLMUnavailable(SkillForgeError):
    """--llm was requested but the optional `anthropic` extra / API key is missing."""
```

### models.py
```python
@dataclass(frozen=True)
class Command:
    name: str
    help: str = ""

@dataclass
class SourceSignals:
    name: str                                   # raw source name (pre-slug)
    summary: str = ""                           # one-line "what it is"
    kind: str = "generic"                       # producing analyzer: python|node|docs|generic|cli
    language: str | None = None                 # "Python", "JavaScript", ...
    install: str | None = None                  # e.g. "pip install foo"
    homepage: str | None = None
    commands: list[Command] = field(default_factory=list)
    api: list[str] = field(default_factory=list)        # public symbols / exports
    usage: list[str] = field(default_factory=list)      # fenced code snippets
    keywords: list[str] = field(default_factory=list)   # trigger seeds
    notes: list[str] = field(default_factory=list)      # extra body bullets (doc sections)
    source: str = ""                            # path/desc the signals came from

@dataclass
class SkillDraft:
    name: str                                   # kebab-case; equals output dir name
    description: str                            # 40..1024 chars, trigger-oriented
    body: str                                   # markdown body (no frontmatter)
    version: str = "0.1.0"
    license: str | None = None
    signals: SourceSignals | None = None        # provenance (not serialized)
```

### config.py
```python
@dataclass
class Settings:
    anthropic_api_key_env: str = "ANTHROPIC_API_KEY"
    model_id: str = "claude-haiku-4-5"          # cheap refiner default
    default_outdir: str = ".claude/skills"      # where skills live for Claude Code
    default_version: str = "0.1.0"
    max_description: int = 1024
    min_description: int = 40

    @classmethod
    def from_env(cls) -> "Settings":
        """Read SKILL_FORGE_* env overrides (SKILL_FORGE_MODEL_ID, SKILL_FORGE_OUTDIR,
        SKILL_FORGE_VERSION). Plain os.environ; no pydantic."""
```

### slug.py
```python
def slugify(text: str) -> str:
    """Lowercase, ASCII, words joined by single hyphens; strips a leading scope like
    '@org/' and common suffixes are kept. Guarantees is_kebab_case() on the result, or
    raises ValueError if nothing usable remains."""
def is_kebab_case(name: str) -> bool:    # ^[a-z0-9]+(-[a-z0-9]+)*$
```

### frontmatter.py  (stdlib only — no PyYAML)
```python
def render_frontmatter(fields: dict[str, str]) -> str:
    """Render flat `key: value` scalars between `---` lines. Insertion order preserved.
    A value is quoted (double) iff it contains a character that would break the flat
    parser (':', '#', leading/trailing space, or starts with a quote). Skips None/empty."""
def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a SKILL.md string into (frontmatter dict, body). Mirrors the reference PHP
    linter: frontmatter must be the very first thing, open and close with `---` on their
    own lines, flat `key: value` scalars only, one layer of matching quotes stripped.
    Returns ({}, text) when there is no well-formed frontmatter."""
```

### describe.py — the crown jewel
```python
def build_description(signals: SourceSignals, *, settings: Settings | None = None) -> str:
    """Deterministically compose a trigger-oriented description from signals:
      - opens with what it is ("Use when working with {name} — {summary}."),
      - states capability from commands/api,
      - lists explicit trigger phrases from keywords + command names ("Trigger when the
        user mentions ... or wants to ..."), deliberately a little 'pushy' (per skill
        authoring guidance: descriptions under-trigger by default),
      - clamps to settings.max_description (cut on a sentence/word boundary, never mid-word),
      - pads to >= settings.min_description if too thin.
    Pure; no I/O."""
```

### templates.py
```python
def build_body(signals: SourceSignals) -> str:
    """Assemble the markdown body (no frontmatter): H1 title, summary, a '## When to use'
    section (signal-driven bullets — one per command, else per API symbol, plus a
    'Trigger phrases:' line from keywords), '## Overview' (language/install/homepage),
    '## Commands' (if any), '## API' (if any), '## Usage' (fenced snippets, per-snippet
    language detection), '## Related topics' (filtered, de-boilerplated doc sections),
    and a trailing provenance line '> Generated by skill-forge from `{source}`. Review
    before publishing.' Imperative voice. Stays well under 500 lines. Pure."""
```

### validate.py  (the bundled linter — rules identical to the reference PHP checker)
```python
@dataclass(frozen=True)
class Problem:
    field: str
    message: str
    severity: str = "error"     # "error" | "warning"

@dataclass
class LintResult:
    name: str
    path: str | None
    problems: list[Problem]
    @property
    def ok(self) -> bool:       # no error-severity problems
    @property
    def errors(self) -> list[Problem]: ...
    @property
    def warnings(self) -> list[Problem]: ...

DESCRIPTION_MIN = 40
DESCRIPTION_MAX = 1024

def lint_text(text: str, *, dir_name: str | None = None) -> list[Problem]:
    """Validate a SKILL.md string. Checks, matching the reference linter:
      - frontmatter present + well-formed (else single error, stop),
      - name present, kebab-case, and == dir_name when dir_name given,
      - description present and DESCRIPTION_MIN..DESCRIPTION_MAX chars,
      - version is optional and NOT a recognized top-level field — a top-level `version`
        is a placement warning ("move under metadata"); if present it must be semver-like,
      - body below frontmatter non-empty."""
def lint_skill_file(path: str | Path) -> LintResult:
    """Lint a single SKILL.md; dir_name inferred from the parent directory."""
def lint_path(path: str | Path) -> list[LintResult]:
    """Accept a SKILL.md file, a single skill dir, or a skills/ root (globs */SKILL.md).
    Raises SourceNotFound if nothing matches."""
```

### generate.py
```python
def forge(source: str | Path, *, name: str | None = None, kind: str | None = None,
          llm: bool = False, settings: Settings | None = None) -> SkillDraft:
    """analyze(source, kind) -> SourceSignals; build_description + build_body -> SkillDraft;
    if llm: refine_with_llm (best-effort, falls back to deterministic draft on any failure);
    validate the final draft (raise InvalidSkill on error-severity problems); return it.
    `name` overrides the slug; otherwise slugify(signals.name)."""

def draft_from_signals(signals: SourceSignals, *, name: str | None = None,
                       settings: Settings | None = None) -> SkillDraft:
    """Pure deterministic draft (no LLM). Used by forge() and directly testable."""
```

### skill.py
```python
def render_skill(draft: SkillDraft) -> str:
    """Full SKILL.md text: render_frontmatter({name, description, license?, metadata:{version}}) +
    blank line + draft.body + trailing newline."""
def write_skill(draft: SkillDraft, outdir: str | Path, *, force: bool = False) -> Path:
    """Write render_skill(draft) to <outdir>/<draft.name>/SKILL.md. Creates parents.
    Refuses to overwrite an existing SKILL.md unless force=True (raise SkillForgeError).
    The skill name is slug-validated, so the join cannot escape outdir. Returns the path."""
```

### llm.py  (optional; never required for the deterministic path)
```python
def refine_with_llm(draft: SkillDraft, signals: SourceSignals,
                    settings: Settings | None = None) -> SkillDraft:
    """Lazy `import anthropic`; missing -> LLMUnavailable("pip install 'skill-forge[anthropic]'").
    Missing API key -> LLMUnavailable. Ask the model (settings.model_id) to return JSON
    {"description": ..., "body": ...} that sharpens triggers and tightens prose given the
    signals. Re-validate the merged draft; if the model's output is invalid or unparseable,
    return the original deterministic draft unchanged (fail-safe, never worse)."""
```

### analyzers/__init__.py
```python
def detect(source: str | Path) -> str:
    """Return analyzer kind for a path: a docs file (.md/.markdown/.rst/.txt) -> 'docs';
    a dir with pyproject.toml/setup.py/setup.cfg or *.py -> 'python'; a dir with
    package.json -> 'node'; otherwise 'generic'. Raises SourceNotFound if the path is absent."""
def analyze(source: str | Path, *, kind: str | None = None) -> SourceSignals:
    """Dispatch to the matching analyzer (forced kind or detect()). Raises AnalyzerError
    if the chosen analyzer yields nothing usable (e.g. empty dir, no name)."""
```
`cli_help.capture_cli_help(command: str, *, timeout: float = 10.0) -> SourceSignals` is
**not** part of detect()/analyze(); it is invoked only by the CLI's explicit `--from-cli`
flag. It runs `shlex.split(command)` (no shell), captures `--help`, parses usage/options
into commands+notes. Timeout-guarded; any failure -> AnalyzerError.

### cli.py — entry point `skill-forge` (argparse, no extra dep)
Subcommands:
- `forge <source>` — generate and write a skill.
  Flags: `-o/--outdir` (default Settings.default_outdir), `--name`, `--kind {python,node,docs,generic}`,
  `--from-cli "<cmd>"` (capture a CLI tool's `--help` instead of reading `<source>`; `<source>` optional then),
  `--llm`, `--stdout` (print, do not write), `--force` (overwrite), `--version-str` (skill version).
  On write: print the path and a one-line lint verdict. On `--stdout`: print the SKILL.md.
- `lint <path>` — run the bundled linter; print per-skill ✓/✗ with problems; exit 1 on any error.
- `check <source>` — regenerate in memory and diff against the existing skill at
  `<outdir>/<name>/SKILL.md`; print a unified diff; exit 1 if they differ (CI drift guard).
- `version` — print `skill-forge {__version__}`.
Exit non-zero with a clean one-line message on any SkillForgeError. No traceback for known errors.

### __init__.py exports
`forge, draft_from_signals, SkillDraft, SourceSignals, Command, Settings,
render_skill, write_skill, analyze, detect, build_description, build_body,
lint_text, lint_skill_file, lint_path, LintResult, Problem,
slugify, is_kebab_case, refine_with_llm,
SkillForgeError, SourceNotFound, AnalyzerError, InvalidSkill, LLMUnavailable`.
Define `__version__ = "0.1.0"`.

## Tests (pytest) — MUST pass offline (no network, no anthropic installed)
1. `test_slug`: slugify handles spaces, scopes (`@org/pkg`), camelCase, dots; rejects empty.
2. `test_frontmatter_roundtrip`: render then parse returns the same flat fields + body;
   values needing quoting (containing ':') survive a round trip.
3. `test_validate_rules`: each rule fires — missing/blank name, non-kebab name, name≠dir,
   description too short / too long, missing version (warning), empty body, malformed
   frontmatter. A known-good skill produces zero errors. **Boundaries 40 and 1024 exact.**
4. `test_describe_budget`: build_description never exceeds max, never below min, ends clean
   (no mid-word cut), and includes at least one command/keyword trigger when present.
5. `test_python_analyzer`: on a temp package (pyproject + `__init__` with `__all__` + a
   click/argparse subcommand) extracts name, summary, api, at least one command, keywords.
6. `test_docs_analyzer`: on a temp README.md extracts H1 as name, first paragraph as
   summary, H2s as notes, fenced blocks as usage.
7. `test_node_analyzer`: on a temp package.json extracts name, description, bin commands, keywords.
8. `test_generic_analyzer`: on a temp dir with assorted files guesses a language and a name.
9. `test_forge_valid_by_construction`: forge() on each fixture yields a draft whose
   render_skill() passes lint_text(dir_name=draft.name) with **zero errors**. Headline test.
10. `test_write_skill`: writes `<out>/<name>/SKILL.md`; refuses overwrite without force;
    path stays inside outdir; force overwrites.
11. `test_cli_forge_stdout` + `test_cli_lint` + `test_cli_check`: invoke `main([...])`
    in-process; forge --stdout prints valid frontmatter; lint exits 0 on good / 1 on bad;
    check exits 0 when in sync, 1 after a tweak.
12. `test_llm_optional`: refine_with_llm with anthropic absent raises LLMUnavailable; the
    deterministic forge() path never imports anthropic.
Aim >90% coverage of slug/frontmatter/validate/describe/templates/generate/skill and each
analyzer. llm.py covered by the lazy-error test only.

## Quality bar
- Ruff-clean (line length 100, `select = ["E","F","I","UP","B"]`), type hints throughout,
  docstrings on public API.
- **Zero network and zero code execution** in analyze()/forge(). The Python analyzer uses
  `ast` only — it never imports or runs the target. `--from-cli` is the single exception
  and is explicit, no-shell, timeout-guarded.
- No secrets. The deterministic path imports no third-party package.
- Generated skills always pass the bundled linter — assert it in tests, not just by hope.
- README: positioning, the two guarantees, a 30-second quickstart, the `--llm` note, a
  comparison vs "ask an LLM to write a SKILL.md", a `check` (CI drift) example, and an
  honest "what this is NOT" section. Accurate to the actual code.
```
