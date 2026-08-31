#!/usr/bin/env python3
"""Fail if this pack still presents the clone as one Git-install skill.

The GitHub repo is the source. The install unit is one `.<harness>/` tree
(or `skills/rust` inside it), never the monorepo. A root `SKILL.md` with the
same identity as `skills/rust` is what made SkillStar-style scanners treat
the whole clone as the skill payload.

This script:

  1. Rejects a pack-root skill identity (`SKILL.md` + body dirs).
  2. Requires each generated harness folder to be a standalone copy: taking
     that folder alone (preserving symlinks, not following them out of tree)
     still yields a readable `skills/rust/SKILL.md` and kernel/reference.
  3. Simulates SkillStar-style discovery and fails if the chosen install
     folder is the repo root when `skills/rust` or harness projections exist.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Keep in sync with scripts/sync-providers.py PROVIDERS.
HARNESS_DIRS = (
    ".claude",
    ".cursor",
    ".agents",
    ".kiro",
    ".opencode",
    ".pi",
    ".omp",
    ".dsh",
    ".qoder",
    ".trae-cn",
    ".trae",
    ".grok",
    ".agent",
    ".hermes",
)

ROOT_SKILL_IDENTITY = ("SKILL.md", "reference", "rules", "kernel", "agents")
MONOREPO_NOISE = ("tests", "docs", "scripts", "evals", "examples")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)


def skill_frontmatter_name(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    fm = text[4:end]
    name = None
    has_desc = False
    for line in fm.splitlines():
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        if line.startswith("description:"):
            has_desc = True
    if not name or not has_desc:
        return None
    return name


def is_canonical_skill_folder(folder_path: str) -> bool:
    path = folder_path.replace("\\", "/").strip("/")
    return path == "skills" or path.startswith("skills/") or path == "source/skills" or path.startswith(
        "source/skills/"
    )


def discover_skill_md_folders(repo: Path) -> list[tuple[str, str]]:
    """Return (folder_path, identity) for regular-file SKILL.md manifests."""
    found: list[tuple[str, str]] = []
    skip = {".git", "node_modules", "target", "tests"}
    for path in repo.rglob("SKILL.md"):
        if any(part in skip for part in path.relative_to(repo).parts):
            continue
        try:
            meta = path.lstat()
        except OSError:
            continue
        if not os.path.stat.S_ISREG(meta.st_mode):
            continue
        name = skill_frontmatter_name(path)
        if not name:
            continue
        rel = path.parent.relative_to(repo)
        folder = "" if rel == Path(".") else rel.as_posix()
        found.append((folder, name))
    return found


def skillstar_style_install_folder(repo: Path) -> str | None:
    """Choose one install folder the way SkillStar pack-layout does.

    Root `SKILL.md` that mirrors `skills/<name>/` is a shim, not the unit.
    Remaining identities prefer the canonical catalog over harness copies.
    """
    candidates = discover_skill_md_folders(repo)
    if not candidates:
        return None
    root_ids = [name for folder, name in candidates if folder == ""]
    if root_ids:
        root_id = root_ids[0]
        has_canonical_twin = any(
            folder
            and name.casefold() == root_id.casefold()
            and is_canonical_skill_folder(folder)
            for folder, name in candidates
        )
        if has_canonical_twin:
            candidates = [(folder, name) for folder, name in candidates if folder != ""]
        else:
            return ""

    # Prefer canonical catalog, then first remaining identity match for `rust`.
    rust = [(folder, name) for folder, name in candidates if name.casefold() == "rust"]
    if not rust:
        return candidates[0][0]
    rust.sort(key=lambda item: (0 if is_canonical_skill_folder(item[0]) else 1, item[0]))
    return rust[0][0]


def check_root_is_not_skill_identity() -> int:
    failed = 0
    for name in ROOT_SKILL_IDENTITY:
        path = REPO_ROOT / name
        if not path.exists() and not path.is_symlink():
            continue
        if name == "SKILL.md":
            identity = skill_frontmatter_name(path) if path.is_file() else None
            fail(
                f"pack root {name} must not be a Git-install skill identity "
                f"(found name={identity!r}); install unit is skills/rust or .<harness>/"
            )
            failed += 1
            continue
        fail(
            f"pack root {name}/ is a leftover one-level skill shim; "
            "one-level scanners should take .dsh/ (or another harness tree), not the clone"
        )
        failed += 1
    return failed


def check_discovery_does_not_pick_root() -> int:
    chosen = skillstar_style_install_folder(REPO_ROOT)
    canonical = REPO_ROOT / "skills" / "rust" / "SKILL.md"
    harness_hits = any((REPO_ROOT / d / "skills" / "rust" / "SKILL.md").exists() for d in HARNESS_DIRS)
    if not canonical.is_file() and not harness_hits:
        fail("neither skills/rust nor any .<harness>/skills/rust projection exists")
        return 1
    if chosen == "":
        fail(
            "SkillStar-style discovery chose the repo root as the install folder; "
            "root SKILL.md must not be the Git-install identity when skills/rust "
            "or harness projections exist"
        )
        return 1
    if chosen is None:
        fail("SkillStar-style discovery found no SKILL.md")
        return 1
    if chosen != "skills/rust" and not any(
        chosen == f"{d}/skills/rust" or chosen == d for d in HARNESS_DIRS
    ):
        fail(f"SkillStar-style discovery chose unexpected folder {chosen!r}")
        return 1
    print(f"OK: discovery install folder is {chosen}")
    return 0


def check_harness_standalone(harness: str) -> int:
    src = REPO_ROOT / harness
    if not src.is_dir():
        fail(f"missing harness install unit {harness}/")
        return 1

    skill = src / "skills" / "rust"
    if skill.is_symlink():
        fail(
            f"{harness}/skills/rust is an outbound symlink "
            f"({os.readlink(skill)}); copying {harness}/ alone leaves a dangling link"
        )
        return 1
    if not (skill / "SKILL.md").is_file():
        fail(f"{harness}/skills/rust/SKILL.md missing (not a standalone install unit)")
        return 1
    name = skill_frontmatter_name(skill / "SKILL.md")
    if name != "rust":
        fail(f"{harness}/skills/rust/SKILL.md identity is {name!r}, want rust")
        return 1
    if not (skill / "reference" / "engage.md").is_file():
        fail(f"{harness}/skills/rust/reference/engage.md missing")
        return 1
    if not (skill / "kernel" / "evidence.md").is_file():
        fail(f"{harness}/skills/rust/kernel/evidence.md missing")
        return 1

    leaked = [name for name in MONOREPO_NOISE if (src / name).exists()]
    other_harnesses = [d for d in HARNESS_DIRS if d != harness and (src / d).exists()]
    if leaked or other_harnesses:
        fail(
            f"{harness}/ is not a slim install unit; contains "
            f"{', '.join(leaked + other_harnesses)}"
        )
        return 1

    # Copy the harness folder the way a Git installer would: preserve
    # symlinks, do not rewrite them to their targets.
    with tempfile.TemporaryDirectory(prefix=f"rust-skills-{harness.lstrip('.')}-") as tmp:
        dest = Path(tmp) / harness
        shutil.copytree(src, dest, symlinks=True, copy_function=shutil.copy2)
        copied = dest / "skills" / "rust"
        if copied.is_symlink() and not copied.exists():
            fail(
                f"copying {harness}/ with symlinks preserved left a dangling "
                f"skills/rust -> {os.readlink(copied)}"
            )
            return 1
        if not (copied / "SKILL.md").is_file():
            fail(f"copied {harness}/ has no readable skills/rust/SKILL.md")
            return 1
        if not (copied / "reference" / "engage.md").is_file():
            fail(f"copied {harness}/ lost reference/engage.md")
            return 1
        if (dest / "tests").exists() or (dest / "scripts").exists():
            fail(f"copied {harness}/ ingested monorepo tests/ or scripts/")
            return 1
    return 0


def main() -> int:
    failed = 0
    failed += check_root_is_not_skill_identity()
    failed += check_discovery_does_not_pick_root()
    for harness in HARNESS_DIRS:
        failed += check_harness_standalone(harness)
    if failed:
        return 1
    print(
        f"OK: pack root is not a skill identity; {len(HARNESS_DIRS)} harness "
        "trees are standalone install units"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
