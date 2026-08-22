#!/usr/bin/env python3
"""Generate command tables from scripts/command-metadata.json.

scripts/command-metadata.json is the single source of truth for each
command's user-facing facts: category, one-line summary, argument hint,
and trigger phrases (Chinese `triggers` plus English `triggers_en`). This
script rewrites generated blocks between markers:

  skills/rust/SKILL.md   router table (命令|分类|触发|Reference)
  README.md              command quick reference, grouped by category

Usage:
  ./scripts/gen-command-tables.py           regenerate the two blocks
  ./scripts/gen-command-tables.py --check   exit 1 if a block drifted

sync-providers.py runs this before syncing; check-consistency.sh runs it
with --check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
METADATA = REPO_ROOT / "scripts" / "command-metadata.json"
SKILL_MD = REPO_ROOT / "skills" / "rust" / "SKILL.md"
README_MD = REPO_ROOT / "README.md"
REFERENCE_DIR = REPO_ROOT / "skills" / "rust" / "reference"

SKILL_START = "<!-- commands-table:start -->"
SKILL_END = "<!-- commands-table:end -->"
README_START = "<!-- commands-table:start -->"
README_END = "<!-- commands-table:end -->"


def load_metadata() -> dict:
    data = json.loads(METADATA.read_text(encoding="utf-8"))
    categories = data.get("categories")
    commands = data.get("commands")
    if not isinstance(categories, list) or not categories:
        raise SystemExit(f"{METADATA} needs a non-empty 'categories' list")
    if not isinstance(commands, dict) or not commands:
        raise SystemExit(f"{METADATA} needs a 'commands' object")
    return data


def validate(metadata: dict) -> None:
    categories = metadata["categories"]
    commands = metadata["commands"]
    problems = []
    for name, entry in commands.items():
        if entry.get("category") not in categories:
            problems.append(f"{name}: unknown category {entry.get('category')!r}")
        if not str(entry.get("summary", "")).strip():
            problems.append(f"{name}: missing summary")
        triggers = entry.get("triggers")
        if not isinstance(triggers, list) or not triggers:
            problems.append(f"{name}: missing triggers")
        triggers_en = entry.get("triggers_en")
        if not isinstance(triggers_en, list) or not triggers_en:
            problems.append(f"{name}: missing triggers_en")
    references = {p.stem for p in REFERENCE_DIR.glob("*.md")} - {"routing", "craft", "engage", "testing"}
    for missing in sorted(references - set(commands)):
        problems.append(f"reference file without metadata: {missing}.md")
    for orphan in sorted(set(commands) - references):
        problems.append(f"metadata command without reference file: {orphan}")
    if problems:
        raise SystemExit(f"{METADATA}: " + "; ".join(problems))


def format_triggers(entry: dict) -> str:
    zh = [f"「{t}」" for t in entry["triggers"]]
    en = list(entry.get("triggers_en") or [])
    return " · ".join(zh + en)


def skill_block(metadata: dict) -> str:
    lines = ["| 命令 | 分类 | 触发（中/英） | Reference |", "|---|---|---|---|"]
    for name, entry in metadata["commands"].items():
        lines.append(
            f"| `{name}` | {entry['category']} | {format_triggers(entry)} | "
            f"[reference/{name}.md](reference/{name}.md) |"
        )
    return "\n".join(lines) + "\n"


def command_text(name: str, entry: dict) -> str:
    hint = str(entry.get("argumentHint", "")).strip()
    return f"/rust-skills:rust {name}" + (f" {hint}" if hint else "")


def readme_block(metadata: dict) -> str:
    entries = list(metadata["commands"].items())
    width = max(len(command_text(n, e)) for n, e in entries) + 2
    out = []
    for category in metadata["categories"]:
        rows = [
            f"{command_text(n, e):<{width}} # {e['summary']}"
            for n, e in entries
            if e["category"] == category
        ]
        out.append(f"#### {category}")
        out.extend(rows)
        out.append("")
    return "\n".join(out)


def argument_hint(metadata: dict) -> str:
    """Category-grouped command hint, impeccable-style: visible when typing the slash command."""
    groups = []
    for category in metadata["categories"]:
        names = [
            name
            for name, entry in metadata["commands"].items()
            if entry["category"] == category
        ]
        groups.append(f"{category}: " + "|".join(names))
    return "[" + " · ".join(groups) + "] [target]"


HINT_RE = re.compile(r"^argument-hint:.*$", re.M)


def set_argument_hint(text: str, hint: str) -> tuple[str, bool]:
    new_text, count = HINT_RE.subn(f'argument-hint: "{hint}"', text, count=1)
    if count != 1:
        raise SystemExit(f"{SKILL_MD}: argument-hint line not found in frontmatter")
    return new_text, new_text != text


def replace_between(text: str, start: str, end: str, content: str) -> tuple[str, bool]:
    s = text.find(start)
    e = text.find(end)
    if s == -1 or e == -1 or e <= s:
        raise SystemExit("marker pair not found")
    block = start + "\n" + content + end
    return text[:s] + block + text[e + len(end):], text[s:e + len(end)] != block


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()

    metadata = load_metadata()
    validate(metadata)

    drifts = []
    skill_text = SKILL_MD.read_text(encoding="utf-8")
    hinted, hint_changed = set_argument_hint(skill_text, argument_hint(metadata))
    skill_new, table_changed = replace_between(
        hinted, SKILL_START, SKILL_END, skill_block(metadata)
    )
    if hint_changed or table_changed:
        if args.check:
            drifts.append("SKILL.md 路由表/argument-hint")
        else:
            SKILL_MD.write_text(skill_new, encoding="utf-8")
            print("wrote SKILL.md 路由表 + argument-hint")
    readme_text = README_MD.read_text(encoding="utf-8")
    readme_new, readme_changed = replace_between(
        readme_text, README_START, README_END, readme_block(metadata)
    )
    if readme_changed:
        if args.check:
            drifts.append("README 命令速查")
        else:
            README_MD.write_text(readme_new, encoding="utf-8")
            print("wrote README 命令速查")

    if args.check:
        if drifts:
            print("table drift: " + ", ".join(drifts), file=sys.stderr)
            print("run ./scripts/gen-command-tables.py", file=sys.stderr)
            return 1
        print("OK: command tables match scripts/command-metadata.json")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
