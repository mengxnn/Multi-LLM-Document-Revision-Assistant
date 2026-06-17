import json
import tempfile
import unittest
from pathlib import Path

from office_revision.continue_flow import (
    build_continue_requirements,
    find_latest_output_dir,
    find_project_requirements_path,
    next_output_version,
    resolve_continue_target,
    versioned_output_dir,
)


def write_latest_metadata(project_dir: Path, session: Path, output_root_name: str = "outputs") -> None:
    metadata = project_dir / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "latest.json").write_text(
        json.dumps(
            {
                "session_dir": str(session),
                "version_dir": session.name,
                "version": 1,
                "status": "pending",
                "output_root": output_root_name,
            }
        ),
        encoding="utf-8",
    )


class ContinueFlowTests(unittest.TestCase):
    def test_finds_latest_output_dir_from_project_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "Project_20260612"
            output_root = project / "outputs"
            session = output_root / "153000-pending-v1"
            latest = output_root / "latest"
            session.mkdir(parents=True)
            latest.mkdir()
            write_latest_metadata(project, session)

            self.assertEqual(find_latest_output_dir(output_root), session)

    def test_next_output_version_uses_next_available_version_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            (output_root / "153000-pending-v1").mkdir()
            (output_root / "160000-continue-v2").mkdir()
            (output_root / "latest").mkdir()

            self.assertEqual(next_output_version(output_root), 3)

    def test_versioned_output_dir_puts_version_in_directory_name(self):
        self.assertEqual(
            versioned_output_dir(Path("outputs"), "160000", "continue", 2),
            Path("outputs/160000-continue-v2"),
        )

    def test_resolve_continue_target_accepts_project_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "Project_20260612"
            output_root = project / "outputs"
            session = output_root / "153000-pending-v1"
            session.mkdir(parents=True)
            write_latest_metadata(project, session)

            target = resolve_continue_target(project, dry_run=False)

            self.assertEqual(target.project_dir, project)
            self.assertEqual(target.output_root, output_root)
            self.assertEqual(target.previous_output_dir, session)

    def test_resolve_continue_target_accepts_version_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "Project_20260612"
            session = project / "dry_run_outputs" / "153000-pending-v1"
            session.mkdir(parents=True)

            target = resolve_continue_target(session, dry_run=False)

            self.assertEqual(target.project_dir, project)
            self.assertEqual(target.output_root, project / "dry_run_outputs")
            self.assertEqual(target.previous_output_dir, session)

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
