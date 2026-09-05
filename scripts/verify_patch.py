#!/usr/bin/env python3
"""Shared verification entry for every write command.

check_patch green is not proof. This script classifies Patch.verification
and only runs cargo when --run is explicit.

  python3 scripts/verify_patch.py --patch <json> --root <dir>
  python3 scripts/verify_patch.py --patch <json> --root <dir> --run --json
  python3 scripts/verify_patch.py --check-fixtures
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_patch import inspect_targets, load_patch, resolve_patch_files

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_SUB = {"check", "test", "nextest"}


def parse_verification(text: str, root: Path) -> tuple[str, list[str], Path | None, list[str]]:
    """Return (status, argv, manifest, errors)."""
    raw = text.strip()
    if not raw:
        return "gap", [], None, ["verification: empty"]
    if any(tok in raw for tok in ("&&", "||", ";", "|", "`", "$(", "\n")):
        return "invalid", [], None, ["verification: only one cargo command, no shell chaining"]
    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        return "invalid", [], None, [f"verification: cannot parse: {exc}"]
    if not tokens:
        return "gap", [], None, ["verification: empty"]
    if tokens[0] != "cargo":
        return "invalid", [], None, ["verification: must start with cargo"]
    i = 1
    if i < len(tokens) and tokens[i].startswith("+"):
        i += 1
    if i >= len(tokens) or tokens[i] not in ALLOWED_SUB:
        return "invalid", [], None, ["verification: subcommand must be check, test, or nextest"]
    manifest = None
    if "--manifest-path" not in tokens:
        return "invalid", tokens, None, ["verification: missing --manifest-path"]
    idx = tokens.index("--manifest-path")
    if idx + 1 >= len(tokens):
        return "invalid", tokens, None, ["verification: --manifest-path has no path"]
    mpath = Path(tokens[idx + 1])
    if not mpath.is_absolute():
        mpath = root / mpath
    if not mpath.is_file():
        return "missing-manifest", tokens, mpath, [f"verification: manifest not found: {mpath}"]
    return "runnable", tokens, mpath, []


def run_cargo(argv: list[str], root: Path) -> tuple[str, int, str]:
    if shutil.which("cargo") is None:
        return "cargo-missing", 127, "cargo not on PATH"
    env = os.environ.copy()
    env["CARGO_TERM_COLOR"] = "never"
    try:
        proc = subprocess.run(
            argv,
            cwd=root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        return "timeout", 124, "cargo timed out"
    text = (proc.stdout or "") + (proc.stderr or "")
    status = "ran" if proc.returncode == 0 else "failed"
    return status, proc.returncode, text[-2000:]


def evaluate(patch_path: Path, root: Path, do_run: bool) -> dict:
    doc, patch_errors = load_patch(patch_path)
    hits: list[str] = []
    scanned: list[str] = []
    skipped: list[str] = []
    if doc and isinstance(doc.get("files"), list) and doc["files"]:
        files, file_errs = resolve_patch_files(doc["files"], root)
        patch_errors.extend(file_errs)
        hits, scanned, skipped = inspect_targets(files)
    verification = str((doc or {}).get("verification", ""))
    v_status, argv, manifest, v_errors = parse_verification(verification, root)
    if patch_errors:
        v_status = "invalid"
    ran_log = ""
    code = None
    if do_run and v_status == "runnable":
        v_status, code, ran_log = run_cargo(argv, root)
    payload = {
        "ok": not patch_errors and not hits and v_status in {"runnable", "ran"},
        "patch_errors": patch_errors,
        "hits": hits,
        "scanned": scanned,
        "skipped": skipped,
        "verification_status": v_status,
        "verification_errors": v_errors,
        "command": argv,
        "manifest": str(manifest) if manifest else None,
        "exit_code": code,
        "proven": v_status == "ran",
    }
    if ran_log:
        payload["cargo_tail"] = ran_log
    return payload


def check_fixtures() -> int:
    failed = 0
    refuse = evaluate(
        REPO_ROOT / "tests" / "fixtures" / "scene-79" / "patch-refuse.json",
        REPO_ROOT,
        do_run=False,
    )
    if refuse["verification_status"] != "invalid":
        print(f"FAIL: refuse should be invalid, got {refuse['verification_status']}", file=sys.stderr)
        failed += 1
    if refuse["proven"]:
        print("FAIL: refuse must not be proven", file=sys.stderr)
        failed += 1
    ok = evaluate(
        REPO_ROOT / "tests" / "fixtures" / "scene-79" / "patch-ok.json",
        REPO_ROOT,
        do_run=False,
    )
    if ok["verification_status"] != "runnable":
        print(f"FAIL: ok should be runnable, got {ok}", file=sys.stderr)
        failed += 1
    if ok["proven"]:
        print("FAIL: dry classify must not set proven", file=sys.stderr)
        failed += 1
    if failed == 0:
        print("OK: verify_patch fixtures (refuse invalid, ok runnable, neither proven)")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check-fixtures", action="store_true")
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--run", action="store_true", help="actually execute cargo; default only classifies")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.check_fixtures:
        return check_fixtures()
    if not args.patch:
        print("usage: verify_patch.py --patch <json> --root <dir> [--run]", file=sys.stderr)
        return 2
    root = args.root.resolve() if args.root else Path.cwd()
    payload = evaluate(args.patch, root, args.run)
    if args.json:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for err in payload["patch_errors"] + payload["verification_errors"]:
            print(err, file=sys.stderr)
        for hit in payload["hits"]:
            print(hit, file=sys.stderr)
        print(
            f"verification_status={payload['verification_status']} proven={payload['proven']}",
            file=sys.stderr if not payload["ok"] else sys.stdout,
        )
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
