#!/usr/bin/env python3
"""What counts as a production-code fact.

inspect_project and check_patch must share this predicate. A hit inside a
comment, string, cfg(test) item, test/example/bench file, *_test.rs, or
build.rs is not a project fact.
"""
from __future__ import annotations

import re
from pathlib import Path

UNWRAP_RE = re.compile(r"\.unwrap\s*\(")
EXPECT_RE = re.compile(r"\.expect\s*\(")
PRINTLN_RE = re.compile(r"\bprintln!\s*\(")
DBG_RE = re.compile(r"\bdbg!\s*\(")
CLONE_RE = re.compile(r"\.clone\s*\(")
AMP_STRING_RE = re.compile(r"&String\b")
INDEX_LOOP_RE = re.compile(r"for\s+\w+\s+in\s+0\s*\.\.")

SIGNAL_RULES = (
    ("unwrap", UNWRAP_RE),
    ("expect", EXPECT_RE),
    ("println", PRINTLN_RE),
    ("dbg", DBG_RE),
)

PATCH_RULES = (
    ("unwrap", UNWRAP_RE, "ERR-03"),
    ("println", PRINTLN_RE, "OBS-01"),
    ("dbg", DBG_RE, "OBS-01"),
    ("clone", CLONE_RE, "OWN-01"),
    ("amp_string", AMP_STRING_RE, "OWN-02"),
    ("index_loop", INDEX_LOOP_RE, "SIMP-13"),
)
PATCH_BLOCKING = frozenset({"unwrap", "println", "dbg"})
PATCH_SIGNALS = frozenset({"clone", "amp_string", "index_loop"})

CFG_TEST_RE = re.compile(
    r"#\[\s*cfg\s*\(\s*(?:test|any\s*\([^;]{0,200}?\btest\b[^;]{0,200}?\))\s*\)\s*\]",
    re.S,
)
ITEM_START_RE = re.compile(
    r"(?:pub(?:\s*\([^)]+\))?[\s\n]+)?(?:async[\s\n]+)?(?:unsafe[\s\n]+)?"
    r"(?:const[\s\n]+)?(?:extern[\s\n]+(?:\"[^\"]+\"[\s\n]+)?)?"
    r"(?:fn|mod|impl|struct|enum|trait|type|union|use|static|const)\b",
    re.S,
)

SKIP_DIR_NAMES = frozenset({"tests", "examples", "benches", "target"})


def crate_root_for(path: Path) -> Path | None:
    cur = path if path.is_dir() else path.parent
    for candidate in [cur, *cur.parents]:
        if (candidate / "Cargo.toml").is_file():
            return candidate
    return None


def is_prod_rs(path: Path, relative_to: Path | None = None) -> bool:
    if path.suffix != ".rs":
        return False
    name = path.name.lower()
    if name == "build.rs" or name.endswith("_test.rs"):
        return False
    root = relative_to or crate_root_for(path)
    try:
        parts = path.resolve().relative_to(root.resolve()).parts if root else path.parts
    except ValueError:
        parts = path.parts
    if any(part.lower() in SKIP_DIR_NAMES for part in parts):
        return False
    return True


def iter_prod_rs(targets: list[Path]) -> list[Path]:
    """Same exclusion whether the caller passed a file or a directory."""
    out: list[Path] = []
    seen: set[Path] = set()
    for raw in targets:
        t = raw
        root = crate_root_for(t)
        if t.is_file():
            if is_prod_rs(t, relative_to=root):
                rp = t.resolve()
                if rp not in seen:
                    seen.add(rp)
                    out.append(t)
        elif t.is_dir():
            for path in t.rglob("*.rs"):
                if is_prod_rs(path, relative_to=root or crate_root_for(path)):
                    rp = path.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        out.append(path)
    return out
