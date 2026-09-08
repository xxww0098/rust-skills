"""CLI regressions for Patch scope and verification evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class PatchToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src/lib.rs").write_text("pub fn ping() -> u8 { 1 }\n", encoding="utf-8")
        (self.root / "Cargo.toml").write_text(
            '[package]\nname = "patch-probe"\nversion = "0.1.0"\nedition = "2021"\n',
            encoding="utf-8",
        )
        self.patch = {
            "intent": "keep ping total",
            "finding_id": "greenfield",
            "owner_layer": "lib",
            "files": ["src/lib.rs"],
            "invariant": "ping returns one",
            "shape": "total function",
            "refused": "unwrap",
            "verification": "cargo test --manifest-path Cargo.toml",
        }

    def run_tool(self, name, *args, env=None):
        patch_path = self.root / "patch.json"
        patch_path.write_text(json.dumps(self.patch), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / name), "--patch", str(patch_path),
             "--root", str(self.root), "--json", *args],
            capture_output=True, text=True, check=False, env=env,
        )
        return proc, json.loads(proc.stdout)

    def test_patch_directories_are_refused_by_both_entrypoints(self):
        self.patch["files"] = ["src"]
        for tool in ("check_patch.py", "verify_patch.py"):
            with self.subTest(tool=tool):
                proc, report = self.run_tool(tool)
                self.assertEqual(proc.returncode, 1, report)
                self.assertFalse(report["ok"])
                self.assertIn("not a file", "\n".join(report["patch_errors"]))
                self.assertEqual(report["scanned"], [])

    def test_patch_values_are_not_coerced_to_strings(self):
        valid = self.patch.copy()
        for field, value in (("intent", None), ("shape", {}), ("verification", []),
                             ("files", [None])):
            with self.subTest(field=field):
                self.patch = {**valid, field: value}
                for tool in ("check_patch.py", "verify_patch.py"):
                    proc, report = self.run_tool(tool)
                    self.assertEqual(proc.returncode, 1, report)
                    self.assertIn("string", "\n".join(report["patch_errors"]))

    def test_non_verifying_cargo_modes_are_refused(self):
        for command in (
            "cargo test --manifest-path Cargo.toml --help",
            "cargo check --manifest-path Cargo.toml -h",
            "cargo nextest list --manifest-path Cargo.toml",
            "cargo nextest run --manifest-path Cargo.toml --version",
            "cargo test --manifest-path Cargo.toml -- --list",
            "cargo test -- --manifest-path Cargo.toml",
        ):
            with self.subTest(command=command):
                self.patch["verification"] = command
                proc, report = self.run_tool("verify_patch.py")
                self.assertEqual(proc.returncode, 1, report)
                self.assertEqual(report["verification_status"], "invalid")
                self.assertFalse(report["proven"])

    def test_equals_manifest_option_is_runnable_but_not_proven(self):
        self.patch["verification"] = "cargo +stable test --manifest-path=Cargo.toml -- --exact ping"
        proc, report = self.run_tool("verify_patch.py")
        self.assertEqual(proc.returncode, 0, report)
        self.assertEqual(report["verification_status"], "runnable")
        self.assertEqual(report["manifest"], str((self.root / "Cargo.toml").resolve()))
        self.assertFalse(report["proven"])

    def test_equivalent_patch_paths_are_scanned_once(self):
        source = (self.root / "src/lib.rs").resolve()
        self.patch["files"] = ["src/lib.rs", "src/../src/lib.rs", str(source)]
        for tool in ("check_patch.py", "verify_patch.py"):
            with self.subTest(tool=tool):
                proc, report = self.run_tool(tool)
                self.assertEqual(proc.returncode, 0, report)
                self.assertEqual(report["scanned"], [str(source)])

    def test_cfg_any_test_does_not_hide_feature_enabled_production(self):
        (self.root / "src/lib.rs").write_text(
            '#[cfg(any(test, feature = "live"))]\n'
            'pub fn live() { Some(1).unwrap(); }\n'
            '#[cfg(test)]\nmod tests { fn noise() { Some(2).unwrap(); } }\n'
            'pub fn text() { let _s = ".unwrap()"; /* Some(3).unwrap() */ }\n',
            encoding="utf-8",
        )
        proc, report = self.run_tool("check_patch.py")
        self.assertEqual(proc.returncode, 1, report)
        self.assertEqual(report["hits"], [
            f"{(self.root / 'src/lib.rs').resolve()}:2: ERR-03 unwrap: "
            "pub fn live() { Some(1).unwrap(); }"
        ])
        snapshot = subprocess.run(
            [sys.executable, str(SCRIPTS / "inspect_project.py"), str(self.root)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
        self.assertEqual(json.loads(snapshot.stdout)["signals"], [
            {"kind": "unwrap", "path": "src/lib.rs:2",
             "provenance": "source-scan", "confidence": "high"}
        ])

    def test_explicit_files_use_root_and_refuse_missing_paths(self):
        for source, expected_code in (("src/lib.rs", 0), ("src/missing.rs", 1)):
            with self.subTest(source=source):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPTS / "check_patch.py"), "--root",
                     str(self.root), "--json", source],
                    capture_output=True, text=True, check=False,
                )
                report = json.loads(proc.stdout)
                self.assertEqual(proc.returncode, expected_code, report)
                if expected_code == 0:
                    self.assertEqual(report["scanned"], [str((self.root / source).resolve())])
                else:
                    self.assertIn("missing file", "\n".join(report["patch_errors"]))

    def cargo_environment(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        cargo = bin_dir / "cargo"
        cargo.write_text(
            f"#!{sys.executable}\n"
            "import os, pathlib, sys\n"
            "pathlib.Path('cargo-called').write_text('executed')\n"
            "sys.exit(int(os.environ.get('CARGO_TEST_EXIT', '0')))\n",
            encoding="utf-8",
        )
        cargo.chmod(0o755)
        return {**os.environ, "PATH": str(bin_dir)}

    def test_shape_refusals_never_execute_cargo_or_become_proven(self):
        env = self.cargo_environment()
        (self.root / "src/lib.rs").write_text(
            "pub fn ping() -> u8 { Some(1).unwrap() }\n", encoding="utf-8",
        )
        proc, report = self.run_tool("verify_patch.py", "--run", env=env)
        self.assertEqual(proc.returncode, 1, report)
        self.assertFalse(report["proven"])
        self.assertEqual(report["verification_status"], "invalid")
        self.assertIn("ERR-03 unwrap", report["hits"][0])
        self.assertFalse((self.root / "cargo-called").exists())

    def test_proof_requires_explicit_successful_cargo_execution(self):
        env = self.cargo_environment()
        proc, dry = self.run_tool("verify_patch.py", env=env)
        self.assertEqual(proc.returncode, 0, dry)
        self.assertEqual(dry["verification_status"], "runnable")
        self.assertFalse(dry["proven"])
        self.assertFalse((self.root / "cargo-called").exists())
        for code, status in ((0, "ran"), (17, "failed")):
            with self.subTest(code=code):
                proc, report = self.run_tool(
                    "verify_patch.py", "--run", env={**env, "CARGO_TEST_EXIT": str(code)},
                )
                self.assertEqual(proc.returncode, 0 if code == 0 else 1, report)
                self.assertEqual(report["verification_status"], status)
                self.assertEqual(report["exit_code"], code)
                self.assertEqual(report["proven"], code == 0)
                self.assertEqual((self.root / "cargo-called").read_text(), "executed")

    def test_provably_test_only_cfg_combinations_remain_excluded(self):
        for predicate in ("test", "any(test)", "any(test, doctest)", "any(doctest, test,)"):
            with self.subTest(predicate=predicate):
                (self.root / "src/lib.rs").write_text(
                    f"#[cfg({predicate})]\nfn helper() {{ Some(1).unwrap(); }}\n"
                    "pub fn ping() -> u8 { 1 }\n", encoding="utf-8",
                )
                for tool in ("check_patch.py", "verify_patch.py"):
                    proc, report = self.run_tool(tool)
                    self.assertEqual(proc.returncode, 0, report)
                    self.assertEqual(report["hits"], [])

    def test_nextest_global_options_can_precede_run(self):
        for command in (
            "cargo nextest --color never run --manifest-path Cargo.toml",
            "cargo nextest -v --color=never -P ci --manifest-path Cargo.toml run",
            "cargo +stable nextest --config-file config.toml --profile=ci run --manifest-path Cargo.toml",
        ):
            with self.subTest(command=command):
                self.patch["verification"] = command
                proc, report = self.run_tool("verify_patch.py")
                self.assertEqual(proc.returncode, 0, report)
                self.assertEqual(report["verification_status"], "runnable")
                self.assertFalse(report["proven"])
        self.patch["verification"] = "cargo nextest --profile run list --manifest-path Cargo.toml"
        proc, report = self.run_tool("verify_patch.py")
        self.assertEqual(proc.returncode, 1, report)
        self.assertEqual(report["verification_status"], "invalid")


if __name__ == "__main__":
    unittest.main()
