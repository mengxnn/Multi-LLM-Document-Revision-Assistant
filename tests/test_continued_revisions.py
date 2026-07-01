import json
import tempfile
import unittest
from pathlib import Path

from office_revision.application import (
    ContinueRevisionRequest,
    RevisionApplication,
    RevisionApplicationError,
    StartProjectRequest,
)


class ContinuedRevisionTests(unittest.TestCase):
    def test_continues_dry_run_project_from_feedback_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            app = RevisionApplication(projects_root=root)
            first = app.start_new_project(
                StartProjectRequest(
                    requirements_text="Write a project plan.",
                    source_text="Initial draft.",
                    cycles=1,
                    dry_run=True,
                )
            )
            events = []

            result = app.continue_existing_revision(
                ContinueRevisionRequest(
                    project_id=first.project_id,
                    feedback_text="Make the plan more concrete and add timeline details.",
                    cycles=1,
                    dry_run=True,
                ),
                on_progress=events.append,
            )

            self.assertEqual(result.version, 2)
            self.assertEqual(result.status, "continue")
            self.assertEqual(result.mode, "dry-run")
            self.assertEqual(result.version_path.parent.name, "dry_run_outputs")
            self.assertTrue(result.version_path.name.endswith("-continue-v2"))
            self.assertTrue((result.version_path / "final_draft" / "final.md").exists())
            self.assertTrue((result.latest_path / "final_draft" / "final.md").exists())
            self.assertEqual(
                (result.project_path / "inputs" / "feedback.md").read_text(encoding="utf-8"),
                "Make the plan more concrete and add timeline details.",
            )
            run_log = json.loads((result.version_path / "metadata" / "run_log.json").read_text(encoding="utf-8"))
            self.assertTrue(run_log["is_continue"])
            self.assertEqual(run_log["previous_version"], "v1")
            self.assertEqual(run_log["current_version"], "v2")
            self.assertIn("writer_completed", [event.stage for event in events])
            self.assertTrue(any("用时" in event.display_message() for event in events))
            self.assertEqual(events[-1].stage, "completed")

    def test_rejects_conflicting_feedback_before_writing_new_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            app = RevisionApplication(projects_root=root)
            first = app.start_new_project(
                StartProjectRequest(
                    requirements_text="Write a project plan.",
                    cycles=1,
                    dry_run=True,
                )
            )
            feedback_path = Path(temp_dir) / "feedback.md"
            feedback_path.write_text("Use this file.", encoding="utf-8")

            with self.assertRaises(RevisionApplicationError):
                app.continue_existing_revision(
                    ContinueRevisionRequest(
                        project_id=first.project_id,
                        feedback_path=feedback_path,
                        feedback_text="Use this text.",
                        dry_run=True,
                    )
                )

            self.assertFalse(list((first.project_path / "dry_run_outputs").glob("*-continue-v2")))

    def test_continues_from_selected_history_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            app = RevisionApplication(projects_root=root)
            first = app.start_new_project(
                StartProjectRequest(
                    requirements_text="Write a project plan.",
                    source_text="First draft base.",
                    cycles=1,
                    dry_run=True,
                )
            )
            second = app.continue_existing_revision(
                ContinueRevisionRequest(
                    project_id=first.project_id,
                    feedback_text="Create a second version.",
                    cycles=1,
                    dry_run=True,
                )
            )

            result = app.continue_existing_revision(
                ContinueRevisionRequest(
                    project_id=first.project_id,
                    base_version_path=first.version_path,
                    feedback_text="Use the first version as the base.",
                    cycles=1,
                    dry_run=True,
                )
            )

            self.assertEqual(second.version, 2)
            self.assertEqual(result.version, 3)
            run_log = json.loads((result.version_path / "metadata" / "run_log.json").read_text(encoding="utf-8"))
            self.assertEqual(run_log["previous_output_dir"], str(first.version_path))
            self.assertEqual(run_log["previous_version"], "v1")
            final_text = (result.version_path / "final_draft" / "final.md").read_text(encoding="utf-8")
            self.assertIn("First draft base.", final_text)


if __name__ == "__main__":
    unittest.main()
