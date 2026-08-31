#!/usr/bin/env python3
"""Mirror one skill source into impeccable's harness set plus Oh My Pi and dsh.

Source of truth:
  skills/rust/                  skill body, rules, references
  commands/                     slash-command pins
  .claude-plugin/plugin.json    plugin identity + version

This script regenerates command tables from scripts/command-metadata.json,
then writes vendor manifests and per-harness **standalone copies**. Each
`.<agent>/` tree is an install unit: SkillStar (and peers) can take that
folder as `source_folder` without the rest of the monorepo. Do not hand-edit
generated files.

  ./scripts/sync-providers.py           write manifests and materialized trees
  ./scripts/sync-providers.py --check   exit 1 if generated files drifted
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_PLUGIN = REPO_ROOT / ".claude-plugin" / "plugin.json"
SKILL_MD = REPO_ROOT / "skills" / "rust" / "SKILL.md"
RULES_MD = REPO_ROOT / "skills" / "rust" / "rules" / "preamble.md"
RULES_FULL = REPO_ROOT / "skills" / "rust" / "rules" / "rules-full.md"

# Impeccable provider set plus Oh My Pi (`.omp`) and DeepSeek Harness (`.dsh`).
# `.codex/skills` is omitted on purpose: Codex loads repo skills from `.agents`.
PROVIDERS = (
    {"name": "Claude Code", "dir": ".claude", "commands": True},
    {"name": "Cursor", "dir": ".cursor", "commands": True},
    {"name": "Codex Repo Skills", "dir": ".agents", "commands": True},
    {"name": "Kiro", "dir": ".kiro", "commands": False},
    {"name": "OpenCode", "dir": ".opencode", "commands": True},
    {"name": "Pi", "dir": ".pi", "commands": False},
    {"name": "Oh My Pi", "dir": ".omp", "commands": True},
    {"name": "DeepSeek Harness", "dir": ".dsh", "commands": False},
    {"name": "Qoder", "dir": ".qoder", "commands": False},
    {"name": "Trae China", "dir": ".trae-cn", "commands": False},
    {"name": "Trae", "dir": ".trae", "commands": False},
    {"name": "Grok Build", "dir": ".grok", "commands": True},
    {"name": "Antigravity", "dir": ".agent", "commands": False},
    {"name": "Hermes Agent", "dir": ".hermes", "commands": False},
)

PROVIDER_NAMES = tuple(p["name"] for p in PROVIDERS)

# Former pack-root skill identity. One-level scanners must install a harness
# tree (e.g. `.dsh/`), not the clone. A root `SKILL.md` with name `rust` is
# what made Git installers treat the whole repository as one skill.
ROOT_SKILL_IDENTITY = ("SKILL.md", "reference", "rules", "kernel", "agents")


def harness_projections() -> tuple[tuple[str, str], ...]:
    """Repo-relative dest → repo-relative canonical source."""
    command_pins = sorted(p.name for p in (REPO_ROOT / "commands").glob("*.md"))
    pairs: list[tuple[str, str]] = []
    for provider in PROVIDERS:
        config_dir = provider["dir"]
        pairs.append((f"{config_dir}/skills/rust", "skills/rust"))
        if provider["commands"]:
            for name in command_pins:
                pairs.append((f"{config_dir}/commands/{name}", f"commands/{name}"))
    return tuple(pairs)


def load_canonical() -> dict:
    if not CANONICAL_PLUGIN.is_file():
        raise SystemExit(f"missing canonical manifest: {CANONICAL_PLUGIN}")
    data = json.loads(CANONICAL_PLUGIN.read_text(encoding="utf-8"))
    if not data.get("version"):
        raise SystemExit(f'{CANONICAL_PLUGIN} is missing "version"')
    return data


def dumps(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_or_check(path: Path, content: str, check: bool, drifts: list[str]) -> None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if current == content:
        return
    if check:
        drifts.append(rel)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {rel}")


def replace_or_append_version(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count != 1:
        raise SystemExit(f"{label} has no version line matching {pattern}")
    return updated


def set_skill_version(version: str, check: bool, drifts: list[str]) -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{SKILL_MD} has no YAML frontmatter")
    end = text.find("\n---", 3)
    if end == -1:
        raise SystemExit(f"{SKILL_MD} frontmatter is not closed")
    fm = text[4:end]
    body = text[end + 4 :]
    if re.search(r"^version:\s*", fm, flags=re.M):
        new_fm = re.sub(r"^version:\s*.*$", f"version: {version}", fm, count=1, flags=re.M)
    else:
        new_fm = fm.rstrip() + f"\nversion: {version}"
    write_or_check(SKILL_MD, f"---\n{new_fm}\n---{body}", check, drifts)


def set_spec_version(version: str, check: bool, drifts: list[str]) -> None:
    rules = RULES_MD.read_text(encoding="utf-8")
    write_or_check(
        RULES_MD,
        replace_or_append_version(
            rules,
            r"^# Rust 工程规范（注入版 v[0-9]+\.[0-9]+\.[0-9]+）$",
            f"# Rust 工程规范（注入版 v{version}）",
            str(RULES_MD),
        ),
        check,
        drifts,
    )
    if not check:
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "gen-rules-full.py")],
            check=True,
        )
    elif RULES_FULL.is_file():
        # --check: gen-rules-full.py --check is owned by check-consistency.sh
        pass


def expected_files(plugin: dict) -> dict[Path, str]:
    version = plugin["version"]
    name = plugin["name"]
    description = plugin["description"]
    author = plugin.get("author", {"name": "xxww"})
    license_id = plugin.get("license", "MIT")
    keywords = plugin.get("keywords", ["rust"])
    plugin_entry_description = (
        "Scoped Rust engineering playbooks with review, triage, "
        "framework overlays, project-local state, and evidence-driven validation"
    )

    claude_marketplace = {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": name,
        "version": version,
        "description": "Personal Rust engineering skills marketplace",
        "owner": {"name": author.get("name", "xxww")},
        "plugins": [
            {
                "name": name,
                "description": plugin_entry_description,
                "version": version,
                "source": "./",
                "category": "development",
            }
        ],
    }

    grok_plugin = {
        "name": name,
        "version": version,
        "description": description,
        "author": author,
        "license": license_id,
        "keywords": keywords,
    }
    grok_marketplace = {
        "name": name,
        "description": "Personal Rust engineering skills marketplace",
        "owner": {"name": author.get("name", "xxww")},
        "plugins": [
            {
                "name": name,
                "description": plugin_entry_description,
                "version": version,
                "category": "development",
                "source": {"type": "local", "path": "./"},
            }
        ],
    }

    cursor_plugin = {
        "name": name,
        "displayName": "Rust Skills",
        "version": version,
        "description": description,
        "author": author,
        "license": license_id,
        "keywords": keywords,
        "skills": "./skills/",
        "commands": "./commands/",
    }
    cursor_marketplace = {
        "name": name,
        "owner": {"name": author.get("name", "xxww")},
        "metadata": {
            "description": "Personal Rust engineering skills marketplace",
            "version": version,
        },
        "plugins": [
            {
                "name": name,
                "description": plugin_entry_description,
                "source": "./",
            }
        ],
    }

    codex_plugin = {
        "name": name,
        "version": version,
        "description": description,
        "author": author,
        "license": license_id,
        "keywords": keywords,
        "skills": "./skills/",
    }

    return {
        REPO_ROOT / ".claude-plugin" / "marketplace.json": dumps(claude_marketplace),
        REPO_ROOT / ".grok-plugin" / "plugin.json": dumps(grok_plugin),
        REPO_ROOT / ".grok-plugin" / "marketplace.json": dumps(grok_marketplace),
        REPO_ROOT / ".cursor-plugin" / "plugin.json": dumps(cursor_plugin),
        REPO_ROOT / ".cursor-plugin" / "marketplace.json": dumps(cursor_marketplace),
        REPO_ROOT / ".codex-plugin" / "plugin.json": dumps(codex_plugin),
    }


def _file_equal(a: Path, b: Path) -> bool:
    if not a.is_file() or not b.is_file():
        return False
    return a.read_bytes() == b.read_bytes()


def _tree_equal(a: Path, b: Path) -> bool:
    if a.is_file() and b.is_file():
        return _file_equal(a, b)
    if not a.is_dir() or not b.is_dir():
        return False
    a_files = {p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file()}
    b_files = {p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file()}
    if a_files != b_files:
        return False
    return all(_file_equal(a / rel, b / rel) for rel in a_files)


def _copy_replace(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_file() and not dst.is_symlink() and _file_equal(src, dst):
            return
        if dst.exists() or dst.is_symlink():
            if dst.is_dir() and not dst.is_symlink():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        shutil.copy2(src, dst)
        return
    dst.mkdir(parents=True, exist_ok=True)
    src_files = {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()}
    dst_files = (
        {p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file()} if dst.exists() else set()
    )
    for rel in dst_files - src_files:
        (dst / rel).unlink(missing_ok=True)
    for rel in src_files:
        s, d = src / rel, dst / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.is_file() and not d.is_symlink() and _file_equal(s, d):
            continue
        if d.is_symlink() or (d.exists() and d.is_dir()):
            if d.is_dir() and not d.is_symlink():
                shutil.rmtree(d)
            else:
                d.unlink()
        shutil.copy2(s, d)


def ensure_materialized(dest_rel: str, src_rel: str, check: bool, drifts: list[str]) -> None:
    """Write a standalone copy. Outbound relative symlinks are not an install unit."""
    dest = REPO_ROOT / dest_rel
    src = REPO_ROOT / src_rel
    if not src.exists():
        raise SystemExit(f"missing canonical source: {src_rel}")

    if dest.is_symlink():
        if check:
            drifts.append(dest_rel)
            return
        dest.unlink()
        _copy_replace(src, dest)
        print(f"copied {dest_rel} <- {src_rel} (replaced symlink)")
        return

    if dest.exists() and _tree_equal(dest, src):
        return
    if check:
        drifts.append(dest_rel)
        return
    if dest.exists():
        if dest.is_dir() and not dest.is_symlink():
            # Incremental copy below.
            pass
        else:
            dest.unlink()
    _copy_replace(src, dest)
    print(f"copied {dest_rel} <- {src_rel}")


def remove_root_skill_identity(check: bool, drifts: list[str]) -> None:
    for name in ROOT_SKILL_IDENTITY:
        path = REPO_ROOT / name
        if not path.exists() and not path.is_symlink():
            continue
        if check:
            drifts.append(name)
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"removed root skill-identity shim {name}")


def generate_command_pins() -> None:
    """Materialize slash pins for every command. review.md stays handwritten."""
    meta = json.loads((REPO_ROOT / "scripts" / "command-metadata.json").read_text(encoding="utf-8"))
    commands_dir = REPO_ROOT / "commands"
    commands_dir.mkdir(exist_ok=True)
    for name, spec in meta["commands"].items():
        path = commands_dir / f"{name}.md"
        if name == "review" and path.is_file():
            continue
        hint = spec.get("argumentHint") or ""
        summary = spec.get("summary") or name
        path.write_text(
            f"""---
description: /rust-skills:rust {name} pin
---


# /{name}

Pin. Load the rust skill and run `reference/{name}.md` on `$ARGUMENTS`.
{summary}. Args `{hint}`. Write policy is SKILL's — this pin cannot widen writes.
Equiv: `/rust-skills:rust {name} $ARGUMENTS`.
""",
            encoding="utf-8",
        )


def apply_activation(plugin: dict, check: bool, drifts: list[str]) -> None:
    act_path = REPO_ROOT / "scripts" / "activation.json"
    act = json.loads(act_path.read_text(encoding="utf-8"))
    desc = act["description"]
    if plugin.get("description") != desc:
        if check:
            drifts.append(".claude-plugin/plugin.json")
        else:
            plugin["description"] = desc
            CANONICAL_PLUGIN.write_text(dumps(plugin), encoding="utf-8")
            print("wrote .claude-plugin/plugin.json description from activation.json")
    verbs = "/".join(act["write_verbs_zh"]) + " or " + "/".join(act["write_verbs_en"])
    openai = (
        "interface:\n"
        '  display_name: "rust-skills"\n'
        '  short_description: "Cargo/Rust engineering workflows — review, craft, axum, Tauri, stack"\n'
        f'  default_prompt: "Use $rust-skills for Cargo/Rust work in the current repo. '
        f"Write only if the user said {verbs} or --apply. Explicit "
        f'review/audit/triage/doctor stay read-only even with --apply. Skip non-Cargo work and language trivia."\n'
        "policy:\n"
        "  allow_implicit_invocation: true\n"
        "compatibility:\n"
        '  canonical_format: "agent-skills"\n'
        "  adapter_targets:\n"
        '    - "openai"\n'
        '    - "claude"\n'
        '    - "generic"\n'
        "  activation:\n"
        '    mode: "implicit-on-cargo"\n'
        "  trust:\n"
        '    source_tier: "local"\n'
        '    remote_inline_execution: "forbid"\n'
        '    writes: "user-authorized-project-files-only"\n'
    )
    write_or_check(REPO_ROOT / "skills" / "rust" / "agents" / "openai.yaml", openai, check, drifts)
    text = SKILL_MD.read_text(encoding="utf-8")
    new, n = re.subn(r"^description:.*$", f"description: {desc}", text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("SKILL.md missing description line")
    write_or_check(SKILL_MD, new, check, drifts)


def regenerate_command_tables() -> None:
    """Rebuild SKILL.md/README command tables from command-metadata.json."""
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "gen-command-tables.py")],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()

    plugin = load_canonical()
    version = plugin["version"]
    drifts: list[str] = []

    if not args.check:
        regenerate_command_tables()
        generate_command_pins()
    else:
        meta = json.loads((REPO_ROOT / "scripts" / "command-metadata.json").read_text(encoding="utf-8"))
        for name in meta["commands"]:
            if not (REPO_ROOT / "commands" / f"{name}.md").is_file():
                drifts.append(f"commands/{name}.md")
    apply_activation(plugin, args.check, drifts)
    set_skill_version(version, args.check, drifts)
    set_spec_version(version, args.check, drifts)
    for path, content in expected_files(plugin).items():
        write_or_check(path, content, args.check, drifts)
    remove_root_skill_identity(args.check, drifts)
    for dest_rel, src_rel in harness_projections():
        ensure_materialized(dest_rel, src_rel, args.check, drifts)

    if args.check:
        if drifts:
            print("provider drift:", file=sys.stderr)
            for rel in drifts:
                print(f"  {rel}", file=sys.stderr)
            print("run ./scripts/sync-providers.py", file=sys.stderr)
            return 1
        print(f"OK: provider manifests and standalone harness trees match {version}")
        return 0

    print(f"OK: plugin/spec {version} synced to {', '.join(PROVIDER_NAMES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
