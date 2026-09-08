"""RUST.md facets must stay scoped to each crate."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


RENDERER = Path(__file__).resolve().parents[1] / "scripts" / "render_rust_md.py"


class ProjectionTests(unittest.TestCase):
    def test_artifact_uses_crate_targets_or_its_own_entrypoints(self):
        cases = (
            ([{"name": "core", "manifest": "crates/core/Cargo.toml", "targets": []},
              {"name": "server", "manifest": "apps/api/Cargo.toml", "targets": []}],
             ["crates/core/src/lib.rs", "apps/api/src/bin/server.rs"],
             "覆盖: core=artifact:lib, server=artifact:cli"),
            ([{"name": "app", "manifest": "Cargo.toml", "targets": []}],
             ["src/main.rs"], "覆盖: app=artifact:cli"),
            ([{"name": "core", "manifest": "Cargo.toml", "targets": ["lib"]}],
             ["src/bin/disabled.rs"], "覆盖: core=artifact:lib"),
        )
        for crates, entries, expected in cases:
            with self.subTest(expected=expected):
                snapshot = {
                    "identity": {"resolver": "2"}, "crates": crates,
                    "graphs": {"entrypoints": entries},
                }
                proc = subprocess.run(
                    [sys.executable, str(RENDERER), "--snapshot", "-"],
                    input=json.dumps(snapshot), capture_output=True, text=True, check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn(expected, proc.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
