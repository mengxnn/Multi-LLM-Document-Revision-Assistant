import json
import tempfile
import unittest
from pathlib import Path

from office_revision.application import (
    RevisionApplication,
    RevisionApplicationError,
    StartProjectRequest,
)
from office_revision.application.new_projects import NewProjectService


class NewProjectTests(unittest.TestCase):
    def test_uploaded_markdown_source_keeps_source_type_and_writes_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "draft.md"
            requirements = root / "requirements.txt"
            source.write_text("Draft text.", encoding="utf-8")
            requirements.write_text("Improve it.", encoding="utf-8")

            result = RevisionApplication(projects_root=root / "projects").start_new_project(
                StartProjectRequest(
                    requirements_path=str(requirements),
                    source_path=str(source),
                    cycles=1,
                    dry_run=True,
                )
            )

            manifest = json.loads(
                (result.version_path / "metadata" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["source_type"], "md")
            self.assertTrue((result.version_path / "final_draft" / "final.docx").exists())
            self.assertTrue((result.project_path / "inputs" / "source.md").exists())

    def test_starts_dry_run_project_from_pasted_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            events = []
            app = RevisionApplication(projects_root=root)

            result = app.start_new_project(
                StartProjectRequest(
                    requirements_text="# Test Plan\nWrite a concrete plan.",
                    source_text="Initial draft.",
                    meeting_notes_text="Keep the deadline.",
                    cycles=1,
                    dry_run=True,
                ),
                on_progress=events.append,
            )

            self.assertEqual(result.version, 1)
            self.assertEqual(result.mode, "dry-run")
            self.assertTrue((result.project_path / "inputs" / "requirements.md").exists())
            self.assertTrue((result.project_path / "inputs" / "source.md").exists())
            self.assertTrue((result.project_path / "inputs" / "meeting_notes.md").exists())
            self.assertTrue((result.project_path / "inputs" / "feedback.md").exists())
            self.assertTrue(result.artifacts.final_md.exists())
            self.assertEqual(result.artifacts.final_md.parent.name, "final_draft")
            self.assertTrue((result.latest_path / "final_draft" / "final.md").exists())
            self.assertEqual(events[0].stage, "reading_inputs")
            self.assertIn("writer_running", [event.stage for event in events])
            self.assertIn("writer_completed", [event.stage for event in events])
            self.assertIn("reviewer_running", [event.stage for event in events])
            self.assertIn("reviewer_completed", [event.stage for event in events])
            self.assertTrue(
                any(
                    event.elapsed_seconds is not None and "用时" in event.display_message()
                    for event in events
                )
            )
            self.assertEqual(events[-1].stage, "completed")

    def test_rejects_conflicting_or_empty_requirements_before_project_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            app = RevisionApplication(projects_root=root)

            with self.assertRaises(RevisionApplicationError):
                app.start_new_project(
                    StartProjectRequest(
                        requirements_path=Path("requirements.md"),
                        requirements_text="requirements",
                        dry_run=True,
                    )
                )
            with self.assertRaises(RevisionApplicationError):
                app.start_new_project(StartProjectRequest(requirements_text="  ", dry_run=True))

            self.assertFalse(root.exists())

    def test_failed_real_run_removes_new_project_without_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"

            def failing_runner(*args, **kwargs):
                raise RuntimeError("model timed out")

            app = RevisionApplication(
                projects_root=root,
                new_project_service=NewProjectService(
                    root,
                    real_runner=failing_runner,
                    title_generator=lambda **kwargs: "Should Not Run",
                ),
            )

            with self.assertRaises(RevisionApplicationError):
                app.start_new_project(
                    StartProjectRequest(
                        requirements_text="Write a plan.",
                        cycles=1,
                        dry_run=False,
                    )
                )

            self.assertTrue(root.exists())
            self.assertEqual([path.name for path in root.iterdir()], [])

    def test_starts_without_source_for_requested_cycles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = RevisionApplication(projects_root=Path(temp_dir) / "projects")
            result = app.start_new_project(
                StartProjectRequest(requirements_text="Write from scratch.", cycles=3, dry_run=True)
            )

            self.assertFalse(result.stopped_early)
            self.assertEqual(result.actual_cycles, 3)
            self.assertFalse((result.project_path / "inputs" / "source.md").exists())


if __name__ == "__main__":
    unittest.main()
