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
from office_revision.application.continued_revisions import ContinuedRevisionService
from office_revision.project_manager import write_latest_metadata
from office_revision.workflow import RevisionPass, RevisionResult


def write_blank_pdf(path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)


class ContinuedRevisionTests(unittest.TestCase):
    def test_continue_context_respects_history_switches_and_supplemental_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            project = root / "Project_20260720"
            inputs = project / "inputs"
            previous = project / "outputs" / "100000-pending-v1"
            (previous / "final_draft").mkdir(parents=True)
            inputs.mkdir(parents=True)
            (inputs / "requirements.md").write_text(
                "Original requirements.",
                encoding="utf-8",
            )
            (inputs / "source.md").write_text("Original source.", encoding="utf-8")
            (inputs / "meeting_notes.md").write_text(
                "Original meeting notes.",
                encoding="utf-8",
            )
            (previous / "final_draft" / "final.md").write_text(
                "Selected version.",
                encoding="utf-8",
            )
            write_latest_metadata(project / "outputs", previous)
            supplement_one = Path(temp_dir) / "new-data.md"
            supplement_two = Path(temp_dir) / "decisions.txt"
            supplement_one.write_text("New data.", encoding="utf-8")
            supplement_two.write_text("New decision.", encoding="utf-8")
            seen = {}

            def feedback_analyzer(**kwargs):
                seen["analysis"] = kwargs
                return "Use the supplied context."

            def real_runner(request, **kwargs):
                seen["workflow"] = request
                return RevisionResult(
                    request=request,
                    passes=[
                        RevisionPass(
                            cycle_index=1,
                            draft="Continued draft.",
                            review="是否继续修改：否\n总体评分：5",
                        )
                    ],
                )

            service = ContinuedRevisionService(
                root,
                real_runner=real_runner,
                feedback_analyzer=feedback_analyzer,
            )

            result = service.continue_existing_revision(
                ContinueRevisionRequest(
                    project_id=project.name,
                    feedback_text="Apply this feedback.",
                    retain_original_requirements=False,
                    retain_original_source=True,
                    retain_original_meeting_notes=True,
                    supplemental_paths=(supplement_one, supplement_two),
                    cycles=1,
                )
            )

            workflow = seen["workflow"]
            self.assertIn("Selected version.", workflow.source_text)
            self.assertIn("Original source.", workflow.source_text)
            self.assertIn("new-data.md", workflow.source_text)
            self.assertIn("New data.", workflow.source_text)
            self.assertIn("decisions.txt", workflow.source_text)
            self.assertNotIn("Original requirements.", workflow.requirements)
            self.assertIn("Apply this feedback.", workflow.requirements)
            self.assertEqual(workflow.meeting_notes, "Original meeting notes.")
            self.assertEqual(seen["analysis"]["original_requirements"], "")

            context_log = json.loads(
                (result.version_path / "metadata" / "run_log.json").read_text(
                    encoding="utf-8"
                )
            )["context_selection"]
            self.assertFalse(context_log["retain_original_requirements"])
            self.assertTrue(context_log["retain_original_source"])
            self.assertTrue(context_log["retain_original_meeting_notes"])
            self.assertEqual(
                context_log["supplemental_files"],
                ["new-data.md", "decisions.txt"],
            )
            self.assertTrue(
                (result.version_path / "inputs" / "supplemental_01_new-data.md").exists()
            )
            self.assertTrue(
                (result.version_path / "inputs" / "supplemental_02_decisions.txt").exists()
            )

    def test_continue_supplemental_image_pdf_uses_ocr_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            project = root / "Project_20260720"
            inputs = project / "inputs"
            previous = project / "outputs" / "100000-pending-v1"
            (previous / "final_draft").mkdir(parents=True)
            inputs.mkdir(parents=True)
            (inputs / "requirements.md").write_text(
                "Original requirements.",
                encoding="utf-8",
            )
            (previous / "final_draft" / "final.md").write_text(
                "Selected version.",
                encoding="utf-8",
            )
            write_latest_metadata(project / "outputs", previous)
            scanned = Path(temp_dir) / "扫描补充.pdf"
            write_blank_pdf(scanned)
            calls = []
            seen = {}

            def real_runner(request, **kwargs):
                seen["workflow"] = request
                return RevisionResult(
                    request=request,
                    passes=[
                        RevisionPass(
                            cycle_index=1,
                            draft="Continued draft.",
                            review="是否继续修改：否\n总体评分：5",
                        )
                    ],
                )

            service = ContinuedRevisionService(
                root,
                real_runner=real_runner,
                feedback_analyzer=lambda **kwargs: "Use OCR content.",
                ocr_reader=lambda path, language: calls.append((Path(path), language))
                or "OCR supplemental content.",
            )

            result = service.continue_existing_revision(
                ContinueRevisionRequest(
                    project_id=project.name,
                    feedback_text="Apply the scanned supplement.",
                    supplemental_paths=(scanned,),
                    enable_ocr=True,
                    cycles=1,
                )
            )

            self.assertEqual(calls, [(scanned, "chi_sim+eng")])
            self.assertIn("OCR supplemental content.", seen["workflow"].source_text)
            self.assertTrue(
                (
                    result.version_path
                    / "inputs"
                    / "supplemental_01_扫描补充_ocr.md"
                ).exists()
            )

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
