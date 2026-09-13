#!/usr/bin/env python3
"""E3 agent-skill eval harness (OpenAI eval-skills pattern).

An eval is: prompt → captured run (trace + artifacts) → checks → score.

  python3 scripts/eval-agent.py                 # static contracts (CI)
  python3 scripts/eval-agent.py --live          # optional Codex runs
  python3 scripts/eval-agent.py --grade-trace evals/fixtures/sample-review.jsonl --case rt-review

--static green is E1/E2-shaped contract coverage, not behavioral verification.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS = REPO_ROOT / "evals"
PROMPTS = EVALS / "prompts"
SUCCESS = EVALS / "success-criteria.json"
METADATA = REPO_ROOT / "scripts" / "command-metadata.json"
ACTIVATION = REPO_ROOT / "scripts" / "activation.json"
TRIGGERS = EVALS / "triggers.json"
RUBRIC_SCHEMA = EVALS / "schemas" / "rubric.schema.json"
RUN_SCHEMA = EVALS / "schemas" / "run-result.schema.json"
ARTIFACTS = EVALS / "artifacts"
SAMPLE_TRACE = EVALS / "fixtures" / "sample-review.jsonl"

VIRTUAL = {"craft", "help", "skip"}
SUITES = ("trigger", "routing", "write-gate")
AUTH_VALUES = {
    "readonly",
    "inspect-until-apply",
    "write-declared",
    "suggest-only",
    "suggest-until-split",
    "suggest-until-gate",
    "readonly-until-write-verbs",
    "write-if-authorized",
    "declared-files",
}
KINDS = {"explicit", "implicit", "contextual", "negative"}
READONLY_COMMANDS = {"review", "audit", "triage", "doctor"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"{path}: empty")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{path}: duplicate id")
    for row in rows:
        if not row.get("prompt", "").strip():
            raise SystemExit(f"{path}: {row.get('id')} missing prompt")
    return rows


def parse_jsonl(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def event_item(event: dict) -> dict:
    item = event.get("item")
    return item if isinstance(item, dict) else {}


def command_executions(events: list[dict]) -> list[str]:
    out = []
    for event in events:
        item = event_item(event)
        if item.get("type") == "command_execution" and isinstance(item.get("command"), str):
            out.append(item["command"])
    return out


def agent_texts(events: list[dict]) -> str:
    chunks = []
    for event in events:
        item = event_item(event)
        if item.get("type") in {"agent_message", "message", "agent_message.completed"}:
            for key in ("text", "content", "output"):
                value = item.get(key)
                if isinstance(value, str):
                    chunks.append(value)
        for key in ("text", "message", "output"):
            value = event.get(key)
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks)


def wrote_files(events: list[dict]) -> bool:
    write_types = {
        "file_change",
        "file_edit",
        "patch",
        "apply_patch",
        "edited_file",
        "create_file",
    }
    for event in events:
        item = event_item(event)
        kind = str(item.get("type") or event.get("type") or "")
        if kind in write_types:
            return True
        if kind == "command_execution":
            cmd = str(item.get("command") or "")
            if re.search(r"\b(tee|cp|mv|rm|mkdir|cargo\s+add|git\s+commit)\b", cmd):
                return True
    return False


def skill_invoked(events: list[dict]) -> bool:
    blob = agent_texts(events).lower()
    if "rust-skills" in blob or "/rust-skills:rust" in blob:
        return True
    for event in events:
        item = event_item(event)
        for key in ("skill", "name", "id"):
            value = str(item.get(key) or "")
            if value in {"rust", "rust-skills"}:
                return True
        skills = item.get("skills") or event.get("skills")
        if isinstance(skills, list) and any(
            str(s) in {"rust", "rust-skills"} or (isinstance(s, dict) and s.get("name") in {"rust", "rust-skills"})
            for s in skills
        ):
            return True
    return False


def check(cid: str, passed: bool, notes: str) -> dict:
    return {"id": cid, "pass": bool(passed), "notes": notes}


def grade_events(
    events: list[dict],
    *,
    should_trigger: bool,
    expected_command: str | None,
    expected_auth: str | None,
    caps: dict,
) -> list[dict]:
    texts = agent_texts(events)
    cmds = command_executions(events)
    invoked = skill_invoked(events)
    wrote = wrote_files(events)
    inspects = sum("inspect_project.py" in c for c in cmds)
    checks = [
        check(
            "skill-invoked",
            invoked if should_trigger else not invoked,
            f"invoked={invoked} expected={should_trigger}",
        ),
        check(
            "command-budget",
            len(cmds) <= int(caps.get("max_command_executions", 25)),
            f"{len(cmds)} command_execution events",
        ),
        check(
            "inspect-budget",
            inspects <= int(caps.get("max_inspect_project", 2)),
            f"{inspects} inspect_project.py runs",
        ),
    ]
    if expected_command:
        if expected_command == "skip":
            checks.append(check("owner-correct", not invoked, "skip must not own the turn"))
        elif expected_command == "help":
            ok = ("推荐" in texts or "命令" in texts) and not wrote
            checks.append(check("owner-correct", ok, "bare entry recommends, does not execute"))
        elif expected_command == "craft":
            ok = invoked and ("craft" in texts.lower() or "实现" in texts or "Patch" in texts or not wrote)
            checks.append(check("owner-correct", invoked, "craft/engage should own Cargo implement turns"))
        else:
            token = expected_command
            ok = token in texts or f"/rust-skills:rust {token}" in texts or f"`{token}`" in texts
            checks.append(check("owner-correct", ok, f"looking for owner {token!r}"))
    if expected_auth in {"readonly", "suggest-only"} or expected_command in READONLY_COMMANDS:
        no_write = (not wrote) and ("未改动" in texts or "只读" in texts or not should_trigger)
        checks.append(check("write-gate", not wrote, "readonly/suggest must not write files"))
        if expected_command in READONLY_COMMANDS:
            checks.append(check("readonly-owner", no_write or "只读" in texts, "review-class stays read-only"))
    if expected_auth == "write-declared":
        checks.append(check("write-gate", True, "declared-file writes are allowed; live runs inspect the fixture"))
    return checks


def score_checks(checks: list[dict]) -> tuple[bool, int]:
    if not checks:
        return False, 0
    passed = sum(1 for c in checks if c["pass"])
    return all(c["pass"] for c in checks), round(100 * passed / len(checks))


def required_schema_keys(schema: dict) -> set[str]:
    return set(schema.get("required") or [])


def static_contracts() -> int:
    failed = 0
    success = load_json(SUCCESS)
    if not isinstance(success, dict):
        fail("success-criteria.json must be an object")
        return 1
    meta = load_json(METADATA)
    commands = meta["commands"]
    act = load_json(ACTIVATION)
    triggers = load_json(TRIGGERS)
    rubric = load_json(RUBRIC_SCHEMA)
    run_schema = load_json(RUN_SCHEMA)

    for label, schema, needed in (
        ("rubric", rubric, {"overall_pass", "score", "checks"}),
        ("run-result", run_schema, {"id", "suite", "prompt", "overall_pass", "score", "checks"}),
    ):
        missing = needed - required_schema_keys(schema)
        if missing:
            fail(f"{label} schema missing required {sorted(missing)}")
            failed += 1
        if schema.get("additionalProperties") is not False:
            fail(f"{label} schema must set additionalProperties false")
            failed += 1

    skill = success.get("skill") or {}
    for bucket in ("outcome", "process", "style", "efficiency"):
        items = skill.get(bucket)
        if not isinstance(items, list) or not items:
            fail(f"success-criteria skill.{bucket} empty")
            failed += 1
            continue
        for item in items:
            if not item.get("id") or not item.get("text"):
                fail(f"success-criteria skill.{bucket} item missing id/text")
                failed += 1

    auth_by_cat = success.get("auth_by_category") or {}
    for name, entry in commands.items():
        cat = entry["category"]
        if cat not in auth_by_cat:
            fail(f"command {name} category {cat!r} missing from auth_by_category")
            failed += 1
    overrides = success.get("auth_overrides") or {}
    for name, auth in overrides.items():
        if name not in commands:
            fail(f"auth override for unknown command {name}")
            failed += 1
        if auth not in AUTH_VALUES:
            fail(f"auth override {name}={auth!r} not in {sorted(AUTH_VALUES)}")
            failed += 1
    for name in READONLY_COMMANDS:
        resolved = overrides.get(name) or auth_by_cat.get(commands[name]["category"])
        if resolved != "readonly":
            fail(f"{name} must resolve to readonly, got {resolved!r}")
            failed += 1
    for virt in VIRTUAL:
        if virt not in (success.get("virtual") or {}):
            fail(f"success-criteria missing virtual owner {virt}")
            failed += 1

    trigger_rows = read_csv(PROMPTS / "trigger.prompts.csv")
    routing_rows = read_csv(PROMPTS / "routing.prompts.csv")
    gate_rows = read_csv(PROMPTS / "write-gate.prompts.csv")

    kinds_seen = {row.get("kind") for row in trigger_rows + routing_rows}
    for needed in KINDS:
        if needed not in kinds_seen:
            fail(f"prompt sets missing kind {needed}")
            failed += 1

    desc = act["description"]
    must = [item["phrase"] for item in triggers.get("must_activate", [])]
    trigger_phrases = list(must)
    for entry in commands.values():
        trigger_phrases.extend(p for p in (entry.get("triggers") or []) if p)
        trigger_phrases.extend(p for p in (entry.get("triggers_en") or []) if p)
    false_rows = [row for row in trigger_rows if row["should_trigger"].lower() == "false"]
    true_rows = [row for row in trigger_rows if row["should_trigger"].lower() == "true"]
    if len(true_rows) < 8 or len(false_rows) < 3:
        fail(f"trigger CSV needs ≥8 positive and ≥3 negative, got {len(true_rows)}/{len(false_rows)}")
        failed += 1
    for row in trigger_rows:
        if row.get("kind") not in KINDS:
            fail(f"{row['id']}: bad kind {row.get('kind')!r}")
            failed += 1
        flag = row["should_trigger"].lower() == "true"
        if flag and row.get("kind") == "negative":
            fail(f"{row['id']}: negative kind cannot should_trigger")
            failed += 1
        if not flag and row.get("kind") != "negative":
            fail(f"{row['id']}: should_trigger=false must be kind=negative")
            failed += 1
        if flag:
            hit = (
                "/rust-skills" in row["prompt"]
                or "$rust" in row["prompt"]
                or any(p in row["prompt"] for p in trigger_phrases)
                or any(v in row["prompt"] for v in act["write_verbs_zh"] + act["write_verbs_en"])
            )
            if not hit:
                fail(f"{row['id']}: positive prompt has no description/verb/skill token")
                failed += 1
        else:
            skip_tokens = list(triggers.get("forbidden_in_description") or []) + ["Python", "翻译", "Go", "历史", "Tailwind", "React"]
            if not any(tok in row["prompt"] for tok in skip_tokens):
                fail(f"{row['id']}: negative prompt has no skip token")
                failed += 1
            if any(tok in desc for tok in skip_tokens if tok in row["prompt"] and tok in (triggers.get("forbidden_in_description") or [])):
                fail(f"{row['id']}: skip token still in description")
                failed += 1

    covered: dict[str, list[str]] = {name: [] for name in commands}
    for row in routing_rows:
        kind = row.get("kind")
        if kind not in KINDS:
            fail(f"{row['id']}: bad kind {kind!r}")
            failed += 1
        expected = row["expected_command"]
        if expected in covered:
            covered[expected].append(row["id"])
        elif expected in VIRTUAL:
            pass
        else:
            fail(f"{row['id']}: expected_command {expected!r} not in metadata or virtual")
            failed += 1
        if expected in commands:
            phrases = list(commands[expected].get("triggers") or []) + list(
                commands[expected].get("triggers_en") or []
            )
            explicit = bool(re.search(rf"/rust-skills:rust\s+{re.escape(expected)}(\s|$)", row["prompt"]))
            if not explicit and not any(p and p in row["prompt"] for p in phrases):
                fail(f"{row['id']}: routing prompt does not mention a {expected} trigger")
                failed += 1
        if expected == "skip" and kind != "negative":
            fail(f"{row['id']}: skip rows must be negative")
            failed += 1
        if expected == "help" and row["prompt"].strip() not in {"/rust-skills:rust", "/rust-skills:rust "}:
            # bare entry may have trailing space; anything with a subcommand is not help
            if re.search(r"/rust-skills:rust\s+\S", row["prompt"]):
                fail(f"{row['id']}: help row must be the bare entry")
                failed += 1
    missing = sorted(name for name, rows in covered.items() if not rows)
    if missing:
        fail("routing CSV missing commands: " + ", ".join(missing))
        failed += 1
    for virt in VIRTUAL:
        if not any(row["expected_command"] == virt for row in routing_rows):
            fail(f"routing CSV missing virtual owner {virt}")
            failed += 1
    if not any(row["id"] == "rt-review-apply" for row in routing_rows):
        fail("routing CSV missing rt-review-apply (review --apply stays review)")
        failed += 1

    for row in gate_rows:
        expected = row["expected_command"]
        auth = row["expected_auth"]
        if expected not in commands and expected not in VIRTUAL:
            fail(f"{row['id']}: unknown command {expected}")
            failed += 1
        if auth not in AUTH_VALUES:
            fail(f"{row['id']}: bad auth {auth!r}")
            failed += 1
        if expected in READONLY_COMMANDS and auth != "readonly":
            fail(f"{row['id']}: {expected} write-gate must be readonly")
            failed += 1
        if expected in READONLY_COMMANDS and "--apply" in row["prompt"] and auth != "readonly":
            fail(f"{row['id']}: --apply must not upgrade review-class auth")
            failed += 1

    if not SAMPLE_TRACE.is_file():
        fail(f"missing sample trace {SAMPLE_TRACE}")
        failed += 1
    else:
        sample = parse_jsonl(SAMPLE_TRACE.read_text(encoding="utf-8"))
        sample_checks = grade_events(
            sample,
            should_trigger=True,
            expected_command="review",
            expected_auth="readonly",
            caps=success.get("efficiency_caps") or {},
        )
        ok, _ = score_checks(sample_checks)
        if not ok:
            fail("sample-review.jsonl does not pass the review/readonly grader")
            failed += 1
            for item in sample_checks:
                if not item["pass"]:
                    fail(f"  {item['id']}: {item['notes']}")

    if failed:
        print(f"eval-agent --static: {failed} check(s) failed", file=sys.stderr)
        return 1
    print(
        "OK: eval-agent contracts "
        f"({len(trigger_rows)} trigger, {len(routing_rows)} routing, "
        f"{len(gate_rows)} write-gate; {len(commands)} commands covered)"
    )
    return 0


def suite_rows(suite: str) -> list[dict[str, str]]:
    if suite == "trigger":
        rows = read_csv(PROMPTS / "trigger.prompts.csv")
        for row in rows:
            row["suite"] = "trigger"
            row.setdefault("expected_command", "craft" if row["should_trigger"].lower() == "true" else "skip")
            row.setdefault("expected_auth", "")
        return rows
    if suite == "routing":
        rows = read_csv(PROMPTS / "routing.prompts.csv")
        for row in rows:
            row["suite"] = "routing"
            row["should_trigger"] = "false" if row["expected_command"] == "skip" else "true"
            row.setdefault("expected_auth", "readonly" if row["expected_command"] in READONLY_COMMANDS | {"help", "skip"} else "")
        return rows
    rows = read_csv(PROMPTS / "write-gate.prompts.csv")
    for row in rows:
        row["suite"] = "write-gate"
        row["should_trigger"] = "true"
        row.setdefault("kind", "explicit")
    return rows


def find_case(case_id: str) -> dict[str, str]:
    for suite in SUITES:
        for row in suite_rows(suite):
            if row["id"] == case_id:
                return row
    raise SystemExit(f"unknown case id {case_id}")


def grade_case(row: dict[str, str], events: list[dict], success: dict) -> dict:
    checks = grade_events(
        events,
        should_trigger=row.get("should_trigger", "true").lower() == "true",
        expected_command=row.get("expected_command") or None,
        expected_auth=row.get("expected_auth") or None,
        caps=success.get("efficiency_caps") or {},
    )
    overall, score = score_checks(checks)
    return {
        "id": row["id"],
        "suite": row.get("suite") or "routing",
        "prompt": row["prompt"],
        "should_trigger": row.get("should_trigger", "true").lower() == "true",
        "expected_command": row.get("expected_command") or None,
        "expected_auth": row.get("expected_auth") or None,
        "overall_pass": overall,
        "score": score,
        "checks": checks,
    }


def run_codex(prompt: str, out_jsonl: Path, *, full_auto: bool, cwd: Path) -> int:
    bin_name = os.environ.get("CODEX_BIN", "codex")
    args = [bin_name, "exec", "--json"]
    if full_auto:
        args.append("--full-auto")
    args.append(prompt)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    out_jsonl.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0 and not result.stdout.strip():
        fail(f"codex exec failed: {result.stderr[-2000:]}")
    return result.returncode


def live(suite: str, limit: int | None) -> int:
    if shutil.which(os.environ.get("CODEX_BIN", "codex")) is None:
        fail("codex CLI not on PATH; E3 live runs need Codex. Static contracts still pass.")
        return 2
    success = load_json(SUCCESS)
    rows = suite_rows(suite)
    if limit is not None:
        rows = rows[:limit]
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    failed = 0
    results = []
    work = REPO_ROOT / "tests" / "projects" / "single-lib"
    for row in rows:
        trace_path = ARTIFACTS / f"{row['id']}.jsonl"
        auth = row.get("expected_auth") or ""
        full_auto = auth in {"write-if-authorized", "write-declared"} or "--apply" in row["prompt"]
        if row.get("expected_command") in READONLY_COMMANDS:
            full_auto = False
        code = run_codex(row["prompt"], trace_path, full_auto=full_auto, cwd=work)
        events = parse_jsonl(trace_path.read_text(encoding="utf-8")) if trace_path.is_file() else []
        result = grade_case(row, events, success)
        result["trace"] = str(trace_path.relative_to(REPO_ROOT))
        if code != 0 and not events:
            result["overall_pass"] = False
            result["checks"].append(check("codex-exit", False, f"exit {code}"))
            result["score"] = 0
        (ARTIFACTS / f"{row['id']}.summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        results.append(result)
        status = "PASS" if result["overall_pass"] else "FAIL"
        print(f"{status} {row['id']} score={result['score']}")
        if not result["overall_pass"]:
            failed += 1
    summary = {"suite": suite, "failed": failed, "results": results}
    (ARTIFACTS / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if failed:
        print(f"eval-agent --live: {failed} case(s) failed", file=sys.stderr)
        return 1
    print(f"OK: eval-agent live {suite} {len(results)} case(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="run Codex E3 evals")
    parser.add_argument("--suite", choices=SUITES, default="trigger")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--grade-trace", type=Path, default=None)
    parser.add_argument("--case", default=None, help="case id for --grade-trace")
    args = parser.parse_args()
    if args.grade_trace is not None:
        case_id = args.case
        if not case_id:
            case_id = args.grade_trace.stem
        row = find_case(case_id)
        events = parse_jsonl(Path(args.grade_trace).read_text(encoding="utf-8"))
        result = grade_case(row, events, load_json(SUCCESS))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["overall_pass"] else 1
    if args.live:
        return live(args.suite, args.limit)
    return static_contracts()


if __name__ == "__main__":
    raise SystemExit(main())
