#!/usr/bin/env python3
"""Mechanical write-refusals from kernel/write.md.

A patch check is a Patch contract plus production-code shapes on Patch.files.
Comments, strings, #[cfg(test)] items, tests/examples/benches, build.rs and
*_test.rs are not facts. Passing a directory without --patch is a scope error:
that is an audit, not a patch check.

  python3 scripts/check_patch.py --patch <patch.json> [--root <dir>]
  python3 scripts/check_patch.py --patch <patch.json> --json
  python3 scripts/check_patch.py --check-fixtures
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rs_scan import PATCH_RULES, is_prod_rs, iter_prod_rs, scan_rules

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED = (
    "intent",
    "finding_id",
    "owner_layer",
    "files",
    "invariant",
    "shape",
    "refused",
    "verification",
)
CARGO_CMD_RE = re.compile(r"\bcargo(?:\s+\+[\w.\-]+)?\s+(?:check|test|nextest)\b")
MANIFEST_RE = re.compile(r"--manifest-path\b")


def scan(path: Path) -> list[str]:
    hits = []
    for lineno, name, rule, src in scan_rules(path, PATCH_RULES):
        hits.append(f"{path}:{lineno}: {rule} {name}: {src}")
    return hits


def load_patch(path: Path) -> tuple[dict | None, list[str]]:
    errors = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"patch: cannot read {path}: {exc}"]
    if not isinstance(data, dict):
        return None, ["patch: document must be a JSON object"]
    for key in REQUIRED:
        if key not in data:
            errors.append(f"patch: missing field {key}")
    if errors:
        return data, errors
    for key in REQUIRED:
        if key == "files":
            continue
        if not str(data.get(key, "")).strip():
            errors.append(f"patch: empty field {key}")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        errors.append("patch: files must be a non-empty array")
    elif any(not str(item).strip() for item in files):
        errors.append("patch: files contains an empty path")
    verification = str(data.get("verification", ""))
    if verification.strip():
        if not CARGO_CMD_RE.search(verification):
            errors.append("patch: verification must name cargo check, cargo test, or cargo nextest")
        if not MANIFEST_RE.search(verification):
            errors.append("patch: verification must pin --manifest-path")
    return data, errors


def resolve_patch_files(files: list, root: Path) -> tuple[list[Path], list[str]]:
    resolved: list[Path] = []
    errors: list[str] = []
    for raw in files:
        path = Path(str(raw))
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            errors.append(f"patch: missing file {raw}")
            continue
        resolved.append(path)
    return resolved, errors


def inspect_targets(targets: list[Path]) -> tuple[list[str], list[str], list[str]]:
    hits: list[str] = []
    scanned: list[str] = []
    skipped: list[str] = []
    for path in targets:
        if path.is_dir():
            skipped.append(f"{path}: directory is not a patch file")
            continue
        if path.suffix != ".rs":
            skipped.append(str(path))
            continue
        if not is_prod_rs(path):
            skipped.append(str(path))
            continue
        scanned.append(str(path))
        hits.extend(scan(path))
    return hits, scanned, skipped


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

    scene = REPO_ROOT / "tests" / "fixtures" / "scene-79"
    _doc, refuse_errs = load_patch(scene / "patch-refuse.json")
    if not refuse_errs:
        print("FAIL: patch-refuse.json should fail the Patch contract", file=sys.stderr)
        failed += 1
    ok_doc, ok_errs = load_patch(scene / "patch-ok.json")
    if ok_errs:
        print("FAIL: patch-ok.json contract:\n" + "\n".join(ok_errs), file=sys.stderr)
        failed += 1
    elif ok_doc:
        files, file_errs = resolve_patch_files(ok_doc["files"], REPO_ROOT)
        shape_hits, scanned, _skipped = inspect_targets(files)
        if file_errs or shape_hits or not scanned:
            print(
                "FAIL: patch-ok.json should scan clean production files:\n"
                + "\n".join(file_errs + shape_hits),
                file=sys.stderr,
            )
            failed += 1
    if failed == 0:
        print(f"OK: check_patch fixtures ({len(hits)} hits on scene-79)")
    return failed


def report(payload: dict, as_json: bool) -> int:
    if as_json:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for err in payload["patch_errors"]:
            print(err, file=sys.stderr)
        for hit in payload["hits"]:
            print(hit, file=sys.stderr)
        if payload["ok"]:
            scanned = ", ".join(payload["scanned"]) or "(no production .rs)"
            print(f"OK: patch shapes clean ({scanned})")
    return 0 if payload["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check-fixtures", action="store_true")
    parser.add_argument("--patch", type=Path, help="Patch JSON (kernel/write.md contract)")
    parser.add_argument("--root", type=Path, default=None, help="Resolve Patch.files from this directory")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("targets", nargs="*", type=Path)
    args = parser.parse_args()
    if args.check_fixtures:
        return check_fixtures()

    patch_errors: list[str] = []
    hits: list[str] = []
    scanned: list[str] = []
    skipped: list[str] = []
    root = args.root.resolve() if args.root else Path.cwd()

    if args.patch:
        doc, patch_errors = load_patch(args.patch)
        if doc and "files" in doc and isinstance(doc["files"], list) and doc["files"]:
            files, file_errs = resolve_patch_files(doc["files"], root)
            patch_errors.extend(file_errs)
            more_hits, scanned, skipped = inspect_targets(files)
            hits.extend(more_hits)
        if args.targets:
            patch_errors.append("patch: extra path arguments are ignored; only Patch.files are facts")
    elif args.targets:
        if any(t.is_dir() for t in args.targets):
            patch_errors.append(
                "patch: a directory is not a Patch; pass --patch <json> or explicit Patch.files"
            )
        else:
            more_hits, scanned, skipped = inspect_targets(args.targets)
            hits.extend(more_hits)
    else:
        print("usage: check_patch.py --patch <patch.json> | <file>...", file=sys.stderr)
        return 2

    payload = {
        "ok": not patch_errors and not hits,
        "patch_errors": patch_errors,
        "hits": hits,
        "scanned": scanned,
        "skipped": skipped,
    }
    return report(payload, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
