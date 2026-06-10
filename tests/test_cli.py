import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document

from office_revision.cli import main
from office_revision.connection_test import ConnectionCheckResult


class CliTests(unittest.TestCase):
    def test_dry_run_writes_expected_output_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.md"
            requirements = root / "requirements.md"
            output = root / "output"
            source.write_text("原始项目方案。", encoding="utf-8")
            requirements.write_text("补充目标和进度安排。", encoding="utf-8")

            exit_code = main(
                [
                    "--source",
                    str(source),
                    "--requirements",
                    str(requirements),
                    "--output-dir",
                    str(output),
                    "--cycles",
                    "2",
                    "--dry-run",
                ]
            )

            self.assertEqual(exit_code, 0)
            final_text = (output / "final.md").read_text(encoding="utf-8")
            review_text = (output / "review.md").read_text(encoding="utf-8")
            run_log = json.loads((output / "run_log.json").read_text(encoding="utf-8"))

            self.assertIn("第 2 轮修改稿", final_text)
            self.assertIn("一、总体结论", review_text)
            self.assertIn("是否继续修改：是", review_text)
            self.assertEqual(run_log["cycles"], 2)
            self.assertEqual(run_log["actual_cycles"], 2)
            self.assertFalse(run_log["stopped_early"])
            self.assertEqual(len(run_log["passes"]), 2)
            self.assertIn("writer_instructions", run_log["passes"][0])

    def test_dry_run_with_docx_source_writes_final_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.docx"
            requirements = root / "requirements.md"
            output = root / "output"
            document = Document()
            document.add_heading("项目实施方案", level=1)
            document.add_paragraph("原始项目方案。")
            document.save(source)
            requirements.write_text("补充目标和进度安排。", encoding="utf-8")

            exit_code = main(
                [
                    "--source",
                    str(source),
                    "--requirements",
                    str(requirements),
                    "--output-dir",
                    str(output),
                    "--cycles",
                    "1",
                    "--dry-run",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "final.md").exists())
            self.assertTrue((output / "final.docx").exists())
            final_doc = Document(output / "final.docx")
            self.assertIn("第 1 轮修改稿", [paragraph.text for paragraph in final_doc.paragraphs])

    def test_check_connections_does_not_require_source_or_requirements(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "settings.env"
            config.write_text(
                "\n".join(
                    [
                        "WRITER_API_KEY=writer-key",
                        "WRITER_MODEL=writer-model",
                        "REVIEWER_API_KEY=reviewer-key",
                        "REVIEWER_MODEL=reviewer-model",
                    ]
                ),
                encoding="utf-8",
            )

            with patch(
                "office_revision.connection_test.check_all_connections",
                return_value=[
                    ConnectionCheckResult("WRITER", "writer-model", True, "ok"),
                    ConnectionCheckResult("REVIEWER", "reviewer-model", True, "ok"),
                ],
            ):
                exit_code = main(["--config", str(config), "--check-connections"])

            self.assertEqual(exit_code, 0)


    def test_uses_separate_default_output_directories_for_dry_run_and_real_runs(self):
        dry_run_args = main.__globals__["build_parser"]().parse_args(["--dry-run"])
        real_args = main.__globals__["build_parser"]().parse_args([])

        self.assertEqual(main.__globals__["default_output_dir"](dry_run_args), Path("outputs/demo/latest"))
        self.assertEqual(main.__globals__["default_output_dir"](real_args), Path("outputs/autogen/latest"))

    def test_default_run_output_dirs_include_timestamp_and_latest(self):
        dry_run_args = main.__globals__["build_parser"]().parse_args(["--dry-run"])
        real_args = main.__globals__["build_parser"]().parse_args([])
        explicit_args = main.__globals__["build_parser"]().parse_args(["--output-dir", "custom/out"])

        self.assertEqual(
            main.__globals__["default_run_output_dirs"](dry_run_args, "20260610_093000"),
            [Path("outputs/demo/20260610_093000"), Path("outputs/demo/latest")],
        )
        self.assertEqual(
            main.__globals__["default_run_output_dirs"](real_args, "20260610_093000"),
            [Path("outputs/autogen/20260610_093000"), Path("outputs/autogen/latest")],
        )
        self.assertEqual(
            main.__globals__["default_run_output_dirs"](explicit_args, "20260610_093000"),
            [Path("custom/out")],
        )

    def test_locked_latest_directory_is_skipped_without_failure(self):
        latest = Path("outputs/autogen/latest")
        timestamped = Path("outputs/autogen/20260610_093000")

        with patch("office_revision.cli.shutil.rmtree", side_effect=PermissionError("locked")):
            self.assertFalse(main.__globals__["prepare_output_dir"](latest))
            self.assertTrue(main.__globals__["prepare_output_dir"](timestamped))

    def test_defaults_to_inputs_directory_for_daily_use(self):
        args = main.__globals__["build_parser"]().parse_args([])

        self.assertIsNone(args.source)
        self.assertIsNone(args.requirements)

    def test_docx_source_writes_round_drafts_and_reviews(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.docx"
            requirements = root / "requirements.md"
            output = root / "output"
            document = Document()
            document.add_heading("Project Plan", level=1)
            document.add_paragraph("Original draft.")
            document.save(source)
            requirements.write_text("Improve the plan.", encoding="utf-8")

            exit_code = main(
                [
                    "--source",
                    str(source),
                    "--requirements",
                    str(requirements),
                    "--output-dir",
                    str(output),
                    "--cycles",
                    "2",
                    "--dry-run",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "drafts" / "round_01_draft.md").exists())
            self.assertTrue((output / "drafts" / "round_01_draft.docx").exists())
            self.assertTrue((output / "drafts" / "round_02_draft.md").exists())
            self.assertTrue((output / "drafts" / "round_02_draft.docx").exists())
            self.assertTrue((output / "reviews" / "round_01_review.md").exists())
            self.assertTrue((output / "reviews" / "round_01_review.docx").exists())
            self.assertTrue((output / "reviews" / "round_02_review.md").exists())
            self.assertTrue((output / "reviews" / "round_02_review.docx").exists())
            draft_doc = Document(output / "drafts" / "round_01_draft.docx")
            review_doc = Document(output / "reviews" / "round_01_review.docx")
            self.assertTrue(any(paragraph.text for paragraph in draft_doc.paragraphs))
            self.assertTrue(any(paragraph.text for paragraph in review_doc.paragraphs))


    def test_runs_without_source_when_requirements_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs = root / "inputs"
            requirements = root / "requirements.md"
            output = root / "output"
            inputs.mkdir()
            requirements.write_text("Write a plan from scratch.", encoding="utf-8")

            with patch("office_revision.cli.DEFAULT_INPUT_DIR", inputs):
                exit_code = main(
                    [
                        "--requirements",
                        str(requirements),
                        "--output-dir",
                        str(output),
                        "--cycles",
                        "1",
                        "--dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "final.md").exists())
            self.assertTrue((output / "final.docx").exists())
            run_log = json.loads((output / "run_log.json").read_text(encoding="utf-8"))
            self.assertFalse(run_log["has_source"])
            self.assertIsNone(run_log["source_path"])

    def test_empty_source_and_empty_meeting_notes_are_treated_as_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.md"
            requirements = root / "requirements.md"
            meeting_notes = root / "meeting_notes.md"
            output = root / "output"
            source.write_text("   \n", encoding="utf-8")
            requirements.write_text("Write a plan.", encoding="utf-8")
            meeting_notes.write_text("   \n", encoding="utf-8")

            exit_code = main(
                [
                    "--source",
                    str(source),
                    "--requirements",
                    str(requirements),
                    "--meeting-notes",
                    str(meeting_notes),
                    "--output-dir",
                    str(output),
                    "--cycles",
                    "1",
                    "--dry-run",
                ]
            )

            self.assertEqual(exit_code, 0)
            run_log = json.loads((output / "run_log.json").read_text(encoding="utf-8"))
            self.assertEqual(run_log["source_path"], str(source))
            self.assertEqual(run_log["meeting_notes_path"], str(meeting_notes))
            self.assertFalse(run_log["has_source"])
            self.assertFalse(run_log["has_meeting_notes"])

    def test_discovers_md_source_when_default_docx_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs = root / "inputs"
            output = root / "output"
            inputs.mkdir()
            (inputs / "source.md").write_text("Markdown source text.", encoding="utf-8")
            (inputs / "requirements.md").write_text("Improve it.", encoding="utf-8")

            with patch("office_revision.cli.DEFAULT_INPUT_DIR", inputs):
                exit_code = main(["--output-dir", str(output), "--cycles", "1", "--dry-run"])

            self.assertEqual(exit_code, 0)
            run_log = json.loads((output / "run_log.json").read_text(encoding="utf-8"))
            self.assertTrue(run_log["has_source"])
            self.assertEqual(run_log["source_path"], str(inputs / "source.md"))

    def test_missing_or_empty_requirements_stops_with_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            empty_requirements = root / "requirements.md"
            empty_requirements.write_text(" \n", encoding="utf-8")

            with self.assertRaises(SystemExit) as raised:
                main(
                    [
                        "--requirements",
                        str(empty_requirements),
                        "--output-dir",
                        str(root / "output"),
                        "--dry-run",
                    ]
                )

            self.assertIn("requirements", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
