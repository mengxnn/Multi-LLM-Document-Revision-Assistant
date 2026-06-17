import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from office_revision.cli import main


def write_latest_metadata(output_root: Path, session: Path) -> None:
    metadata = output_root.parent / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "latest.json").write_text(
        json.dumps(
            {
                "session_dir": str(session),
                "version_dir": session.name,
                "version": 1,
                "status": "pending",
                "output_root": output_root.name,
            }
        ),
        encoding="utf-8",
    )


def write_structured_final(session: Path, text: str) -> None:
    final_dir = session / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "final.md").write_text(text, encoding="utf-8")


class DecisionCliTests(unittest.TestCase):
    def test_review_project_accept_updates_latest_pending_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "dry_run_outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            write_latest_metadata(output_root, session)

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
            write_latest_metadata(output_root, session)

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
            write_latest_metadata(output_root, session)

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
            write_latest_metadata(output_root, session)

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

    def test_review_project_can_mark_specific_version_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "outputs"
            older = output_root / "153902-continue-v2"
            latest = output_root / "160000-pending-v3"
            older.mkdir(parents=True)
            latest.mkdir()
            write_latest_metadata(output_root, latest)

            exit_code = main(
                [
                    "--review-project",
                    str(older),
                    "--decision",
                    "abandon",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_root / "153902-abandon-v2").exists())
            self.assertTrue(latest.exists())

    def test_reviewing_specific_history_version_does_not_change_latest_pointer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "outputs"
            older = output_root / "153902-pending-v2"
            latest = output_root / "160000-pending-v3"
            older.mkdir(parents=True)
            latest.mkdir()
            write_latest_metadata(output_root, latest)

            exit_code = main(
                [
                    "--review-project",
                    str(older),
                    "--decision",
                    "accept",
                ]
            )

            self.assertEqual(exit_code, 0)
            latest_metadata = json.loads((project / "metadata" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(latest_metadata["session_dir"]), latest)

            exit_code = main(
                [
                    "--review-project",
                    str(project),
                    "--decision",
                    "abandon",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_root / "160000-abandon-v3").exists())

    def test_continue_project_directory_uses_latest_after_history_version_was_marked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            inputs = project / "inputs"
            output_root = project / "dry_run_outputs"
            older = output_root / "153902-pending-v2"
            latest = output_root / "160000-pending-v3"
            inputs.mkdir(parents=True)
            older.mkdir(parents=True)
            latest.mkdir()
            (inputs / "requirements.md").write_text("Original requirements.", encoding="utf-8")
            (inputs / "feedback.md").write_text("Continue latest.", encoding="utf-8")
            write_structured_final(older, "Older final draft.")
            write_structured_final(latest, "Latest final draft.")
            write_latest_metadata(output_root, latest)

            self.assertEqual(
                main(["--review-project", str(older), "--decision", "accept"]),
                0,
            )
            self.assertEqual(
                main(["--continue-project", str(project), "--cycles", "1"]),
                0,
            )

            new_session = next(output_root.glob("*-continue-v4"))
            run_log = json.loads((new_session / "metadata" / "run_log.json").read_text(encoding="utf-8"))
            self.assertEqual(run_log["previous_output_dir"], str(latest))
            self.assertIn("Latest final draft.", (new_session / "final" / "final.md").read_text(encoding="utf-8"))

    def test_review_project_skip_specific_version_reminder_uses_version_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "outputs"
            version = output_root / "153902-accept-v2"
            version.mkdir(parents=True)

            with patch("builtins.print") as print_mock:
                exit_code = main(
                    [
                        "--review-project",
                        str(version),
                        "--decision",
                        "skip",
                    ]
                )

            self.assertEqual(exit_code, 0)
            expected = output_root / "153902-pending-v2"
            printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
            self.assertIn(f'--review-project "{expected}"', printed)

    def test_review_project_continue_specific_version_prompt_uses_version_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "projects" / "Project_20260612"
            output_root = project / "outputs"
            version = output_root / "153902-pending-v2"
            version.mkdir(parents=True)

            with patch("builtins.print") as print_mock:
                exit_code = main(
                    [
                        "--review-project",
                        str(version),
                        "--decision",
                        "continue",
                    ]
                )

            self.assertEqual(exit_code, 0)
            expected = output_root / "153902-continue-v2"
            printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
            self.assertIn(f'--continue-project "{expected}"', printed)


if __name__ == "__main__":
    unittest.main()
