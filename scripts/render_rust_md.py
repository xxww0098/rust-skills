#!/usr/bin/env python3
"""Deterministic RUST.md projection from a ProjectSnapshot.

Does not invent facets. Model may add 待确认; this script only emits
Facets/基线/Crate 图/域划分 from inspect JSON.

  python3 scripts/render_rust_md.py <project-root>
  python3 scripts/render_rust_md.py --check-fixtures
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from inspect_project import inspect  # noqa: E402

SKILL = REPO_ROOT / "skills" / "rust" / "SKILL.md"
RULES = REPO_ROOT / "skills" / "rust" / "rules" / "rules-full.md"


def skill_version() -> str:
    text = SKILL.read_text(encoding="utf-8")
    m = re.search(r"(?m)^version:\s*(\S+)", text)
    return m.group(1) if m else "0"


def rule_count() -> int:
    n = 0
    for line in RULES.read_text(encoding="utf-8").splitlines():
        if re.match(r"^- [A-Z]+-\d+\[[MSY]\]", line):
            n += 1
    return n


def crate_graph_line(snapshot: dict) -> str:
    cycles = snapshot["graphs"].get("cycles") or []
    if cycles:
        return "环: " + "; ".join(" ↔ ".join(c[:-1]) for c in cycles)
    edges = snapshot["graphs"].get("crate_edges") or []
    if not edges:
        members = [c["name"] for c in snapshot["crates"]]
        return "、".join(members) if members else "(无成员)"
    parts = [f'{e["to"]} ← {e["from"]}' for e in edges]
    return "；".join(parts)


def infer_artifact(crate: dict, snapshot: dict) -> str:
    targets = set(crate.get("targets") or [])
    name = crate["name"]
    entries = " ".join(snapshot["graphs"].get("entrypoints") or [])
    if "bin" in targets or f"{name}/src/main.rs" in entries or "src/bin/" in entries:
        if "lib" in targets or "src/lib.rs" in entries:
            return "cli"
        return "cli"
    return "lib"


def render(snapshot: dict) -> str:
    crates = snapshot["crates"]
    editions = sorted({c.get("edition") or "?" for c in crates})
    edition = editions[0] if len(editions) == 1 else "/".join(editions)
    resolver = snapshot["identity"].get("resolver") or "?"
    facets = []
    for c in crates:
        facets.append(f"{c['name']}=artifact:{infer_artifact(c, snapshot)}")
    orphans = snapshot["graphs"].get("orphans") or []
    domain = "待确认"
    if orphans:
        domain = "孤儿: " + ", ".join(orphans)
    signals = snapshot.get("signals") or []
    counts: dict[str, int] = {}
    for s in signals:
        counts[s["kind"]] = counts.get(s["kind"], 0) + 1
    signal_line = "、".join(f"{k} {v}" for k, v in sorted(counts.items())) or "无机械信号"
    default_art = infer_artifact(crates[0], snapshot) if crates else "lib"
    lines = [
        "## Facets",
        f"默认: artifact={default_art}, maturity=prototype",
        ("覆盖: " + ", ".join(facets)) if facets else "覆盖: (无)",
        "## 基线",
        f"edition {edition} · MSRV unknown · resolver {resolver} · 规范版本 v{skill_version()}（{rule_count()} 条分级规则）",
        "## Crate 图",
        crate_graph_line(snapshot),
        "## 域划分",
        domain,
        f"机械信号: {signal_line}",
    ]
    return "\n".join(lines) + "\n"


def check_fixtures(write: bool = False) -> int:
    failed = 0
    roots = sorted(p for p in (REPO_ROOT / "tests" / "projects").iterdir() if (p / "expected.json").is_file())
    for root in roots:
        golden = root / "projection.md"
        got = render(inspect(root))
        if write:
            golden.write_text(got, encoding="utf-8")
            print(f"wrote {golden.relative_to(REPO_ROOT)}")
            continue
        if not golden.is_file():
            print(f"FAIL: missing {golden.relative_to(REPO_ROOT)}; run with --write", file=sys.stderr)
            failed += 1
            continue
        want = golden.read_text(encoding="utf-8")
        if got != want:
            print(f"FAIL: {root.name} projection drifted", file=sys.stderr)
            print("--- got ---", file=sys.stderr)
            print(got, file=sys.stderr)
            failed += 1
    if failed == 0:
        print(f"OK: {len(roots)} RUST.md projections")
    return failed


def main() -> int:
    write = "--write" in sys.argv
    if "--check-fixtures" in sys.argv:
        return check_fixtures(write=write)
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = Path(args[0]) if args else Path.cwd()
    sys.stdout.write(render(inspect(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
