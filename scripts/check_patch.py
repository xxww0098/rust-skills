#!/usr/bin/env python3
"""Mechanical write-refusals from kernel/write.md.

Scan production .rs for shapes that must not land. Tests/examples/benches,
build.rs, *_test.rs, comments, strings, and #[cfg(test)] items are not facts.

  python3 scripts/check_patch.py <file-or-dir>...
  python3 scripts/check_patch.py --check-fixtures
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rs_scan import PATCH_RULES, iter_prod_rs, scan_rules

REPO_ROOT = Path(__file__).resolve().parent.parent


def scan(path: Path) -> list[str]:
    hits = []
    for lineno, name, rule, src in scan_rules(path, PATCH_RULES):
        hits.append(f"{path}:{lineno}: {rule} {name}: {src}")
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
    noise = REPO_ROOT / "tests" / "projects" / "signal-noise"
    if noise.is_dir():
        test_file = noise / "tests" / "integration.rs"
        if test_file.is_file() and iter_prod_rs([test_file]):
            print("FAIL: direct tests/integration.rs must be excluded", file=sys.stderr)
            failed += 1
        if (noise / "build.rs").is_file() and iter_prod_rs([noise / "build.rs"]):
            print("FAIL: build.rs must be excluded", file=sys.stderr)
            failed += 1
        prod_hits = []
        for path in iter_prod_rs([noise]):
            prod_hits.extend(scan(path))
        if not any("unwrap" in h for h in prod_hits):
            print("FAIL: signal-noise production unwrap missing:\n" + "\n".join(prod_hits), file=sys.stderr)
            failed += 1
        leaked = [h for h in prod_hits if "src/lib.rs" not in str(h)]
        if leaked:
            print("FAIL: non-prod leak in check_patch:\n" + "\n".join(leaked), file=sys.stderr)
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
    for path in iter_prod_rs(args):
        hits = scan(path)
        for h in hits:
            print(h, file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
