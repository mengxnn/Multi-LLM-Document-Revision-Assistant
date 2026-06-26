import json
import tempfile
import unittest
from pathlib import Path

from office_revision.application import (
    ArtifactLinks,
    ContinueRevisionRequest,
    ProgressEvent,
    RevisionApplication,
    RevisionApplicationError,
    RevisionRunResult,
    StartProjectRequest,
)
from office_revision.application.model_connections import ModelConnectionService
from office_revision.connection_test import ConnectionCheckResult
from office_revision.project_paths import VersionLayout, write_manifest


class ApplicationServiceTests(unittest.TestCase):
    def test_exports_new_project_contracts(self):
        request = StartProjectRequest(requirements_text="Write a plan.")
        event = ProgressEvent(stage="reading_inputs", message="Reading inputs")
        timed_event = ProgressEvent(
            stage="writer_completed",
            message="writer round completed",
            cycle=1,
            total_cycles=2,
            elapsed_seconds=12.34,
        )
        result = RevisionRunResult(
            project_id="Project_20260618",
            project_path=Path("projects/Project_20260618"),
            version=1,
            version_path=Path("projects/Project_20260618/outputs/120000-pending-v1"),
            latest_path=Path("projects/Project_20260618/outputs/latest"),
            status="pending",
            mode="real",
            requested_cycles=2,
            actual_cycles=1,
            stopped_early=True,
            stop_reason="reviewer_requested_stop",
            artifacts=ArtifactLinks(),
        )

        self.assertEqual(request.summary_mode, "rule")
        self.assertEqual(event.stage, "reading_inputs")
        self.assertEqual(event.display_message(), "Reading inputs")
        self.assertEqual(timed_event.display_message(), "writer round completed（1/2，用时 12.3 秒）")
        self.assertEqual(result.version, 1)
        self.assertTrue(issubclass(RevisionApplicationError, Exception))

    def test_continue_revision_contract_and_facade_method(self):
        request = ContinueRevisionRequest(project_id="Project_20260626", feedback_text="Revise it.")
        result = RevisionRunResult(
            project_id="Project_20260626",
            project_path=Path("projects/Project_20260626"),
            version=2,
            version_path=Path("projects/Project_20260626/outputs/120000-continue-v2"),
            latest_path=Path("projects/Project_20260626/outputs/latest"),
            status="continue",
            mode="real",
            requested_cycles=2,
            actual_cycles=2,
            stopped_early=False,
            stop_reason=None,
            artifacts=ArtifactLinks(),
        )

        class ContinueService:
            def __init__(self):
                self.calls = []

            def continue_existing_revision(self, request_arg, *, on_progress=None):
                self.calls.append((request_arg, on_progress))
                return result

        service = ContinueService()
        app = RevisionApplication(continued_revision_service=service)

        returned = app.continue_existing_revision(request, on_progress=lambda event: None)

        self.assertIs(returned, result)
        self.assertEqual(service.calls[0][0], request)
        self.assertEqual(request.summary_mode, "rule")

    def test_lists_projects_and_returns_structured_version_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            project = self._create_project(root, "Project_A_20260618", "Project A")
            version = project / "outputs" / "120000-pending-v1"
            layout = VersionLayout(version)
            layout.ensure_dirs()
            layout.final_md.write_text("final", encoding="utf-8")
            write_manifest(
                layout,
                {
                    "project_name": project.name,
                    "version": 1,
                    "status": "pending",
                    "version_dir": version.name,
                    "created_at": "2026-06-18 12:00:00",
                    "mode": "real",
                    "files": {"final_md": "final_draft/final.md"},
                },
            )
            self._write_latest(project, version)

            app = RevisionApplication(projects_root=root)
            projects = app.list_projects()
            detail = app.get_project_details(projects[0].project_id)

            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0].title, "Project A")
            self.assertEqual(projects[0].latest_status, "pending")
            self.assertEqual(len(detail.versions), 1)
            self.assertTrue(detail.versions[0].is_latest)
            self.assertEqual(detail.versions[0].artifacts.final_md, layout.final_md)

    def test_apply_decision_updates_latest_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects"
            project = self._create_project(root, "Project_A_20260618", "Project A")
            output_root = project / "outputs"
            version = output_root / "120000-pending-v1"
            layout = VersionLayout(version)
            layout.ensure_dirs()
            write_manifest(
                layout,
                {
                    "project_name": project.name,
                    "version": 1,
                    "status": "pending",
                    "version_dir": version.name,
                    "created_at": "2026-06-18 12:00:00",
                    "mode": "real",
                    "files": {},
                },
            )
            (output_root / "latest").mkdir(parents=True)
            self._write_latest(project, version)

            app = RevisionApplication(projects_root=root)
            outcome = app.apply_revision_decision(project.name, "accept")

            self.assertEqual(outcome.status, "accept")
            self.assertEqual(outcome.version_path.name, "120000-accept-v1")
            detail = app.get_project_details(project.name)
            self.assertEqual(detail.summary.latest_status, "accept")

    def test_connection_service_returns_gui_friendly_statuses(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "settings.env"
            config.write_text(
                "WRITER_API_KEY=x\nWRITER_MODEL=w\nREVIEWER_API_KEY=y\nREVIEWER_MODEL=r\n",
                encoding="utf-8",
            )

            def checker(settings):
                return [
                    ConnectionCheckResult(item.role, item.model, True, "ok", 0.25)
                    for item in settings
                ]

            service = ModelConnectionService(config, checker=checker)
            results = service.check_model_connections()

            self.assertEqual([item.role for item in results], ["WRITER", "REVIEWER"])
            self.assertTrue(all(item.ok for item in results))
            self.assertEqual(results[0].elapsed_seconds, 0.25)

    @staticmethod
    def _create_project(root: Path, name: str, title: str) -> Path:
        project = root / name
        (project / "metadata").mkdir(parents=True)
        (project / "inputs").mkdir()
        (project / "outputs").mkdir()
        (project / "dry_run_outputs").mkdir()
        (project / "inputs" / "requirements.md").write_text("requirements", encoding="utf-8")
        (project / "metadata" / "project.json").write_text(
            json.dumps(
                {"project_id": name, "title": title, "created_date": "20260618"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return project

    @staticmethod
    def _write_latest(project: Path, version: Path) -> None:
        (project / "metadata" / "latest.json").write_text(
            json.dumps(
                {
                    "version_dir": version.name,
                    "version": 1,
                    "status": "pending",
                    "output_root": version.parent.name,
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
