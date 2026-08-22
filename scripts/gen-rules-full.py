#!/usr/bin/env python3
"""Assemble skills/rust/rules/rules-full.md from per-domain source files.

Domain files in skills/rust/rules/*.md (except namespaces.txt and the
generated rules-full.md) are the source of truth. rules-full.md exists so
one-level scanners and doctor full-audits can still load a single document.

Usage:
  ./scripts/gen-rules-full.py           rewrite rules-full.md
  ./scripts/gen-rules-full.py --check   exit 1 if the merge drifted
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = REPO_ROOT / "skills" / "rust" / "rules"
OUT = RULES_DIR / "rules-full.md"

ORDER = [
    "preamble.md",
    "meta.md",
    "ws.md",
    "test.md",
    "err.md",
    "api.md",
    "own.md",
    "simp.md",
    "async.md",
    "unsafe.md",
    "ffi.md",
    "build.md",
    "dep.md",
    "lint.md",
    "obs.md",
    "perf.md",
    "gate.md",
    "d.md",
]


def assemble() -> str:
    chunks = []
    for name in ORDER:
        path = RULES_DIR / name
        if not path.is_file():
            raise SystemExit(f"missing rules source: {path}")
        chunks.append(path.read_text(encoding="utf-8").rstrip() + "\n")
    return "\n".join(chunks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    new = assemble()
    old = OUT.read_text(encoding="utf-8") if OUT.is_file() else None
    if old == new:
        print("OK: rules-full.md matches domain files")
        return 0
    if args.check:
        print("rules-full.md drifted from domain files; run ./scripts/gen-rules-full.py", file=sys.stderr)
        return 1
    OUT.write_text(new, encoding="utf-8")
    print("wrote skills/rust/rules/rules-full.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
