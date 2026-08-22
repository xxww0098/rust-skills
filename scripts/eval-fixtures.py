#!/usr/bin/env python3
"""Mechanical contracts for pressure scenes that have on-disk fixtures.

This is not an LLM runner. Each tests/fixtures/scene-*/contract.json keeps
the anti-pattern on disk and the playbook needles that scene requires.

Every command in scripts/command-metadata.json must be named by at least
one contract.

  ./scripts/eval-fixtures.py           check all contracts
  ./scripts/eval-fixtures.py --list    print scene ids
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"
METADATA = REPO_ROOT / "scripts" / "command-metadata.json"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def load_contracts() -> list[dict]:
    contracts = []
    for path in sorted(FIXTURES.glob("scene-*/contract.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("id", "title", "fixture", "fixture_needles", "skill_needles"):
            if key not in data:
                raise SystemExit(f"{path}: missing {key}")
        commands = data.get("commands")
        if not isinstance(commands, list) or not commands:
            raise SystemExit(f"{path}: missing commands")
        data["_dir"] = path.parent
        data["_contract"] = path
        contracts.append(data)
    if not contracts:
        raise SystemExit(f"no contracts under {FIXTURES}")
    return contracts


def check_command_coverage(contracts: list[dict]) -> int:
    meta = json.loads(METADATA.read_text(encoding="utf-8"))
    wanted = set(meta["commands"])
    covered: dict[str, list[str]] = {name: [] for name in wanted}
    unknown = []
    for contract in contracts:
        for name in contract["commands"]:
            if name in covered:
                covered[name].append(contract["id"])
            else:
                unknown.append(f"{name} (scene {contract['id']})")
    failed = 0
    missing = sorted(name for name, scenes in covered.items() if not scenes)
    if missing:
        fail("commands without a disk fixture: " + ", ".join(missing))
        failed += 1
    if unknown:
        fail("fixture commands not in command-metadata.json: " + ", ".join(unknown))
        failed += 1
    return failed


def check_contract(contract: dict) -> int:
    failed = 0
    fixture = contract["_dir"] / contract["fixture"]
    rel = fixture.relative_to(REPO_ROOT).as_posix()
    if not fixture.is_file():
        fail(f"scene {contract['id']} missing fixture {rel}")
        return 1
    text = fixture.read_text(encoding="utf-8")
    for needle in contract["fixture_needles"]:
        if needle not in text:
            fail(f"scene {contract['id']} fixture {rel} lost anti-pattern {needle!r}")
            failed += 1
    needles_map = contract["skill_needles"]
    if not isinstance(needles_map, dict):
        fail(f"scene {contract['id']} skill_needles must be an object")
        return failed + 1
    for rel_path, needles in needles_map.items():
        path = REPO_ROOT / rel_path
        if not path.is_file():
            fail(f"scene {contract['id']} missing skill file {rel_path}")
            failed += 1
            continue
        body = path.read_text(encoding="utf-8")
        missing = [n for n in needles if n not in body]
        if missing:
            fail(
                f"scene {contract['id']} {rel_path} missing {', '.join(missing)} "
                f"(acceptance for {contract['title']})"
            )
            failed += 1
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    contracts = load_contracts()
    if args.list:
        for contract in contracts:
            cmds = ",".join(contract["commands"])
            print(f"{contract['id']}\t{cmds}\t{contract['title']}")
        return 0
    failed = check_command_coverage(contracts)
    for contract in contracts:
        failed += check_contract(contract)
    if failed:
        print(f"eval-fixtures: {failed} check(s) failed", file=sys.stderr)
        return 1
    print(
        f"OK: {len(contracts)} fixture eval contracts covering "
        f"{len({c for ct in contracts for c in ct['commands']})} commands"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
