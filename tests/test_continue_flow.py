import json
import tempfile
import unittest
from pathlib import Path

from office_revision.continue_flow import (
    build_continue_requirements,
    find_latest_output_dir,
    find_project_requirements_path,
    next_version_dir,
)


class ContinueFlowTests(unittest.TestCase):
    def test_finds_latest_output_dir_from_latest_session_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "outputs"
            session = output_root / "153000-pending"
            latest = output_root / "latest"
            session.mkdir(parents=True)
            latest.mkdir()
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            self.assertEqual(find_latest_output_dir(output_root), session)

    def test_next_version_dir_uses_next_available_version_number(self):
        session = Path("outputs/160000-continue")

        self.assertEqual(next_version_dir(session), session / "v1")

        with tempfile.TemporaryDirectory() as temp_dir:
            session = Path(temp_dir) / "160000-continue"
            (session / "v1").mkdir(parents=True)
            (session / "v2").mkdir()

            self.assertEqual(next_version_dir(session), session / "v3")

    def test_finds_project_requirements_snapshot_with_custom_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            inputs = Path(temp_dir) / "inputs"
            inputs.mkdir()
            (inputs / "custom_requirements.md").write_text("requirements", encoding="utf-8")
            (inputs / "feedback.md").write_text("feedback", encoding="utf-8")

            self.assertEqual(find_project_requirements_path(inputs), inputs / "custom_requirements.md")

    def test_build_continue_requirements_combines_original_feedback_and_analysis(self):
        text = build_continue_requirements(
            original_requirements="Original requirements.",
            feedback="Keep section A, rewrite section B.",
            feedback_analysis="Preserve A and rewrite B as one coherent draft.",
        )

        self.assertIn("Original requirements.", text)
        self.assertIn("Keep section A", text)
        self.assertIn("Preserve A", text)


if __name__ == "__main__":
    unittest.main()
