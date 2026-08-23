#!/usr/bin/env python3
"""E1 trigger-surface contract: exclusion and activation phrases stay in SKILL.md.

This is not LLM routing proof. It only checks that the published description
still names the include/exclude phrases in evals/triggers.json.

  python3 scripts/eval-triggers.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "rust" / "SKILL.md"
TRIGGERS = REPO_ROOT / "evals" / "triggers.json"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def main() -> int:
    data = json.loads(TRIGGERS.read_text(encoding="utf-8"))
    skill = SKILL.read_text(encoding="utf-8")
    # Only frontmatter description is available before the skill loads.
    desc = ""
    in_fm = False
    for line in skill.splitlines():
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
                continue
            break
        if in_fm and line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
    if not desc:
        fail("SKILL.md missing description frontmatter")
        return 1
    failed = 0
    for item in data.get("must_activate", []) + data.get("must_not_activate", []):
        phrase = item["phrase"]
        where = item.get("where", "description")
        hay = desc if where == "description" else skill
        if phrase not in hay:
            fail(f"missing {where} phrase {phrase!r}")
            failed += 1
    if ": " in desc.replace("/rust-skills:rust", ""):
        fail("description contains colon-space (skill-creator / router hazard)")
        failed += 1
    if failed:
        print(f"eval-triggers: {failed} check(s) failed", file=sys.stderr)
        return 1
    n = len(data.get("must_activate", [])) + len(data.get("must_not_activate", []))
    print(f"OK: trigger eval ({n} description phrases, E1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
