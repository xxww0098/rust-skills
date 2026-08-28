#!/usr/bin/env python3
"""Deterministic ProjectSnapshot subset: crates, edges, cycles, orphans, entrypoints.

Prefer `cargo metadata --no-deps --format-version 1` (`--locked` when lock exists).
Fall back to reading manifests.

  python3 scripts/inspect_project.py <project-root>
  python3 scripts/inspect_project.py --check-fixtures
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "projects"
MOD_RE = re.compile(r"^\s*(?:pub(?:\([^)]+\))?\s+)?mod\s+(\w+)\s*;", re.M)
PKG_NAME_RE = re.compile(r'(?m)^name\s*=\s*"([^"]+)"')
MEMBERS_RE = re.compile(r"(?ms)^\[workspace\].*?^members\s*=\s*\[(.*?)\]")
DEP_TABLE_RE = re.compile(r"(?ms)^\[dependencies\](.*?)(?=^\[|\Z)")
DEP_NAME_RE = re.compile(r"(?m)^([A-Za-z0-9_-]+)\s*=")
EDITION_RE = re.compile(r'(?m)^edition\s*=\s*"([^"]+)"')
RESOLVER_RE = re.compile(r'(?m)^resolver\s*=\s*"([^"]+)"')
UNWRAP_RE = re.compile(r"\.unwrap\s*\(")
EXPECT_RE = re.compile(r"\.expect\s*\(")
PRINTLN_RE = re.compile(r"\bprintln!\s*\(")
DBG_RE = re.compile(r"\bdbg!\s*\(")



def git_head(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def edition_of(manifest: Path) -> str | None:
    if not manifest.is_file():
        return None
    text = manifest.read_text(encoding="utf-8")
    pkg = re.search(r"(?ms)^\[package\](.*?)(?=^\[|\Z)", text)
    if pkg:
        m = EDITION_RE.search(pkg.group(1))
        if m:
            return m.group(1)
    ws = re.search(r"(?ms)^\[workspace\.package\](.*?)(?=^\[|\Z)", text)
    if ws:
        m = EDITION_RE.search(ws.group(1))
        if m:
            return m.group(1)
    m = EDITION_RE.search(text)
    return m.group(1) if m else None


def resolver_of(root: Path) -> str | None:
    man = root / "Cargo.toml"
    if not man.is_file():
        return None
    text = man.read_text(encoding="utf-8")
    ws = re.search(r"(?ms)^\[workspace\](.*?)(?=^\[|\Z)", text)
    body = ws.group(1) if ws else text
    m = RESOLVER_RE.search(body)
    return m.group(1) if m else None


def fan_maps(edges: list[tuple[str, str]], names: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    fan_in = {n: 0 for n in names}
    fan_out = {n: 0 for n in names}
    for a, b in edges:
        if a in fan_out:
            fan_out[a] += 1
        if b in fan_in:
            fan_in[b] += 1
    return fan_in, fan_out


def is_prod_rs(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if "tests" in parts or "examples" in parts or "benches" in parts:
        return False
    if path.name.endswith("_test.rs"):
        return False
    return path.suffix == ".rs"


def scan_signals(root: Path, member_dirs: list[Path]) -> list[dict]:
    found: list[dict] = []
    kinds = (
        ("unwrap", UNWRAP_RE),
        ("expect", EXPECT_RE),
        ("println", PRINTLN_RE),
        ("dbg", DBG_RE),
    )
    for d in member_dirs:
        src = d / "src"
        if not src.is_dir():
            continue
        for path in src.rglob("*.rs"):
            if not is_prod_rs(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            rel = rel_to(root, path)
            for i, line in enumerate(lines, 1):
                stripped = line.lstrip()
                if stripped.startswith("//"):
                    continue
                for kind, rx in kinds:
                    if rx.search(line):
                        found.append(
                            {
                                "kind": kind,
                                "path": f"{rel}:{i}",
                                "provenance": "source-scan",
                                "confidence": "high",
                            }
                        )
    return found


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def rel_to(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def package_name(manifest: Path) -> str | None:
    text = manifest.read_text(encoding="utf-8")
    pkg = re.search(r"(?ms)^\[package\](.*?)(?=^\[|\Z)", text)
    if not pkg:
        return None
    m = PKG_NAME_RE.search(pkg.group(1))
    return m.group(1) if m else None


def workspace_member_dirs(root: Path) -> list[Path]:
    text = (root / "Cargo.toml").read_text(encoding="utf-8")
    m = MEMBERS_RE.search(text)
    if not m:
        return [root] if "[package]" in text else []
    return [root / n for n in re.findall(r'"([^"]+)"', m.group(1))]


def declared_deps(manifest: Path) -> list[str]:
    text = manifest.read_text(encoding="utf-8")
    block = DEP_TABLE_RE.search(text)
    if not block:
        return []
    return sorted(set(DEP_NAME_RE.findall(block.group(1))))


def cargo_metadata(root: Path) -> dict | None:
    cmd = [
        "cargo", "metadata", "--no-deps", "--format-version", "1",
        "--manifest-path", str(root / "Cargo.toml"),
    ]
    if (root / "Cargo.lock").is_file():
        cmd.append("--locked")
    env = os.environ.copy()
    env["CARGO_TERM_COLOR"] = "never"
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env, cwd=root)
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def find_cycles(edges: list[tuple[str, str]]) -> list[list[str]]:
    adj: dict[str, list[str]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, [])
    found: list[list[str]] = []
    stack: list[str] = []
    onstack: set[str] = set()
    seen: set[str] = set()

    def dfs(node: str) -> None:
        seen.add(node)
        stack.append(node)
        onstack.add(node)
        for nxt in adj.get(node, []):
            if nxt not in seen:
                dfs(nxt)
            elif nxt in onstack:
                i = stack.index(nxt)
                cyc = stack[i:] + [nxt]
                body = cyc[:-1]
                rot = min(range(len(body)), key=lambda k: body[k])
                rotated = body[rot:] + body[:rot] + [body[rot]]
                if rotated not in found:
                    found.append(rotated)
        stack.pop()
        onstack.remove(node)

    for node in list(adj):
        if node not in seen:
            dfs(node)
    return found


def pkg_entrypoints(pkg_dir: Path) -> list[Path]:
    found: list[Path] = []
    for rel in ("src/lib.rs", "src/main.rs"):
        p = pkg_dir / rel
        if p.is_file():
            found.append(p)
    bin_dir = pkg_dir / "src" / "bin"
    if bin_dir.is_dir():
        found.extend(sorted(bin_dir.glob("*.rs")))
    return found


def reachable_mods(entry: Path) -> set[Path]:
    seen: set[Path] = set()
    stack = [entry]
    while stack:
        path = stack.pop()
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for name in MOD_RE.findall(text):
            stack.append(path.parent / f"{name}.rs")
            stack.append(path.parent / name / "mod.rs")
    return seen


def pkg_orphans(pkg_dir: Path, entries: list[Path]) -> list[Path]:
    src = pkg_dir / "src"
    if not src.is_dir():
        return []
    keep: set[Path] = set()
    for entry in entries:
        keep |= reachable_mods(entry)
    bin_files = set(p.resolve() for p in (pkg_dir / "src" / "bin").glob("*.rs")) if (pkg_dir / "src" / "bin").is_dir() else set()
    out = []
    for path in src.rglob("*.rs"):
        rp = path.resolve()
        if rp in bin_files or path.name in {"main.rs", "lib.rs"}:
            continue
        if rp not in keep:
            out.append(rp)
    return out


def inspect(root: Path) -> dict:
    root = root.resolve()
    manifest = root / "Cargo.toml"
    degraded: list[str] = []
    lock_policy = "tracked" if (root / "Cargo.lock").is_file() else "absent"
    meta = None
    if manifest.is_file() and (root / "Cargo.lock").is_file():
        meta = cargo_metadata(root)
        if meta is None:
            degraded.append("cargo-metadata-failed")
    elif manifest.is_file():
        degraded.append("lock-absent-manifest-scan")

    crates: list[dict] = []
    edges: list[tuple[str, str]] = []
    member_dirs: list[Path] = []

    if meta:
        ws_names = {p["name"] for p in meta["packages"]}
        for pkg in meta["packages"]:
            pkg_dir = Path(pkg["manifest_path"]).parent
            member_dirs.append(pkg_dir)
            crates.append(
                {
                    "name": pkg["name"],
                    "manifest": rel_to(root, Path(pkg["manifest_path"])),
                    "edition": pkg.get("edition"),
                    "targets": sorted({(t.get("kind") or ["lib"])[0] for t in pkg.get("targets", [])}),
                }
            )
            for dep in pkg.get("dependencies", []):
                name = dep.get("name")
                if name in ws_names:
                    edges.append((pkg["name"], name))
    elif manifest.is_file():
        member_dirs = workspace_member_dirs(root) or [root]
        ws_names: dict[str, Path] = {}
        for d in member_dirs:
            n = package_name(d / "Cargo.toml")
            if n:
                ws_names[n] = d
                crates.append(
                    {
                        "name": n,
                        "manifest": rel_to(root, d / "Cargo.toml"),
                        "edition": edition_of(d / "Cargo.toml") or edition_of(root / "Cargo.toml"),
                        "targets": [],
                    }
                )

        for n, d in ws_names.items():
            for dep in declared_deps(d / "Cargo.toml"):
                if dep in ws_names:
                    edges.append((n, dep))
    else:
        degraded.append("no-manifest")

    entry_rel: list[str] = []
    orphan_rel: list[str] = []
    for d in member_dirs:
        ents = pkg_entrypoints(d)
        entry_rel.extend(rel_to(root, e) for e in ents)
        orphan_rel.extend(rel_to(root, o) for o in pkg_orphans(d, ents))

    edges = sorted(set(edges))
    names = [c["name"] for c in crates]
    fan_in, fan_out = fan_maps(edges, names)
    signals = scan_signals(root, member_dirs)
    return {
        "identity": {
            "workspace_root": str(root),
            "manifest_path": rel_to(root, manifest) if manifest.is_file() else str(manifest),
            "git_head": git_head(root),
            "dirty": False,
            "lock_policy": lock_policy,
            "degraded_reasons": degraded,
            "resolver": resolver_of(root),
        },
        "scope": {"requested_target": None, "primary_files": [], "adjacent_evidence": [], "excluded_paths": []},
        "crates": crates,
        "graphs": {
            "crate_edges": [{"from": a, "to": b} for a, b in edges],
            "cycles": find_cycles(edges),
            "orphans": sorted(set(orphan_rel)),
            "entrypoints": sorted(set(entry_rel)),
            "fan_in": fan_in,
            "fan_out": fan_out,
        },
        "signals": signals,
    }


def comparable(snapshot: dict) -> dict:
    counts: dict[str, int] = {}
    for sig in snapshot.get("signals", []):
        counts[sig["kind"]] = counts.get(sig["kind"], 0) + 1
    fan_in = snapshot["graphs"].get("fan_in", {})
    return {
        "members": sorted(c["name"] for c in snapshot["crates"]),
        "edges": sorted(f'{e["from"]}->{e["to"]}' for e in snapshot["graphs"]["crate_edges"]),
        "cycles": sorted("->".join(c) for c in snapshot["graphs"]["cycles"]),
        "orphans": sorted(snapshot["graphs"]["orphans"]),
        "entrypoints": sorted(snapshot["graphs"]["entrypoints"]),
        "fan_in": sorted(f"{k}:{v}" for k, v in fan_in.items()),
        "signals": sorted(f"{k}:{v}" for k, v in counts.items() if v),
    }


def check_fixtures() -> int:
    failed = 0
    roots = sorted(p for p in FIXTURES.iterdir() if p.is_dir() and (p / "expected.json").is_file())
    if len(roots) < 4:
        fail(f"need ≥4 tests/projects/* with expected.json, found {len(roots)}")
        failed += 1
    for root in roots:
        expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
        got = comparable(inspect(root))
        for key in ("members", "edges", "cycles", "orphans", "entrypoints", "fan_in", "signals"):
            if key not in expected:
                continue
            if set(got.get(key, [])) != set(expected.get(key, [])):

                fail(f"{root.name}.{key}: got {got.get(key)} want {expected.get(key)}")
                failed += 1
    if failed == 0:
        print(f"OK: {len(roots)} project fixtures")
    return failed


def main() -> int:
    if "--check-fixtures" in sys.argv:
        return check_fixtures()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = Path(args[0]) if args else Path.cwd()
    json.dump(inspect(root), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
