"""Find references to template slugs across code, tests and docs.

Used while the registry is trimmed: every hard-coded slug (a picker default, a test
fixture, a doc table) has to be checked when templates are retired. The slug list is
read from the registry plus the retirement map, so this stays correct as the library
changes.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.templates import BUILTIN_TEMPLATES, RETIRED_TEMPLATES  # noqa: E402

SLUGS = sorted(set(BUILTIN_TEMPLATES) | set(RETIRED_TEMPLATES))
SKIP_DIRS = {"node_modules", ".venv", ".git", "__pycache__", "dist", "tmp", "shots", "template-previews", "template_previews", ".pnpm-store", ".pytest_cache"}
SKIP_SUFFIXES = {".png", ".jpg", ".map", ".lock", ".tsbuildinfo", ".db", ".html", ".cmd"}

pattern = re.compile(r"[\"'](" + "|".join(SLUGS) + r")[\"']")


def main() -> None:
    hits: dict[str, list[str]] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix in SKIP_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for slug in pattern.findall(line):
                hits.setdefault(slug, []).append(f"{path.relative_to(ROOT)}:{i}")
    for slug in SLUGS:
        where = hits.get(slug, [])
        retired = "  (已退役)" if slug in RETIRED_TEMPLATES else ""
        print(f"{slug:<12}{len(where):<4}{' '.join(where[:6])}{' …' if len(where) > 6 else ''}{retired}")


if __name__ == "__main__":
    main()
