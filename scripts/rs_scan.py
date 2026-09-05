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


def _raw_hashes(text: str, i: int) -> int:
    n = 0
    while i + n < len(text) and text[i + n] == "#":
        n += 1
    return n


def mask_non_code(text: str) -> str:
    """Replace comments and string/char literals with spaces; keep newlines."""
    out: list[str] = []
    i = 0
    n = len(text)

    def space_out(chunk: str) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in chunk)

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if ch == "r" or (ch == "b" and nxt == "r"):
            j = i + (2 if ch == "b" else 1)
            hashes = _raw_hashes(text, j)
            if j + hashes < n and text[j + hashes] == '"':
                start = i
                i = j + hashes + 1
                close = '"' + ("#" * hashes)
                k = text.find(close, i)
                if k == -1:
                    out.append(space_out(text[start:]))
                    break
                i = k + len(close)
                out.append(space_out(text[start:i]))
                continue

        if ch == "b" and nxt == '"':
            start = i
            i += 2
            while i < n:
                if text[i] == "\\":
                    i = min(i + 2, n)
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            out.append(space_out(text[start:i]))
            continue

        if ch == "b" and nxt == "'":
            start = i
            i += 2
            if i < n and text[i] == "\\":
                i = min(i + 2, n)
            elif i < n:
                i += 1
            if i < n and text[i] == "'":
                i += 1
            out.append(space_out(text[start:i]))
            continue

        if ch == "/" and nxt == "/":
            start = i
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            out.append(space_out(text[start:i]))
            continue

        if ch == "/" and nxt == "*":
            start = i
            i += 2
            depth = 1
            while i < n and depth:
                if text[i] == "/" and i + 1 < n and text[i + 1] == "*":
                    depth += 1
                    i += 2
                    continue
                if text[i] == "*" and i + 1 < n and text[i + 1] == "/":
                    depth -= 1
                    i += 2
                    continue
                i += 1
            out.append(space_out(text[start:i]))
            continue

        if ch == '"':
            start = i
            i += 1
            while i < n:
                if text[i] == "\\":
                    i = min(i + 2, n)
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            out.append(space_out(text[start:i]))
            continue

        if ch == "'":
            start = i
            i += 1
            if i < n and text[i] == "\\":
                i = min(i + 2, n)
            elif i < n:
                i += 1
            if i < n and text[i] == "'":
                i += 1
                out.append(space_out(text[start:i]))
                continue
            out.append(ch)
            continue

        out.append(ch)
        i += 1
    return "".join(out)


def _skip_item(text: str, i: int) -> int:
    m = ITEM_START_RE.search(text, i)
    if not m:
        return i
    j = m.end()
    while j < len(text) and text[j] not in "{;":
        j += 1
    if j >= len(text):
        return len(text)
    if text[j] == ";":
        return j + 1
    depth = 0
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(text)


def mask_cfg_test(text: str) -> str:
    """Blank #[cfg(test)] items. Run after mask_non_code so attrs stay visible."""
    out = list(text)
    for match in CFG_TEST_RE.finditer(text):
        end = _skip_item(text, match.end())
        for k in range(match.start(), end):
            if out[k] != "\n":
                out[k] = " "
    return "".join(out)


def production_code(text: str) -> str:
    return mask_cfg_test(mask_non_code(text))


def scan_rules(path: Path, rules: tuple) -> list[tuple[int, str, str, str]]:
    """Return (lineno, rule_name, extra, line_text) hits in production code."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    masked = production_code(raw)
    raw_lines = raw.splitlines()
    hits = []
    for i, line in enumerate(masked.splitlines(), 1):
        for spec in rules:
            name, rx = spec[0], spec[1]
            extra = spec[2] if len(spec) > 2 else ""
            if rx.search(line):
                src = raw_lines[i - 1].strip() if i <= len(raw_lines) else line.strip()
                hits.append((i, name, extra, src))
    return hits
