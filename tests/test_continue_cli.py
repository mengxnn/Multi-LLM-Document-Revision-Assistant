import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from office_revision.cli import main
from office_revision.continue_flow import FEEDBACK_TEMPLATE


def write_structured_final(session: Path, text: str) -> None:
    final_dir = session / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "final.md").write_text(text, encoding="utf-8")


def write_latest_metadata(project: Path, session: Path, output_root_name: str = "dry_run_outputs") -> None:
    metadata = project / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "latest.json").write_text(
        json.dumps(
            {
                "session_dir": str(session),
                "version_dir": session.name,
                "version": 1,
                "status": "pending",
                "output_root": output_root_name,
            }
        ),
        encoding="utf-8",
    )


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
            write_structured_final(previous, "Previous final draft.")
            write_latest_metadata(project, previous)

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
            self.assertTrue((session / "final" / "final.md").exists())
            self.assertTrue((session / "reviews" / "round_01_review.md").exists())
            self.assertTrue((outputs / "latest" / "final" / "final.md").exists())
            self.assertFalse((session / "final.md").exists())
            self.assertFalse((session / "review.md").exists())
            status = json.loads((session / "metadata" / "session_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "continue")
            self.assertEqual(status["current_version"], "v2")
            run_log = json.loads((session / "metadata" / "run_log.json").read_text(encoding="utf-8"))
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

    def test_continue_project_rejects_empty_feedback_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            inputs = project / "inputs"
            outputs = project / "dry_run_outputs"
            previous = outputs / "153000-pending-v1"
            inputs.mkdir(parents=True)
            previous.mkdir(parents=True)
            (inputs / "requirements.md").write_text("Original requirements.", encoding="utf-8")
            (inputs / "feedback.md").write_text("  \n", encoding="utf-8")
            write_structured_final(previous, "Previous final draft.")
            write_latest_metadata(project, previous)

            with self.assertRaises(SystemExit) as raised:
                main(["--continue-project", str(project), "--cycles", "1"])

            self.assertIn("feedback", str(raised.exception))

    def test_continue_project_rejects_default_feedback_template(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            inputs = project / "inputs"
            outputs = project / "dry_run_outputs"
            previous = outputs / "153000-pending-v1"
            inputs.mkdir(parents=True)
            previous.mkdir(parents=True)
            (inputs / "requirements.md").write_text("Original requirements.", encoding="utf-8")
            (inputs / "feedback.md").write_text(FEEDBACK_TEMPLATE, encoding="utf-8")
            write_structured_final(previous, "Previous final draft.")
            write_latest_metadata(project, previous)

            with self.assertRaises(SystemExit) as raised:
                main(["--continue-project", str(project), "--cycles", "1"])

            self.assertIn("default feedback template", str(raised.exception))

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
            write_structured_final(previous, "Previous final draft.")
            write_latest_metadata(project, previous)

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

    def test_continue_project_can_start_from_specific_version_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            inputs = project / "inputs"
            outputs = project / "dry_run_outputs"
            older = outputs / "153000-pending-v1"
            latest = outputs / "160000-continue-v2"
            inputs.mkdir(parents=True)
            older.mkdir(parents=True)
            latest.mkdir()
            (inputs / "requirements.md").write_text("Original requirements.", encoding="utf-8")
            (inputs / "feedback.md").write_text("Use the older version as the base.", encoding="utf-8")
            write_structured_final(older, "Older final draft.")
            write_structured_final(latest, "Latest final draft.")
            write_latest_metadata(project, latest)

            exit_code = main(
                [
                    "--continue-project",
                    str(older),
                    "--cycles",
                    "1",
                ]
            )

            self.assertEqual(exit_code, 0)
            new_sessions = list(outputs.glob("*-continue-v3"))
            self.assertEqual(len(new_sessions), 1)
            run_log = json.loads((new_sessions[0] / "metadata" / "run_log.json").read_text(encoding="utf-8"))
            self.assertEqual(run_log["previous_output_dir"], str(older))
            self.assertIn("Older final draft.", (new_sessions[0] / "final" / "final.md").read_text(encoding="utf-8"))

    def test_continue_project_prints_review_command_for_new_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            inputs = project / "inputs"
            outputs = project / "dry_run_outputs"
            previous = outputs / "153000-pending-v1"
            inputs.mkdir(parents=True)
            previous.mkdir(parents=True)
            (inputs / "requirements.md").write_text("Original requirements.", encoding="utf-8")
            (inputs / "feedback.md").write_text("Make it clearer.", encoding="utf-8")
            write_structured_final(previous, "Previous final draft.")
            write_latest_metadata(project, previous)

            with patch("builtins.print") as print_mock:
                exit_code = main(["--continue-project", str(project), "--cycles", "1"])

            self.assertEqual(exit_code, 0)
            new_session = next(outputs.glob("*-continue-v2"))
            printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
            self.assertIn("使用下面的命令进行状态标记", printed)
            self.assertIn(f'-ProjectDir "{new_session}"', printed)


if __name__ == "__main__":
    unittest.main()
