from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / ".agents" / "skills" / "run-game-player-research" / "scripts"


def run_script(name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=check,
        env=environment,
    )


class RunManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        root = PROJECT_ROOT / "test-artifacts"
        root.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="manifest-", dir=root)
        self.run_dir = Path(self.temporary.name) / "case-one"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_init_route_and_optional_stages(self) -> None:
        run_script(
            "init_run.py",
            str(self.run_dir),
            "--title",
            "测试事件",
            "--analysis-mode",
            "dual",
            "--historical-review",
        )
        manifest = json.loads((self.run_dir / "run-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["analysis_mode"], "dual")
        self.assertEqual(manifest["stages"]["historical_review"]["status"], "pending")
        self.assertEqual(manifest["stages"]["persona_simulation"]["status"], "skipped")

    def test_automated_stage_can_be_recorded_and_resumed(self) -> None:
        run_script("init_run.py", str(self.run_dir), "--title", "测试事件")
        (self.run_dir / "research-brief.md").write_text("# 范围\n", encoding="utf-8")
        run_script(
            "update_manifest.py",
            str(self.run_dir),
            "research_brief",
            "--status",
            "completed",
            "--executor",
            "automation",
            "--executor-detail",
            "imported collection or analysis artifact",
            "--validation",
            "passed",
            "--output",
            "research-brief.md",
        )
        manifest = json.loads((self.run_dir / "run-manifest.json").read_text(encoding="utf-8"))
        stage = manifest["stages"]["research_brief"]
        self.assertEqual(stage["status"], "completed")
        self.assertEqual(stage["executor"], "automation")
        self.assertEqual(len(stage["outputs"][0]["sha256"]), 64)
        self.assertEqual(manifest["current_stage"], "collection")

    def test_core_completion_does_not_wait_for_optional_postprocessing(self) -> None:
        run_script("init_run.py", str(self.run_dir), "--title", "测试事件")
        run_script(
            "update_manifest.py",
            str(self.run_dir),
            "dashboard_result_injection",
            "--status",
            "completed",
            "--executor",
            "codex",
            "--validation",
            "passed",
        )
        manifest = json.loads((self.run_dir / "run-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["run_status"], "completed")
        self.assertIsNone(manifest["current_stage"])

    def test_classification_stage_requires_an_approved_taxonomy(self) -> None:
        run_script("init_run.py", str(self.run_dir), "--title", "测试事件")
        manifest_path = self.run_dir / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for stage in ("research_brief", "collection", "cleaning"):
            manifest["stages"][stage]["status"] = "completed"
        manifest["current_stage"] = "classification_sentiment"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        plan_path = self.run_dir / "classification-plan.json"
        plan_path.write_text(
            json.dumps({"status": "draft"}, ensure_ascii=False), encoding="utf-8"
        )
        (self.run_dir / "semantic-analysis.json").write_text(
            "{}", encoding="utf-8"
        )

        draft = run_script(
            "validate_stage.py",
            str(self.run_dir),
            "classification_sentiment",
            "--phase",
            "after",
            check=False,
        )
        self.assertEqual(draft.returncode, 2)
        self.assertIn("status=approved", draft.stdout)

        plan_path.write_text(
            json.dumps({"status": "approved"}, ensure_ascii=False), encoding="utf-8"
        )
        approved = run_script(
            "validate_stage.py",
            str(self.run_dir),
            "classification_sentiment",
            "--phase",
            "after",
            check=False,
        )
        self.assertEqual(approved.returncode, 0)


if __name__ == "__main__":
    unittest.main()
