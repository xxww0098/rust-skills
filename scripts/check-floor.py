#!/usr/bin/env python3
"""Keep playbook version pins from rotting.

scripts/version-floor.json is the offline source of truth for edition/MSRV
and the framework lines quoted as 现行稳定线. This script:

  1. Asserts those strings still appear in the named playbooks.
  2. Asserts 现行稳定线 in those files matches the floor's stable_line.
  3. With --fetch, compares crates.io max_version (network optional).

A newer patch on crates.io is a warning; a different major.minor is a failure.

  ./scripts/check-floor.py            offline pins
  ./scripts/check-floor.py --fetch    also hit crates.io
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOOR = REPO_ROOT / "scripts" / "version-floor.json"
CRATES_IO = "https://crates.io/api/v1/crates/{name}"
UA = "rust-skills-check-floor/0.0.41 (https://github.com/xxww0098/rust-skills)"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def load_floor() -> dict:
    return json.loads(FLOOR.read_text(encoding="utf-8"))


def read_files(rel_paths: list[str]) -> dict[str, str]:
    out = {}
    for rel in rel_paths:
        path = REPO_ROOT / rel
        if not path.is_file():
            raise SystemExit(f"missing playbook {rel}")
        out[rel] = path.read_text(encoding="utf-8")
    return out


def major_minor(version: str) -> tuple[str, str]:
    parts = version.split(".")
    if len(parts) < 2:
        raise SystemExit(f"version {version!r} is not major.minor.patch")
    return parts[0], parts[1]


def check_offline(floor: dict) -> int:
    failed = 0
    baseline = floor["baseline"]
    edition = baseline["edition"]
    msrv = baseline["msrv"]
    for rel, text in read_files(baseline["files"]).items():
        if f'edition = "{edition}"' not in text and f"edition 2024" not in text and edition not in text:
            fail(f"{rel} lost edition {edition}")
            failed += 1
        if msrv not in text:
            fail(f"{rel} lost MSRV {msrv}")
            failed += 1
    for crate in floor["crates"]:
        name = crate["name"]
        bodies = read_files(crate["files"])
        for rel, text in bodies.items():
            missing = [n for n in crate["must_contain"] if n not in text]
            if missing:
                fail(f"{name}: {rel} missing {', '.join(missing)}")
                failed += 1
            marker = f"现行稳定线"
            if marker in text:
                line = crate["stable_line"]
                if line not in text.split(marker, 1)[1][:80]:
                    fail(
                        f"{name}: {rel} 现行稳定线 does not mention {line} "
                        f"(update scripts/version-floor.json together with the playbook)"
                    )
                    failed += 1
    return failed


def fetch_max_version(name: str, timeout: float) -> str | None:
    req = urllib.request.Request(
        CRATES_IO.format(name=name),
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        warn(f"crates.io {name}: {exc}")
        return None
    version = data.get("crate", {}).get("max_version")
    if not isinstance(version, str) or not version:
        warn(f"crates.io {name}: no max_version")
        return None
    return version


def check_fetch(floor: dict, timeout: float) -> int:
    failed = 0
    for crate in floor["crates"]:
        name = crate["name"]
        pinned = crate["pinned"]
        latest = fetch_max_version(name, timeout)
        if latest is None:
            continue
        if latest == pinned:
            continue
        pin_mm = major_minor(pinned)
        live_mm = major_minor(latest)
        if pin_mm != live_mm:
            fail(
                f"{name}: crates.io {latest} is a different line than pinned {pinned} "
                f"(stable_line {crate['stable_line']}); refresh the playbook and version-floor.json"
            )
            failed += 1
        else:
            warn(
                f"{name}: crates.io {latest} is newer than pinned {pinned} "
                f"(same {crate['stable_line']}.x line; bump the pin when you next touch the playbook)"
            )
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fetch", action="store_true", help="compare crates.io max_version")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()
    floor = load_floor()
    failed = check_offline(floor)
    if args.fetch:
        failed += check_fetch(floor, args.timeout)
    if failed:
        print(f"check-floor: {failed} check(s) failed", file=sys.stderr)
        return 1
    n = len(floor["crates"])
    mode = "offline+fetch" if args.fetch else "offline"
    print(f"OK: version floor {floor['as_of']} ({n} crates, {mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
