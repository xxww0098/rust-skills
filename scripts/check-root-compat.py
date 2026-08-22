#!/usr/bin/env python3
"""Fail if the pack root is not a one-level skill directory."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    "SKILL.md": "skills/rust/SKILL.md",
    "reference": "skills/rust/reference",
    "rules": "skills/rust/rules",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)


def _file_equal(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()


def _tree_equal(a: Path, b: Path) -> bool:
    if a.is_file() and b.is_file():
        return _file_equal(a, b)
    if not a.is_dir() or not b.is_dir():
        return False
    a_files = {p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file()}
    b_files = {p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file()}
    if a_files != b_files:
        return False
    return all(_file_equal(a / rel, b / rel) for rel in a_files)


def main() -> int:
    failed = False
    for name, target in EXPECTED.items():
        path = REPO_ROOT / name
        want = (REPO_ROOT / target).resolve()
        if path.is_symlink():
            actual = os.readlink(path)
            if actual != target:
                fail(f"{name} should link to {target} (got {actual})")
                failed = True
                continue
        elif not path.exists():
            fail(f"missing root {name} (needed by one-level harness scanners)")
            failed = True
            continue
        else:
            # Real copy is OK when the filesystem cannot host symlinks (Grok sandboxes).
            if not _tree_equal(path.resolve(), want):
                fail(f"root {name} is not a symlink to {target} and content does not match")
                failed = True
                continue
        if name == "SKILL.md":
            text = path.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            fm = parts[1] if len(parts) >= 3 else ""
            if not text.startswith("---") or "name:" not in fm or "description:" not in fm:
                fail("root SKILL.md is missing required frontmatter name/description")
                failed = True
        elif name == "reference" and not (path / "engage.md").is_file():
            fail("root reference/engage.md missing")
            failed = True
        elif name == "rules" and not (path / "rules-full.md").is_file():
            fail("root rules/rules-full.md missing")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
