#!/usr/bin/env bash
set -euo pipefail

# Full-width parens in pressure-scenario titles (`（review）`) need a UTF-8
# locale. `LC_ALL=C` (common in CI) makes the grep shim treat the file as
# bytes and false-fail every command-coverage check.
_locale_now="${LC_ALL:-${LC_CTYPE:-${LANG:-C}}}"
if [[ "$_locale_now" == "C" || "$_locale_now" == "POSIX" ]]; then
  _utf8=""
  if command -v locale >/dev/null 2>&1; then
    if locale -a 2>/dev/null | grep -qiE '^C\.(UTF-8|utf8)$'; then
      _utf8=C.UTF-8
    elif locale -a 2>/dev/null | grep -qiE '^en_US\.(UTF-8|utf8)$'; then
      _utf8=en_US.UTF-8
    fi
  fi
  export LC_ALL="${_utf8:-C.UTF-8}"
fi
unset _locale_now _utf8

if ! command -v rg >/dev/null 2>&1; then
  printf 'WARN: rg not found; using a grep shim. Install ripgrep for identical CI/local behavior.\n' >&2
  rg() {
    local quiet=0 only_matching=0
    local pattern=""
    local -a files=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        -q) quiet=1 ;;
        -o) only_matching=1 ;;
        -n|--no-filename) ;;
        -*)
          # Combined short flags from callers (`-qF`, `-n`).
          [[ "$1" == *q* ]] && quiet=1
          [[ "$1" == *o* ]] && only_matching=1
          ;;
        *)
          if [[ -z "$pattern" ]]; then
            pattern=$1
          else
            files+=("$1")
          fi
          ;;
      esac
      shift
    done
    if [[ -z "$pattern" || ${#files[@]} -eq 0 ]]; then
      printf 'rg shim: missing pattern or file\n' >&2
      return 2
    fi
    local f
    for f in "${files[@]}"; do
      if [[ ! -e "$f" ]]; then
        printf 'rg shim: no such file: %s\n' "$f" >&2
        return 2
      fi
    done
    if (( only_matching )); then
      grep -R -h -oE "$pattern" "${files[@]}"
      return
    fi
    if (( quiet )); then
      grep -R -qE "$pattern" "${files[@]}"
      return
    fi
    grep -R -E "$pattern" "${files[@]}"
  }
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_consis_tmp="$(mktemp -d)"
trap 'rm -rf "$_consis_tmp"' EXIT
skill_file="$repo_root/skills/rust/SKILL.md"
rules_file="$repo_root/skills/rust/rules/rules-full.md"
namespace_file="$repo_root/skills/rust/rules/namespaces.txt"
reference_dir="$repo_root/skills/rust/reference"
kernel_dir="$repo_root/skills/rust/kernel"
scenarios_file="$repo_root/tests/pressure-scenarios.md"

failed=0

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failed=1
}

for required in "$skill_file" "$rules_file" "$namespace_file" "$scenarios_file"; do
  [[ -f "$required" ]] || fail "required file missing: ${required#$repo_root/}"
done
[[ -d "$reference_dir" ]] || fail "required directory missing: ${reference_dir#$repo_root/}"
[[ -d "$kernel_dir" ]] || fail "required directory missing: ${kernel_dir#$repo_root/}"
for kf in scope.md evidence.md finding.md write.md verification.md swarm.md; do
  [[ -f "$kernel_dir/$kf" ]] || fail "kernel file missing: kernel/$kf"
done
rg -q 'Patch' "$kernel_dir/write.md" || fail "kernel/write.md missing Patch contract"
rg -q 'check_patch' "$kernel_dir/verification.md" || fail "kernel/verification.md missing check_patch"
rg -q 'inspect_project.py' "$kernel_dir/swarm.md" || fail "kernel/swarm.md missing inspect_project merge"
rg -q 'kernel/swarm.md' "$skill_file" || fail "SKILL.md does not load kernel/swarm.md"
rg -q 'kernel/write.md' "$reference_dir/craft.md" || fail "craft.md does not load kernel/write.md"
rg -q 'render_rust_md.py' "$reference_dir/document.md" || fail "document.md does not use render_rust_md.py"
rg -q '编排：禁止 swarm' "$reference_dir/craft.md" || fail "craft.md must forbid swarm"
rg -q '编排：禁止 swarm' "$reference_dir/triage.md" || fail "triage.md must forbid swarm"

if ! python3 - "$kernel_dir/swarm.md" "$reference_dir" <<'PY'
from pathlib import Path
import re, sys
swarm, refdir = Path(sys.argv[1]), Path(sys.argv[2])
text = swarm.read_text(encoding="utf-8")
# rows like | `review` | ...
open_cmds = re.findall(r"^\| `([a-z]+)` \|", text, re.M)
failed = 0
for name in open_cmds:
    p = refdir / f"{name}.md"
    if not p.is_file():
        print(f"FAIL: swarm open command missing playbook: {name}", file=sys.stderr)
        failed = 1
        continue
    body = p.read_text(encoding="utf-8")
    if "kernel/swarm.md" not in body:
        print(f"FAIL: {name}.md is in swarm open table but does not load kernel/swarm.md", file=sys.stderr)
        failed = 1
raise SystemExit(failed)
PY
then
  fail "swarm open-table playbooks missing kernel/swarm.md pointer"
fi



for pb in review document doctor crate; do
  rg -q 'ProjectSnapshot' "$reference_dir/$pb.md" || fail "$pb.md does not consume ProjectSnapshot"
done

if (( failed != 0 )); then
  exit 1
fi

# One-level scanners (DeepSeek Harness) that receive this repo as a skill
# directory look for ./SKILL.md, not ./skills/rust/SKILL.md.
if ! python3 "$repo_root/scripts/check-root-compat.py"; then
  fail "pack root is not a one-level skill directory"
fi

command_names() {
  awk -F'`' '/^\| `/{split($2, parts, " "); print parts[1]}' "$skill_file" | sort -u
}

reference_names() {
  for path in "$reference_dir"/*.md; do
    name="$(basename "$path" .md)"
    if [[ "$name" != "routing" && "$name" != "craft" && "$name" != "engage" && "$name" != "testing" ]]; then
      printf '%s\n' "$name"
    fi
  done | sort -u
}

command_names >"$_consis_tmp/cmds"
reference_names >"$_consis_tmp/refs"
missing_references="$(comm -23 "$_consis_tmp/cmds" "$_consis_tmp/refs")"
orphan_references="$(comm -13 "$_consis_tmp/cmds" "$_consis_tmp/refs")"
[[ -z "$missing_references" ]] || fail "commands without reference files: $missing_references"
[[ -z "$orphan_references" ]] || fail "reference files without commands: $orphan_references"

readme_commands() {
  sed -nE 's#^/rust-skills:rust ([a-z]+).*#\1#p' "$repo_root/README.md" | sort -u
}

readme_commands >"$_consis_tmp/readme"
missing_readme_commands="$(comm -23 "$_consis_tmp/cmds" "$_consis_tmp/readme")"
extra_readme_commands="$(comm -13 "$_consis_tmp/cmds" "$_consis_tmp/readme")"
[[ -z "$missing_readme_commands" ]] || fail "commands missing from README: $missing_readme_commands"
[[ -z "$extra_readme_commands" ]] || fail "README commands missing from skill table: $extra_readme_commands"

if ! python3 "$repo_root/scripts/gen-command-tables.py" --check; then
  fail "command tables drifted from scripts/command-metadata.json; run ./scripts/gen-command-tables.py"
fi

if ! python3 "$repo_root/scripts/gen-rules-full.py" --check; then
  fail "rules-full.md drifted from domain files; run ./scripts/gen-rules-full.py"
fi

rule_ids="$(sed -nE 's/^- ([A-Z]+-[0-9]+)\[[MSY]\].*/\1/p' "$rules_file")"
duplicate_ids="$(printf '%s\n' "$rule_ids" | sort | uniq -d)"
[[ -z "$duplicate_ids" ]] || fail "duplicate graded rule ids: $duplicate_ids"

ungraded_ids="$(grep -E '^- [A-Z]{2,}-[0-9]+' "$rules_file" | grep -vE '^- [A-Z]{2,}-[0-9]+\[[MSY]\]' || true)"
[[ -z "$ungraded_ids" ]] || fail "rule lines missing a [M]/[S]/[Y] grade: $ungraded_ids"

while read -r prefix kind owner; do
  [[ "$prefix" == "#" || -z "$prefix" ]] && continue
  [[ -f "$repo_root/skills/rust/$owner" ]] || fail "namespace $prefix has missing owner: $owner"
  if [[ "$kind" == "local" ]] && ! rg -q "${prefix}-[0-9]+" "$repo_root/skills/rust/$owner"; then
    fail "local namespace $prefix is not defined by owner $owner"
  fi
done < "$namespace_file"

if ! python3 - "$repo_root" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
skill_root = root / "skills" / "rust"
reference_dir = skill_root / "reference"
registrations = []
for line in (skill_root / "rules" / "namespaces.txt").read_text(encoding="utf-8").splitlines():
    if not line or line.startswith("#"):
        continue
    prefix, kind, owner = line.split()
    if kind == "local":
        registrations.append((prefix, skill_root / owner))

failed = False
references = list(reference_dir.rglob("*.md"))
kernel_dir = skill_root / "kernel"
kernel_files = list(kernel_dir.rglob("*.md")) if kernel_dir.is_dir() else []
skill_file = skill_root / "SKILL.md"
scenarios_file = root / "tests" / "pressure-scenarios.md"
sources = []
for path in [*references, *kernel_files, skill_file]:

    lines = list(enumerate(path.read_text(encoding="utf-8").splitlines(), 1))
    sources.append((path, lines))
scenario_acceptance = [
    (line_number, line)
    for line_number, line in enumerate(
        scenarios_file.read_text(encoding="utf-8").splitlines(), 1
    )
    if line.startswith("验收：")
]
sources.append((scenarios_file, scenario_acceptance))
for prefix, owner in registrations:
    owner_text = owner.read_text(encoding="utf-8")
    defined = {int(value) for value in re.findall(rf"\b{re.escape(prefix)}-(\d+)\b", owner_text)}
    if not defined:
        print(f"FAIL: local namespace {prefix} has no ids in {owner.relative_to(root)}", file=sys.stderr)
        failed = True
        continue

    expected = set(range(min(defined), max(defined) + 1))
    if defined != expected:
        missing = ", ".join(f"{prefix}-{number:02d}" for number in sorted(expected - defined))
        print(f"FAIL: local namespace {prefix} is not continuous; missing {missing}", file=sys.stderr)
        failed = True

    definition = re.compile(rf"^\s*(?:[-*]\s+|#{{1,6}}\s+|\|\s*){re.escape(prefix)}-(\d+)\b")
    reference = re.compile(rf"\b{re.escape(prefix)}-(\d+)\b")
    for path, lines in sources:
        for line_number, line in lines:
            match = definition.search(line)
            if match and path != owner:
                print(
                    f"FAIL: {prefix}-{match.group(1)} defined outside owner: "
                    f"{path.relative_to(root)}:{line_number}",
                    file=sys.stderr,
                )
                failed = True
            for value in reference.findall(line):
                if int(value) not in defined:
                    print(
                        f"FAIL: undefined local rule reference {prefix}-{value}: "
                        f"{path.relative_to(root)}:{line_number}",
                        file=sys.stderr,
                    )
                    failed = True

raise SystemExit(failed)
PY
then
  fail "local namespace ownership, continuity, or references are invalid"
fi

defined_core_ids="$(rg -o --no-filename '[A-Z]+-[0-9]+' "$rules_file" | sort -u)"
while IFS= read -r rule_id; do
  prefix="${rule_id%%-*}"
  namespace_kind="$(awk -v wanted="$prefix" '$1 == wanted {print $2}' "$namespace_file")"
  [[ "$namespace_kind" == "global" ]] || fail "graded rule $rule_id lacks a global namespace registration"
done <<<"$rule_ids"

{
  rg -o --no-filename '[A-Z]+-[0-9]+' "$reference_dir" "$kernel_dir" "$skill_file"
  sed -n '/^验收：/p' "$scenarios_file" | grep -oE '[A-Z]+-[0-9]+' || true
} | sort -u >"$_consis_tmp/rule_refs"


while IFS= read -r rule_ref; do
  [[ "$rule_ref" == "UTF-8" ]] && continue
  prefix="${rule_ref%%-*}"
  namespace_kind="$(awk -v wanted="$prefix" '$1 == wanted {print $2}' "$namespace_file")"
  if [[ -z "$namespace_kind" ]]; then
    fail "unknown rule reference: $rule_ref"
  elif [[ "$namespace_kind" != "local" ]] && ! grep -qx "$rule_ref" <<<"$defined_core_ids"; then
    fail "undefined core rule reference: $rule_ref"
  fi
done <"$_consis_tmp/rule_refs"

while IFS= read -r command; do
  if ! rg -q "^### .*[（(]${command}[）)]$" "$scenarios_file"; then
    fail "command without an independent pressure scenario: $command"
  fi
done <"$_consis_tmp/cmds"

printf '%s\n' "$reference_dir"/*.md >"$_consis_tmp/ref_files"
while IFS= read -r reference; do
  [[ "$(basename "$reference")" == "routing.md" ]] && continue
  rg -q '^目的：' "$reference" || fail "reference lacks an explicit purpose: ${reference#$repo_root/}"
done <"$_consis_tmp/ref_files"

for domain in async concurrency process axum tauri seaorm sqlx serde obs name cli ship xplat; do
  domain_file="$reference_dir/$domain.md"
  if ! rg -q '只读调用' "$domain_file" || ! rg -q '明确“修/改/实现”' "$domain_file"; then
    fail "domain reference lacks explicit read/apply output modes: ${domain_file#$repo_root/}"
  fi
done

if ! python3 - "$skill_file" "$reference_dir" <<'PY'
from pathlib import Path
import re
import sys

skill = Path(sys.argv[1]).read_text(encoding="utf-8")
ref_dir = Path(sys.argv[2])
match = re.search(r"^## 写入边界.*?\n(.*?)(?=\n## )", skill, re.S | re.M)
if not match:
    print("FAIL: SKILL.md is missing the 写入边界 section", file=sys.stderr)
    raise SystemExit(True)
section = match.group(1)

readonly = ("review", "audit", "triage", "doctor")
advice = ("shape", "crate", "stack")
inspect_first = (
    "harden", "modernize", "distill", "slim", "gate", "bench",
    "concurrency", "process", "async", "serde", "obs", "name", "axum", "tauri",
    "seaorm", "sqlx", "cli", "ship", "xplat",
)

failed = False

def fail(msg: str) -> None:
    global failed
    print(f"FAIL: {msg}", file=sys.stderr)
    failed = True

def bullet_has(heading: str, names: tuple[str, ...]) -> None:
    for line in section.splitlines():
        if heading in line:
            missing = [name for name in names if f"`{name}`" not in line]
            if missing:
                fail(f"写入边界「{heading}」missing {', '.join(missing)}")
            return
    fail(f"写入边界 missing heading {heading}")

bullet_has("评审类永远只读", readonly)
bullet_has("改造/语言语义/框架/交付类先体检", inspect_first)
bullet_has("shape", advice)

for name in readonly:
    text = (ref_dir / f"{name}.md").read_text(encoding="utf-8")
    purpose = ""
    for line in text.splitlines():
        if line.startswith("目的："):
            purpose = line
            break
    if "只读" not in purpose:
        fail(f"{name}.md 目的 must declare 只读 (SKILL 写入边界)")
    for match in re.finditer(r"`--apply`(.{0,16})", text):
        ctx = match.group(1)
        if not re.search(r"不适用|不授权|禁止|不得|不写", ctx):
            fail(f"{name}.md authorizes --apply to write code: `--apply`{ctx}")

for name in advice:
    text = (ref_dir / f"{name}.md").read_text(encoding="utf-8")
    if not any(token in text for token in ("不写码", "不是代码", "永不写码")):
        fail(f"{name}.md is advice-only but does not forbid writing code")

raise SystemExit(failed)
PY
then
  fail "write-boundary classification drifted from references"
fi

if ! python3 - "$scenarios_file" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
blocks = re.split(r"(?m)(?=^### 场景 \d+：)", text)[1:]
failed = False
for block in blocks:
    title = block.splitlines()[0]
    missing = [label for label in ("提问：", "坏答案：", "验收：") if label not in block]
    if missing:
        print(f"FAIL: {title} missing {', '.join(missing)}", file=sys.stderr)
        failed = True
raise SystemExit(failed)
PY
then
  fail "pressure scenario schema is incomplete"
fi

for contract_marker in \
  'contract:rust-md-composition' \
  'branch:DEP-07:no-track' \
  'branch:DEP-07:track' \
  'branch:rust-md-marker-migration' \
  'branch:docs:read-only' \
  'branch:docs:write'
do
  if ! rg -q "^覆盖：.*${contract_marker}" "$scenarios_file"; then
    fail "missing pressure contract marker: $contract_marker"
  fi
done

# Framework deep-dive playbooks live in reference/<command>/*.md. They are not
# commands: the owner reference/<command>.md must exist and link every file.
for subdir in "$reference_dir"/*/; do
  [[ -d "$subdir" ]] || continue
  owner_name="$(basename "$subdir")"
  owner_file="$reference_dir/$owner_name.md"
  [[ -f "$owner_file" ]] || fail "reference sub-directory without owner command: reference/$owner_name/"
  for sub in "$subdir"*.md; do
    [[ -f "$sub" ]] || continue
    sub_rel="$owner_name/$(basename "$sub")"
    rg -q '^目的：' "$sub" || fail "sub-reference lacks an explicit purpose: reference/$sub_rel"
    if [[ -f "$owner_file" ]] && ! rg -qF "($sub_rel)" "$owner_file"; then
      fail "sub-reference not linked from owner reference/$owner_name.md: reference/$sub_rel"
    fi
  done
done

if rg -q 'apply 主操作|借用 apply' "$skill_file" "$reference_dir"; then
  fail "undefined apply operation remains in routing"
fi

if rg -n '规范版本 v[0-9]+\.[0-9]+\.[0-9]+' "$reference_dir" >/dev/null; then
  fail "reference hard-codes the current spec version; read SKILL frontmatter at runtime"
fi

if ! python3 "$repo_root/scripts/eval-fixtures.py"; then
  fail "fixture eval contracts drifted; see scripts/eval-fixtures.py"
fi
if ! python3 "$repo_root/scripts/inspect_project.py" --check-fixtures; then
  fail "project snapshot fixtures drifted; see scripts/inspect_project.py"
fi
if ! python3 "$repo_root/scripts/check_patch.py" --check-fixtures; then
  fail "check_patch fixtures drifted; see scripts/check_patch.py"
fi
if ! python3 "$repo_root/scripts/render_rust_md.py" --check-fixtures; then
  fail "RUST.md projection fixtures drifted; see scripts/render_rust_md.py"
fi

if ! python3 "$repo_root/scripts/eval-triggers.py"; then
  fail "trigger eval drifted; see scripts/eval-triggers.py"
fi

if ! python3 "$repo_root/scripts/check-floor.py"; then
  fail "version floor drifted; see scripts/version-floor.json"
fi

if ! python3 "$repo_root/scripts/sync-providers.py" --check; then
  fail "provider manifests or harness links drifted; run ./scripts/sync-providers.py"
fi

if rg -n '(^|[[:space:]`])/rust([ `]|$)|105 条|13/13|build_override_paired' \
  "$repo_root/README.md" "$repo_root/.claude-plugin" "$repo_root/.grok-plugin" \
  "$repo_root/.cursor-plugin" "$repo_root/.codex-plugin" "$repo_root/commands" \
  "$repo_root/skills" "$repo_root/tests" >/dev/null; then
  fail "stale bare command, count, or removed check remains"
fi

command_count="$(command_names | wc -l | tr -d ' ')"
rule_count="$(printf '%s\n' "$rule_ids" | sed '/^$/d' | wc -l | tr -d ' ')"

rg -o --no-filename '[0-9]+ 条(分级)?规则' \
  "$repo_root/README.md" "$repo_root/skills" "$repo_root/tests" | sed -E 's/ .*//' | sort -u >"$_consis_tmp/stated_counts"
while IFS= read -r stated_count; do
  [[ "$stated_count" == "$rule_count" ]] || fail "stale stated rule count: $stated_count (actual $rule_count)"
done <"$_consis_tmp/stated_counts"

if (( failed != 0 )); then
  exit 1
fi

printf 'OK: %s commands, %s unique graded rules, references and pressure coverage consistent\n' \
  "$command_count" "$rule_count"
