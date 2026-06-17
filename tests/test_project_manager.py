import json
import tempfile
import unittest
from pathlib import Path

from office_revision.project_manager import (
    ProjectContext,
    RenameProjectResult,
    create_project_context,
    fallback_project_title,
    finalize_project_title,
    make_project_directory_name,
    sanitize_project_title,
    snapshot_project_inputs,
    write_final_suggested_project_title,
)


class ProjectManagerTests(unittest.TestCase):
    def test_sanitizes_title_for_windows_directory_name(self):
        self.assertEqual(
            sanitize_project_title(' 项目:实施/方案*修订? "A" '),
            "项目实施方案修订_A",
        )

    def test_make_project_directory_name_adds_date(self):
        self.assertEqual(
            make_project_directory_name("项目实施方案修订", "20260611"),
            "项目实施方案修订_20260611",
        )

    def test_fallback_project_title_prefers_source_stem(self):
        self.assertEqual(
            fallback_project_title(Path("inputs/source.docx"), "# 标题\n正文", "修改要求"),
            "source",
        )

    def test_fallback_project_title_prefers_explicit_requirement_title(self):
        self.assertEqual(
            fallback_project_title(
                Path("inputs/source.docx"),
                "",
                "我需要你帮我完成一个调研报告，题目：县域养老服务发展现状调研报告",
            ),
            "县域养老服务发展现状调研报告",
        )
        self.assertEqual(
            fallback_project_title(None, "", "标题为 数字乡村建设路径研究\n请写成调研报告"),
            "数字乡村建设路径研究",
        )

    def test_fallback_project_title_uses_document_type_before_raw_requirement_prefix(self):
        self.assertEqual(
            fallback_project_title(None, "", "我需要你帮我完成一个调研报告，请结合以下材料"),
            "调研报告",
        )

    def test_create_project_context_uses_unique_directory_when_same_title_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = create_project_context(
                projects_root=temp_dir,
                title="Project Plan",
                created_date="20260616",
            )
            second = create_project_context(
                projects_root=temp_dir,
                title="Project Plan",
                created_date="20260616",
            )

            self.assertEqual(first.project_dir.name, "Project_Plan_20260616")
            self.assertEqual(second.project_dir.name, "Project_Plan_20260616_02")
            self.assertTrue(first.project_dir.exists())
            self.assertTrue(second.project_dir.exists())

    def test_snapshot_project_inputs_copies_existing_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.md"
            requirements = root / "requirements.md"
            meeting_notes = root / "meeting_notes.md"
            source.write_text("source", encoding="utf-8")
            requirements.write_text("requirements", encoding="utf-8")
            meeting_notes.write_text("meeting", encoding="utf-8")
            context = ProjectContext(
                project_dir=root / "projects" / "项目_20260611",
                title="项目",
                created_date="20260611",
            )

            snapshot_project_inputs(
                context,
                source_path=source,
                requirements_path=requirements,
                meeting_notes_path=meeting_notes,
            )

            self.assertEqual((context.inputs_dir / "source.md").read_text(encoding="utf-8"), "source")
            self.assertEqual(
                (context.inputs_dir / "requirements.md").read_text(encoding="utf-8"),
                "requirements",
            )
            self.assertEqual(
                json.loads((context.project_dir / "project.json").read_text(encoding="utf-8"))["title"],
                "项目",
            )

    def test_write_final_suggested_project_title_preserves_directory_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = ProjectContext(
                project_dir=Path(temp_dir) / "projects" / "source_20260616",
                title="source",
                created_date="20260616",
            )
            snapshot_project_inputs(
                context,
                source_path=None,
                requirements_path=Path(temp_dir) / "missing_requirements.md",
                meeting_notes_path=None,
            )

            write_final_suggested_project_title(context, "项目实施方案终稿")

            root_metadata = json.loads((context.project_dir / "project.json").read_text(encoding="utf-8"))
            structured_metadata = json.loads(
                (context.project_dir / "metadata" / "project.json").read_text(encoding="utf-8")
            )
            self.assertEqual(root_metadata["title"], "source")
            self.assertEqual(root_metadata["final_suggested_title"], "项目实施方案终稿")
            self.assertEqual(structured_metadata["final_suggested_title"], "项目实施方案终稿")

    def test_finalize_project_title_renames_project_directory_and_updates_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = create_project_context(
                projects_root=temp_dir,
                title="source",
                created_date="20260616",
            )
            snapshot_project_inputs(
                context,
                source_path=None,
                requirements_path=Path(temp_dir) / "missing_requirements.md",
                meeting_notes_path=None,
            )

            new_context, result = finalize_project_title(context, "县域养老服务发展现状调研报告")

            self.assertIsInstance(result, RenameProjectResult)
            self.assertEqual(result.status, "renamed")
            self.assertEqual(new_context.project_dir.name, "县域养老服务发展现状调研报告_20260616")
            self.assertFalse(context.project_dir.exists())
            metadata = json.loads((new_context.project_dir / "metadata" / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["title"], "县域养老服务发展现状调研报告")
            self.assertEqual(metadata["original_title"], "source")
            self.assertEqual(metadata["final_suggested_title"], "县域养老服务发展现状调研报告")
            self.assertEqual(metadata["rename_status"], "renamed")

    def test_finalize_project_title_uses_numbered_directory_when_target_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "调研报告_20260616"
            existing.mkdir()
            context = create_project_context(
                projects_root=temp_dir,
                title="source",
                created_date="20260616",
            )

            new_context, result = finalize_project_title(context, "调研报告")

            self.assertEqual(result.status, "renamed")
            self.assertEqual(new_context.project_dir.name, "调研报告_20260616_02")

    def test_finalize_project_title_retries_and_records_failure_when_rename_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = create_project_context(
                projects_root=temp_dir,
                title="source",
                created_date="20260616",
            )
            sleep_calls = []

            def failing_rename(target):
                raise PermissionError("locked")

            new_context, result = finalize_project_title(
                context,
                "调研报告",
                max_attempts=3,
                retry_delay_seconds=7,
                sleep=sleep_calls.append,
                rename=failing_rename,
            )

            self.assertEqual(new_context.project_dir, context.project_dir)
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.reason, "PermissionError: locked")
            self.assertEqual(sleep_calls, [7, 7])
            metadata = json.loads((context.project_dir / "metadata" / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["final_suggested_title"], "调研报告")
            self.assertEqual(metadata["rename_status"], "failed")
            self.assertIn("locked", metadata["rename_reason"])


if __name__ == "__main__":
    unittest.main()
