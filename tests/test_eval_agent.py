"""Grade the sample Codex JSONL without calling an LLM."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_eval_agent():
    path = REPO_ROOT / "scripts" / "eval-agent.py"
    spec = importlib.util.spec_from_file_location("eval_agent", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class EvalAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_eval_agent()

    def test_sample_review_trace_passes_readonly_grader(self) -> None:
        events = self.mod.parse_jsonl(
            (REPO_ROOT / "evals" / "fixtures" / "sample-review.jsonl").read_text(encoding="utf-8")
        )
        checks = self.mod.grade_events(
            events,
            should_trigger=True,
            expected_command="review",
            expected_auth="readonly",
            caps={"max_command_executions": 25, "max_inspect_project": 2},
        )
        ok, score = self.mod.score_checks(checks)
        self.assertTrue(ok, checks)
        self.assertGreaterEqual(score, 80)
        self.assertFalse(self.mod.wrote_files(events))

    def test_python_skip_prompt_is_in_trigger_csv(self) -> None:
        rows = self.mod.read_csv(REPO_ROOT / "evals" / "prompts" / "trigger.prompts.csv")
        skip = [row for row in rows if row["should_trigger"].lower() == "false"]
        self.assertTrue(any("Python" in row["prompt"] for row in skip))


if __name__ == "__main__":
    unittest.main()
