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

    def test_defaults_to_inputs_directory_for_daily_use(self):
        args = main.__globals__["build_parser"]().parse_args([])

        self.assertEqual(args.source, "inputs/source.docx")
        self.assertEqual(args.requirements, "inputs/requirements.md")


if __name__ == "__main__":
    unittest.main()
