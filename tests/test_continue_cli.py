import json
import tempfile
import unittest
from pathlib import Path

from office_revision.cli import main


class ContinueCliTests(unittest.TestCase):
    def test_continue_project_creates_versioned_output_from_latest_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "projects" / "Project_20260611"
            inputs = project / "inputs"
            outputs = project / "dry_run_outputs"
            previous = outputs / "153000-pending-v1"
            inputs.mkdir(parents=True)
            previous.mkdir(parents=True)
            (inputs / "requirements.md").write_text("Original requirements.", encoding="utf-8")
            (inputs / "feedback.md").write_text("Please make the whole draft more concrete.", encoding="utf-8")
            (previous / "final.md").write_text("Previous final draft.", encoding="utf-8")
            (outputs / "latest_session.json").write_text(
                json.dumps({"session_dir": str(previous)}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--continue-project",
                    str(project),
                    "--cycles",
                    "1",
                    "--dry-run",
                ]
            )

            self.assertEqual(exit_code, 0)
            continue_sessions = list(outputs.glob("*-continue-v2"))
            self.assertEqual(len(continue_sessions), 1)
            session = continue_sessions[0]
            self.assertTrue((session / "final.md").exists())
            self.assertTrue((session / "review.md").exists())
            self.assertTrue((outputs / "latest" / "final.md").exists())
            status = json.loads((session / "session_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "continue")
            self.assertEqual(status["current_version"], "v2")
            run_log = json.loads((session / "run_log.json").read_text(encoding="utf-8"))
            self.assertTrue(run_log["is_continue"])
            self.assertEqual(run_log["previous_version"], "v1")
            self.assertEqual(run_log["current_version"], "v2")

    def test_continue_project_requires_feedback_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "Project_20260611"
            (project / "inputs").mkdir(parents=True)
            (project / "dry_run_outputs" / "latest").mkdir(parents=True)

            with self.assertRaises(SystemExit) as raised:
                main(["--continue-project", str(project), "--dry-run"])

            self.assertIn("feedback", str(raised.exception))

    def test_continue_project_auto_detects_dry_run_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            inputs = project / "inputs"
            outputs = project / "dry_run_outputs"
            previous = outputs / "153000-pending-v1"
            inputs.mkdir(parents=True)
            previous.mkdir(parents=True)
            (inputs / "requirements.md").write_text("Original requirements.", encoding="utf-8")
            (inputs / "feedback.md").write_text("Make it clearer.", encoding="utf-8")
            (previous / "final.md").write_text("Previous final draft.", encoding="utf-8")
            (outputs / "latest_session.json").write_text(
                json.dumps({"session_dir": str(previous)}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--continue-project",
                    str(project),
                    "--cycles",
                    "1",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(list(outputs.glob("*-continue-v2")))


if __name__ == "__main__":
    unittest.main()
