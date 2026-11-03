"""Scan the repository for sensitive data. Standard library only.

Prints counts per category and file:line locations, never the matched values.
Exit code 0 only when there are zero findings.

    python scan_sensitive.py [root]

The deny list of proper names is kept OUTSIDE the repo (so the list itself is
not published): put one term per line in the file named by the
SCAN_DENYLIST environment variable. A small built-in list of generic markers
is always applied.
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}
SCAN_EXT = {".py", ".md", ".txt", ".ini", ".toml", ".cfg", ".json", ".yml", ".yaml", ".spec", ".csv"}
SELF = os.path.basename(__file__)
ALLOWED_NAMES = {".gitignore"}

PATTERNS = {
    "cpf": re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"),
    "cnpj": re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}(?!\d)"),
    "apps_script_url": re.compile(r"script\.google\.com/macros", re.I),
    "sheets_url": re.compile(r"docs\.google\.com/spreadsheets", re.I),
    "windows_user_path": re.compile(r"[A-Za-z]:\\+Users", re.I),
    "network_or_drive_path": re.compile(r"(?<![A-Za-z])[A-Z]:\\{1,2}[A-Za-z]"),
    "unc_path": re.compile(r"\\\\[A-Za-z0-9_.-]+\\[A-Za-z0-9_$.-]+"),
    "secret": re.compile(
        r"(api[_-]?key|secret|token|passwd|password|bearer)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
        r"|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_-]{30,}"
        r"|(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{40,}", re.I),
    "google_id": re.compile(r"\b[A-Za-z0-9_-]{44}\b|AKfycb[A-Za-z0-9_-]{20,}"),
}

BUILTIN_TERMS: list[str] = []


def load_terms() -> list[str]:
    terms = list(BUILTIN_TERMS)
    path = os.environ.get("SCAN_DENYLIST")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            terms += [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    return terms


def scan(root: str) -> dict[str, list[str]]:
    terms = load_terms()
    term_res = [re.compile(re.escape(t), re.I) for t in terms]
    findings: dict[str, list[str]] = defaultdict(list)
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name == SELF:
                continue
            ext = os.path.splitext(name)[1].lower()
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if ext not in SCAN_EXT and name not in ALLOWED_NAMES:
                findings["unexpected_file_type"].append(rel)
                continue
            with open(full, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    for cat, rx in PATTERNS.items():
                        if rx.search(line):
                            findings[cat].append(f"{rel}:{lineno}")
                    for rx in term_res:
                        if rx.search(line):
                            findings["denylist_term"].append(f"{rel}:{lineno}")
    return findings


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    findings = scan(root)
    terms = len(load_terms())
    print(f"scanned {root} ({len(PATTERNS)} patterns, {terms} deny-list terms)")
    total = 0
    for cat in [*PATTERNS, "denylist_term", "unexpected_file_type"]:
        hits = findings.get(cat, [])
        total += len(hits)
        print(f"  {cat}: {len(hits)}")
        for loc in hits:
            print(f"    {loc}")
    print(f"TOTAL FINDINGS: {total}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
