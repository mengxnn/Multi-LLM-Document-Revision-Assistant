import json
import tempfile
import unittest
from pathlib import Path

from office_revision.project_manager import (
    ProjectContext,
    fallback_project_title,
    make_project_directory_name,
    sanitize_project_title,
    snapshot_project_inputs,
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


if __name__ == "__main__":
    unittest.main()
