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


def write_text_pdf(path: Path, text: str) -> None:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(output)


def write_blank_pdf(path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)


class NewProjectTests(unittest.TestCase):
    def test_uploaded_pdf_requirements_keeps_original_and_extracted_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirements = root / "requirements.pdf"
            write_text_pdf(requirements, "PDF requirements body")

            result = RevisionApplication(projects_root=root / "projects").start_new_project(
                StartProjectRequest(
                    requirements_path=str(requirements),
                    cycles=1,
                    dry_run=True,
                )
            )

            self.assertTrue((result.project_path / "inputs" / "requirements.pdf").exists())
            self.assertIn(
                "PDF requirements body",
                (result.project_path / "inputs" / "requirements.md").read_text(encoding="utf-8"),
            )

    def test_image_only_pdf_fails_before_project_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "scanned.pdf"
            write_blank_pdf(source)

            with self.assertRaisesRegex(RevisionApplicationError, "image-only"):
                RevisionApplication(projects_root=root / "projects").start_new_project(
                    StartProjectRequest(
                        requirements_text="Improve it.",
                        source_path=str(source),
                        cycles=1,
                        dry_run=True,
                    )
                )

            self.assertFalse((root / "projects").exists())

    def test_image_only_pdf_uses_ocr_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "scanned.pdf"
            write_blank_pdf(source)
            calls = []
            service = NewProjectService(
                root / "projects",
                ocr_reader=lambda path, language: calls.append((Path(path), language))
                or "OCR draft body",
            )

            result = RevisionApplication(
                projects_root=root / "projects",
                new_project_service=service,
            ).start_new_project(
                StartProjectRequest(
                    requirements_text="Improve it.",
                    source_path=str(source),
                    cycles=1,
                    dry_run=True,
                    enable_ocr=True,
                )
            )

            self.assertEqual(calls, [(source, "chi_sim+eng")])
            self.assertIn(
                "OCR draft body",
                (result.project_path / "inputs" / "source_ocr.md").read_text(encoding="utf-8"),
            )
            self.assertTrue((result.project_path / "inputs" / "source.pdf").exists())

    def test_uploaded_pdf_source_keeps_original_and_extracted_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "draft.pdf"
            write_text_pdf(source, "PDF draft body")

            result = RevisionApplication(projects_root=root / "projects").start_new_project(
                StartProjectRequest(
                    requirements_text="Improve it.",
                    source_path=str(source),
                    cycles=1,
                    dry_run=True,
                )
            )

            self.assertTrue((result.project_path / "inputs" / "source.pdf").exists())
            extracted = result.project_path / "inputs" / "source_extracted.md"
            self.assertTrue(extracted.exists())
            self.assertIn("PDF draft body", extracted.read_text(encoding="utf-8"))

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

    def test_start_project_writes_input_summaries_for_saved_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            long_source = "source " * 5000

            result = RevisionApplication(projects_root=root / "projects").start_new_project(
                StartProjectRequest(
                    requirements_text="Improve it.",
                    source_text=long_source,
                    cycles=1,
                    dry_run=True,
                )
            )

            summaries = json.loads(
                (result.project_path / "metadata" / "input_summaries.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summaries["requirements.md"]["kind"], "md")
            self.assertGreater(summaries["source.md"]["extracted_chars"], 20000)
            self.assertIn("long", summaries["source.md"]["warnings"])

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
