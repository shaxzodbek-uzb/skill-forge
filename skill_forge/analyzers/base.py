"""Shared, dependency-free helpers for the analyzers.

Everything here is pure text processing over files already on disk — no network, no code
execution.
"""

from __future__ import annotations

import re
from pathlib import Path

README_NAMES = [
    "README.md",
    "README.markdown",
    "README.rst",
    "README.txt",
    "README",
    "readme.md",
]

EXT_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".java": "Java",
    ".kt": "Kotlin",
    ".sh": "Shell",
    ".c": "C",
    ".cpp": "C++",
    ".cs": "C#",
}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "to", "of", "in", "on", "is", "are",
    "your", "you", "this", "that", "it", "as", "by", "be", "can", "from", "into", "via",
    "using", "use", "used", "uses", "any", "all", "not", "no", "yes", "tool", "library",
    "package", "project", "simple", "easy", "fast", "small", "based",
    # Low-signal filler that tends to leak from prose summaries / headings.
    "single", "source", "truth", "turns", "point", "required", "valid", "canonical",
    "well", "formed", "make", "makes", "made", "just", "also", "new", "one", "first",
    "more", "most", "very", "really", "over", "get", "gets", "why", "out", "only",
    "such", "when", "what", "how", "we", "us", "its", "their",
}

# Headings that are structural/boilerplate, not real topics worth surfacing as triggers.
STOP_HEADINGS = {
    "install", "installation", "license", "licence", "contributing", "contribution",
    "development", "configuration", "config", "why", "table of contents", "contents",
    "changelog", "acknowledgements", "acknowledgments", "badges", "usage", "notes",
    "getting started", "quickstart", "quick start", "overview", "requirements",
    "features", "faq", "support", "credits", "authors", "roadmap", "todo", "examples",
}

_MD_MARKUP_RE = re.compile(r"[`*_]+")


def strip_markdown(text: str) -> str:
    """Remove inline emphasis/code markers and leading heading hashes; collapse whitespace."""
    cleaned = _MD_MARKUP_RE.sub("", text or "")
    cleaned = re.sub(r"^#+\s*", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def clean_section_titles(titles: list[str]) -> list[str]:
    """Strip markup and drop boilerplate/duplicate section headings (for the Notes list)."""
    out: list[str] = []
    seen: set[str] = set()
    for title in titles:
        cleaned = strip_markdown(title)
        key = cleaned.lower()
        if not cleaned or key in STOP_HEADINGS or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{1,}")


def read_text(path: str | Path) -> str:
    """Read a file as UTF-8, ignoring undecodable bytes; '' if unreadable."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def find_readme(directory: str | Path) -> Path | None:
    """Return the first README-like file in ``directory``, or None."""
    d = Path(directory)
    for name in README_NAMES:
        candidate = d / name
        if candidate.is_file():
            return candidate
    return None


def _is_noise(line: str) -> bool:
    """True for lines that should not seed a prose summary (badges, images, HTML, tables)."""
    return (
        line.startswith("![")
        or line.startswith("[![")
        or line.startswith("<")
        or line.startswith("|")
        or line.startswith(">")
        or bool(re.fullmatch(r"[-=*_]{3,}", line))
    )


def parse_markdown(text: str) -> dict:
    """Extract ``title``, ``summary``, ``headings`` (list of (level, text)), and
    ``code_blocks`` (fenced block bodies) from markdown-ish text."""
    title = ""
    summary = ""
    summary_done = False
    headings: list[tuple[int, str]] = []
    code_blocks: list[str] = []
    para: list[str] = []
    in_code = False
    buf: list[str] = []

    def flush_para() -> None:
        nonlocal summary, summary_done
        if para and not summary_done:
            summary = " ".join(para).strip()
            summary_done = True
        para.clear()

    for line in text.splitlines():
        if _FENCE_RE.match(line):
            if in_code:
                code_blocks.append("\n".join(buf))
                buf = []
            in_code = not in_code
            continue
        if in_code:
            buf.append(line)
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            htext = heading.group(2).strip()
            if level == 1 and not title:
                title = htext
            headings.append((level, htext))
            flush_para()
            continue

        stripped = line.strip()
        if stripped == "":
            flush_para()
            continue
        if not summary_done and not _is_noise(stripped):
            para.append(stripped)

    if buf:
        code_blocks.append("\n".join(buf))
    flush_para()
    return {"title": title, "summary": summary, "headings": headings, "code_blocks": code_blocks}


def tokenize_keywords(*texts: str, limit: int = 12) -> list[str]:
    """Pull distinct lowercase keyword tokens from free text, dropping stopwords."""
    out: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in _WORD_RE.findall(text or ""):
            token = match.lower()
            if token in _STOPWORDS or token in seen or len(token) < 3:
                continue
            seen.add(token)
            out.append(token)
            if len(out) >= limit:
                return out
    return out


def guess_language(directory: str | Path) -> str | None:
    """Guess the dominant language of a directory from its file extensions."""
    skip = {".git", "node_modules", ".venv", "venv", "dist", "build"}
    counts: dict[str, int] = {}
    for path in Path(directory).rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        lang = EXT_LANGUAGE.get(path.suffix)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])
