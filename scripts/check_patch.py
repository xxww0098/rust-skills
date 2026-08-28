#!/usr/bin/env python3
"""Mechanical write-refusals from kernel/write.md.

Scan production .rs for shapes that must not land. Tests/examples/benches skipped.

  python3 scripts/check_patch.py <file-or-dir>...
  python3 scripts/check_patch.py --check-fixtures
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RULES = (
    ("unwrap", re.compile(r"\.unwrap\s*\("), "ERR-03"),
    ("println", re.compile(r"\bprintln!\s*\("), "OBS-01"),
    ("dbg", re.compile(r"\bdbg!\s*\("), "OBS-01"),
    ("clone", re.compile(r"\.clone\s*\("), "OWN-01"),
    ("amp_string", re.compile(r"&String\b"), "OWN-02"),
    ("index_loop", re.compile(r"for\s+\w+\s+in\s+0\s*\.\."), "SIMP-13"),
)


def is_prod_rs(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if "tests" in parts or "examples" in parts or "benches" in parts:
        return False
    if path.name.endswith("_test.rs"):
        return False
    return path.suffix == ".rs"


def iter_rs(targets: list[Path]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        if t.is_file() and t.suffix == ".rs":
            out.append(t)
        elif t.is_dir():
            out.extend(p for p in t.rglob("*.rs") if is_prod_rs(p))
    return out


def scan(path: Path) -> list[str]:
    hits = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [f"{path}: {exc}"]
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("//"):
            continue
        for name, rx, rule in RULES:
            if rx.search(line):
                hits.append(f"{path}:{i}: {rule} {name}: {line.strip()}")
    return hits


def check_fixtures() -> int:
    failed = 0
    dirty = REPO_ROOT / "tests" / "fixtures" / "scene-79" / "hits.rs"
    hits = scan(dirty)
    if not hits:
        print("FAIL: scene-79/hits.rs should trip check_patch", file=sys.stderr)
        failed += 1
    clean = REPO_ROOT / "tests" / "projects" / "single-lib" / "src" / "lib.rs"
    clean_hits = scan(clean)
    if clean_hits:
        print("FAIL: single-lib should be clean:\n" + "\n".join(clean_hits), file=sys.stderr)
        failed += 1
    if failed == 0:
        print(f"OK: check_patch fixtures ({len(hits)} hits on scene-79)")
    return failed


def main() -> int:
    if "--check-fixtures" in sys.argv:
        return check_fixtures()
    args = [Path(a) for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: check_patch.py <file-or-dir>...", file=sys.stderr)
        return 2
    failed = 0
    for path in iter_rs(args):
        hits = scan(path)
        for h in hits:
            print(h, file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
