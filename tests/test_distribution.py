"""Exercise generated install units without access to the source checkout."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class DistributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="rust-distribution-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for name in ("scripts", "skills", "schemas", "commands", ".claude-plugin"):
            shutil.copytree(
                REPO_ROOT / name, self.repo / name, symlinks=True,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        shutil.copy2(REPO_ROOT / "README.md", self.repo / "README.md")

    def cli(self, script: Path, *args: str, stdin: str | None = None, bytecode: bool = False) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PATH="")
        if bytecode:
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            env.pop("PYTHONPYCACHEPREFIX", None)
        # Apple Python redirects caches globally; exercise normal install-local caches.
        python_flags = ["-X", "pycache_prefix="] if bytecode else []
        return subprocess.run(
            [sys.executable, *python_flags, str(script), *args], cwd=self.root, env=env,
            input=stdin, text=True, capture_output=True, check=False,
        )

    def sync(self, *args: str) -> subprocess.CompletedProcess:
        return self.cli(self.repo / "scripts" / "sync-providers.py", *args)

    def assert_success(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_runtime_bytecode_is_not_distribution_drift_or_payload(self) -> None:
        self.assert_success(self.sync())
        canonical = self.repo / "skills" / "rust"
        installed = self.repo / ".dsh" / "skills" / "rust"
        for skill in (canonical, installed):
            self.assert_success(self.cli(skill / "scripts" / "verify_patch.py", "--help", bytecode=True))
            self.assertTrue(list((skill / "scripts" / "__pycache__").glob("*.pyc")))
        self.assert_success(self.sync("--check"))
        evidence = canonical / "kernel" / "evidence.md"
        evidence.write_text(evidence.read_text(encoding="utf-8") + "\n<!-- distribution probe -->\n", encoding="utf-8")
        self.assert_success(self.sync())
        self.assertFalse(list(installed.rglob("*.pyc")))
        self.assert_success(self.sync("--check"))

    def test_installed_kernel_schema_links_stay_within_the_skill(self) -> None:
        self.assert_success(self.sync())
        installed = self.repo / ".dsh" / "skills" / "rust"
        for name in ("write.md", "evidence.md", "finding.md"):
            with self.subTest(name=name):
                document = installed / "kernel" / name
                links = re.findall(r"\]\(([^)]+schema\.json)\)", document.read_text(encoding="utf-8"))
                self.assertTrue(links, f"{name} has no schema link")
                for link in links:
                    target = (document.parent / link).resolve()
                    self.assertTrue(target.is_relative_to(installed), f"{name}: {link} leaves the skill")
                    self.assertTrue(target.is_file(), f"{name}: {link} is missing")

    def test_sync_never_follows_a_harness_parent_symlink(self) -> None:
        self.assert_success(self.sync())
        parent = self.repo / ".dsh" / "skills"
        outside = self.root / "outside"
        parent.rename(outside)
        sentinel = outside / "rust" / "keep.txt"
        sentinel.write_text("not owned by this repository", encoding="utf-8")
        parent.symlink_to(outside, target_is_directory=True)
        result = self.sync()
        self.assertTrue(sentinel.exists(), "sync deleted a file outside the repository")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "not owned by this repository")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        checked = self.cli(self.repo / "scripts" / "check-root-compat.py")
        self.assertNotEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_nested_symlinks_are_drift_and_materialize_without_touching_targets(self) -> None:
        self.assert_success(self.sync())
        skill = self.repo / ".dsh" / "skills" / "rust"
        for rel in ("kernel/evidence.md", "reference"):
            with self.subTest(rel=rel):
                path = skill / rel
                outside = self.root / path.name
                path.rename(outside)
                path.symlink_to(outside, target_is_directory=outside.is_dir())
                before = {p.relative_to(outside): p.read_bytes() for p in outside.rglob("*") if p.is_file()} if outside.is_dir() else outside.read_bytes()
                drift = self.sync("--check")
                self.assertNotEqual(drift.returncode, 0, "sync --check accepted an outbound symlink")
                self.assert_success(self.sync())
                self.assertFalse(path.is_symlink())
                after = {p.relative_to(outside): p.read_bytes() for p in outside.rglob("*") if p.is_file()} if outside.is_dir() else outside.read_bytes()
                self.assertEqual(after, before)
        self.assert_success(self.cli(self.repo / "scripts" / "check-root-compat.py"))

    def test_ignored_cache_symlinks_are_detected_and_repaired(self) -> None:
        self.assert_success(self.sync())
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "keep.txt"
        sentinel.write_text("external cache target", encoding="utf-8")
        scripts = self.repo / ".dsh" / "skills" / "rust" / "scripts"
        for rel, target in (("__pycache__", outside), ("__pycache__/scan.pyc", sentinel)):
            with self.subTest(rel=rel):
                link = scripts / rel
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(target, target_is_directory=target.is_dir())
                try:
                    self.assertNotEqual(self.sync("--check").returncode, 0)
                    self.assert_success(self.sync())
                    self.assertFalse(link.is_symlink())
                    self.assertEqual(sentinel.read_text(encoding="utf-8"), "external cache target")
                    self.assert_success(self.cli(self.repo / "scripts" / "check-root-compat.py"))
                finally:
                    if link.is_symlink():
                        link.unlink()

    def test_standalone_skill_runs_verification_snapshot_and_projection(self) -> None:
        self.assert_success(self.sync())
        self.assert_success(self.cli(self.repo / "scripts" / "check-root-compat.py"))
        installed = self.root / "installed" / "rust"
        shutil.copytree(self.repo / ".dsh" / "skills" / "rust", installed, symlinks=True)
        shutil.rmtree(self.repo)
        project = self.root / "project"
        (project / "src").mkdir(parents=True)
        (project / "Cargo.toml").write_text(
            '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2024"\n', encoding="utf-8",
        )
        source = project / "src" / "lib.rs"
        source.write_text("pub fn answer() -> u32 { 42 }\n", encoding="utf-8")
        patch = project / "patch.json"
        patch.write_text(json.dumps({
            "intent": "Return the answer", "finding_id": "F1", "owner_layer": "domain",
            "files": ["src/lib.rs"], "invariant": "answer is 42", "shape": "a pure function",
            "refused": "no mutable state", "verification": "cargo check --manifest-path Cargo.toml",
        }), encoding="utf-8")
        scripts = installed / "scripts"
        verified = self.cli(scripts / "verify_patch.py", "--patch", str(patch), "--root", str(project), "--json")
        self.assert_success(verified)
        report = json.loads(verified.stdout)
        self.assertEqual(report["verification_status"], "runnable")
        self.assertFalse(report["proven"])
        checked = self.cli(scripts / "check_patch.py", "--patch", str(patch), "--root", str(project), "--json")
        self.assert_success(checked)
        self.assertEqual(json.loads(checked.stdout)["scanned"], [str(source)])
        inspected = self.cli(scripts / "inspect_project.py", str(project))
        self.assert_success(inspected)
        self.assertEqual([c["name"] for c in json.loads(inspected.stdout)["crates"]], ["demo"])
        projected = self.cli(scripts / "render_rust_md.py", "--snapshot", "-", stdin=inspected.stdout)
        self.assert_success(projected)
        self.assertIn("demo=artifact:lib", projected.stdout)
        self.assertIn("edition 2024", projected.stdout)
        self.assertFalse((project / "Cargo.lock").exists())
        self.assertTrue((installed / "schemas" / "project-snapshot.schema.json").is_file())
        self.assertTrue((scripts / "version-floor.json").is_file())
        self.assertFalse((scripts / "sync-providers.py").exists())
        self.assertFalse((installed / "tests").exists())


if __name__ == "__main__":
    unittest.main()
