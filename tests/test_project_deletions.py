import json
import tempfile
import unittest
from pathlib import Path

from office_revision.application import RevisionApplication, RevisionApplicationError


class ProjectDeletionTests(unittest.TestCase):
    def test_soft_deletes_project_to_trash_and_hides_it_from_project_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            project = self._create_project(root, "Project_A_20260626")
            app = RevisionApplication(projects_root=root)

            result = app.delete_project(project.name)

            self.assertEqual(result.project_id, "Project_A_20260626")
            self.assertFalse(project.exists())
            self.assertTrue(result.trash_path.exists())
            self.assertEqual(result.trash_path.parent, root / ".trash")
            self.assertFalse(result.permanent)
            self.assertEqual(app.list_projects(), ())
            metadata = json.loads(
                (result.trash_path / "metadata" / "project.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["project_id"], "Project_A_20260626")

    def test_soft_delete_uses_unique_trash_path_when_name_already_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            project = self._create_project(root, "Project_A_20260626")
            trash = root / ".trash"
            existing = trash / "Project_A_20260626_deleted_20260626_120000"
            existing.mkdir(parents=True)
            app = RevisionApplication(
                projects_root=root,
                deletion_service=None,
            )

            result = app.delete_project(project.name, deleted_at="20260626_120000")

            self.assertTrue(existing.exists())
            self.assertTrue(result.trash_path.exists())
            self.assertEqual(result.trash_path.name, "Project_A_20260626_deleted_20260626_120000_02")

    def test_permanently_deletes_project_without_creating_trash_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            project = self._create_project(root, "Project_A_20260626")
            app = RevisionApplication(projects_root=root)

            result = app.delete_project(project.name, permanent=True)

            self.assertEqual(result.project_id, "Project_A_20260626")
            self.assertFalse(project.exists())
            self.assertIsNone(result.trash_path)
            self.assertTrue(result.permanent)
            self.assertFalse((root / ".trash").exists())

    def test_rejects_deleting_projects_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            root.mkdir()
            app = RevisionApplication(projects_root=root)

            with self.assertRaises(RevisionApplicationError):
                app.delete_project(root)

            self.assertTrue(root.exists())

    @staticmethod
    def _create_project(root: Path, name: str) -> Path:
        project = root / name
        (project / "metadata").mkdir(parents=True)
        (project / "inputs").mkdir()
        (project / "outputs").mkdir()
        (project / "dry_run_outputs").mkdir()
        (project / "metadata" / "project.json").write_text(
            json.dumps(
                {"project_id": name, "title": "Project A", "created_date": "20260626"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return project


if __name__ == "__main__":
    unittest.main()
