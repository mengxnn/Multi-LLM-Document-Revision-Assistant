import json
import tempfile
import unittest
from pathlib import Path

from office_revision.cli import main


class DecisionCliTests(unittest.TestCase):
    def test_review_project_accept_updates_latest_pending_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "dry_run_outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--review-project",
                    str(project),
                    "--decision",
                    "accept",
                    "--dry-run",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_root / "193728-accept-v1").exists())
            self.assertFalse(session.exists())

    def test_review_project_skip_keeps_pending_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--review-project",
                    str(project),
                    "--decision",
                    "skip",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(session.exists())

    def test_review_project_auto_detects_dry_run_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "dry_run_outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--review-project",
                    str(project),
                    "--decision",
                    "accept",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_root / "193728-accept-v1").exists())

    def test_review_project_continue_is_valid_decision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--review-project",
                    str(project),
                    "--decision",
                    "continue",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_root / "193728-continue-v1").exists())


if __name__ == "__main__":
    unittest.main()
