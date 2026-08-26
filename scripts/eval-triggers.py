#!/usr/bin/env python3
"""E1 trigger-surface contract.

Positives must live in SKILL + plugin + openai adapter descriptions.
Skip cases must live in SKILL 非目标 and must NOT be description keywords
(embedding routers treat 'Python' in description as a match).
near_neighbors are recorded contracts, not LLM runs.

  python3 scripts/eval-triggers.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "rust" / "SKILL.md"
PLUGIN = REPO_ROOT / ".claude-plugin" / "plugin.json"
OPENAI = REPO_ROOT / "skills" / "rust" / "agents" / "openai.yaml"
ACTIVATION = REPO_ROOT / "scripts" / "activation.json"
TRIGGERS = REPO_ROOT / "evals" / "triggers.json"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def skill_description(text: str) -> str:
    desc = ""
    in_fm = False
    for line in text.splitlines():
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
                continue
            break
        if in_fm and line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
    return desc


def nongoals(text: str) -> str:
    m = re.search(r"^## 非目标\n(.*?)(\n## |\Z)", text, flags=re.M | re.S)
    return m.group(1) if m else ""


def main() -> int:
    data = json.loads(TRIGGERS.read_text(encoding="utf-8"))
    act = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    skill = SKILL.read_text(encoding="utf-8")
    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    openai = OPENAI.read_text(encoding="utf-8")
    desc = skill_description(skill)
    failed = 0
    if not desc:
        fail("SKILL.md missing description frontmatter")
        return 1
    if desc != act["description"]:
        fail("SKILL description != scripts/activation.json")
        failed += 1
    if plugin.get("description") != act["description"]:
        fail("plugin.json description != scripts/activation.json")
        failed += 1
    if ": " in desc.replace("/rust-skills:rust", ""):
        fail("description contains colon-space")
        failed += 1
    if len(desc) > 1024:
        fail(f"description {len(desc)} chars > 1024 (Anthropic skill spec)")
        failed += 1
    body = skill.split("---", 2)[-1]
    body_lines = body.count("\n")
    if body_lines > 500:
        fail(f"SKILL.md body {body_lines} lines > 500 (progressive disclosure)")
        failed += 1
    pin_chars = 0
    for pin in (REPO_ROOT / "commands").glob("*.md"):
        for line in pin.read_text(encoding="utf-8").splitlines():
            if line.startswith("description:"):
                pin_chars += len(line.split(":", 1)[1].strip())
                break
    combined = len(desc) + pin_chars
    if combined > 12000:
        fail(f"skill+command descriptions {combined} chars; Claude Code silent-drop budget is 15000")
        failed += 1
    for item in data.get("must_activate", []):
        phrase = item["phrase"]
        if phrase not in desc:
            fail(f"description missing positive {phrase!r}")
            failed += 1
    for phrase in data.get("forbidden_in_description", []):
        if phrase in desc:
            fail(f"description contains skip-attracting {phrase!r}")
            failed += 1
    body = nongoals(skill)
    if not body:
        fail("SKILL.md missing 非目标 section")
        failed += 1
    for phrase in data.get("required_in_nongoals", []):
        if phrase not in body:
            fail(f"非目标 missing {phrase!r}")
            failed += 1
    for prompt in data.get("near_neighbors", []):
        token = prompt["token"]
        expect = prompt["expect"]
        if expect == "activate" and token not in desc and token not in skill:
            fail(f"activate neighbor {token!r} missing from skill")
            failed += 1
        if expect == "skip" and token in desc:
            fail(f"skip neighbor token {token!r} still in description")
            failed += 1
        if expect == "readonly" and token not in body:
            fail(f"readonly neighbor {token!r} missing from 非目标")
            failed += 1
    for verb in act["write_verbs_zh"] + act["write_verbs_en"]:
        if verb not in openai:
            fail(f"openai.yaml missing write verb {verb!r}")
            failed += 1
    if failed:
        print(f"eval-triggers: {failed} check(s) failed", file=sys.stderr)
        return 1
    print("OK: trigger eval (activation.json + 非目标 + near_neighbors, E1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
