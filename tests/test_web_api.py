from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import warnings

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
    category=Warning,
)

from fastapi.testclient import TestClient

from office_revision.application.contracts import (
    ActiveModelProfile,
    ArtifactLinks,
    ContinueRevisionRequest,
    DecisionOutcome,
    DeleteProjectResult,
    ModelConnectionStatus,
    ModelProfile,
    ModelProfileRequest,
    ProgressEvent,
    ProjectDetail,
    ProjectSummary,
    RevisionRunResult,
    StartProjectRequest,
    VersionSummary,
)
from office_revision.web.app import create_app
from office_revision.web.runs import InMemoryRunStore
from office_revision.web.schemas import (
    path_to_string,
    project_summary_to_dict,
    revision_result_to_dict,
)


class WebSchemaTests(TestCase):
    def test_path_to_string_returns_none_for_missing_path(self):
        self.assertIsNone(path_to_string(None))

    def test_path_to_string_normalizes_path_for_json(self):
        self.assertEqual(path_to_string(Path("projects/example")), "projects/example")

    def test_project_summary_to_dict_serializes_path(self):
        summary = ProjectSummary(
            project_id="demo_20260627",
            title="Demo",
            created_date="20260627",
            path=Path("projects/demo_20260627"),
            latest_status="pending",
            latest_version=1,
            latest_mode="dry-run",
        )

        payload = project_summary_to_dict(summary)

        self.assertEqual(payload["project_id"], "demo_20260627")
        self.assertEqual(payload["path"], "projects/demo_20260627")
        self.assertEqual(payload["latest_version"], 1)

    def test_revision_result_to_dict_serializes_artifacts_and_warnings(self):
        result = RevisionRunResult(
            project_id="demo_20260627",
            project_path=Path("projects/demo_20260627"),
            version=1,
            version_path=Path("projects/demo_20260627/outputs/100000-pending-v1"),
            latest_path=Path("projects/demo_20260627/latest"),
            status="pending",
            mode="dry-run",
            requested_cycles=2,
            actual_cycles=1,
            stopped_early=True,
            stop_reason="reviewer approved",
            artifacts=ArtifactLinks(
                final_md=Path("projects/demo_20260627/latest/final_draft/final.md")
            ),
            warnings=("latest locked",),
        )

        payload = revision_result_to_dict(result)

        self.assertEqual(payload["project_id"], "demo_20260627")
        self.assertEqual(
            payload["artifacts"]["final_md"],
            "projects/demo_20260627/latest/final_draft/final.md",
        )
        self.assertEqual(payload["warnings"], ["latest locked"])


class FakeWebApplication:
    def __init__(self):
        self.received_start_request = None
        self.received_continue_request = None
        self.received_model_profile_request = None
        self.decisions = []
        self.deleted = []
        self.activated = []

    def list_projects(self):
        return (
            ProjectSummary(
                project_id="demo_20260627",
                title="Demo",
                created_date="20260627",
                path=Path("projects/demo_20260627"),
                latest_status="pending",
                latest_version=1,
                latest_mode="dry-run",
            ),
        )

    def get_project_details(self, project_id):
        return ProjectDetail(
            summary=self.list_projects()[0],
            versions=(
                VersionSummary(
                    name="100000-pending-v1",
                    version=1,
                    status="pending",
                    mode="dry-run",
                    created_at="2026-06-27T10:00:00",
                    path=Path("projects/demo_20260627/outputs/100000-pending-v1"),
                    is_latest=True,
                    artifacts=ArtifactLinks(
                        final_md=Path("projects/demo_20260627/latest/final_draft/final.md")
                    ),
                ),
            ),
            inputs={"requirements": Path("projects/demo_20260627/inputs/requirements.md")},
        )

    def list_model_profiles(self):
        return (
            ModelProfile(
                profile_id="writer-qwen",
                name="Writer Qwen",
                provider="openai-compatible",
                api_key="secret",
                base_url="https://example.com/v1",
                model="qwen-plus",
            ),
        )

    def get_active_model_profile(self, role):
        if role == "writer":
            profile = self.list_model_profiles()[0]
            return ActiveModelProfile(
                role=role,
                profile_id=profile.profile_id,
                profile=profile,
            )
        return None

    def start_new_project(self, request, on_progress=None):
        self.received_start_request = request
        if on_progress is not None:
            on_progress(
                ProgressEvent(
                    stage="writer_done",
                    message="writer 完成",
                    cycle=1,
                    total_cycles=1,
                    elapsed_seconds=0.2,
                )
            )
        return self._result(version=1)

    def continue_existing_revision(self, request, on_progress=None):
        self.received_continue_request = request
        if on_progress is not None:
            on_progress(
                ProgressEvent(
                    stage="reviewer_done",
                    message="reviewer 完成",
                    cycle=1,
                    total_cycles=1,
                    elapsed_seconds=0.1,
                )
            )
        return self._result(version=2)

    def apply_revision_decision(self, project_id, decision):
        self.decisions.append((project_id, decision))
        return DecisionOutcome(
            status=decision,
            version_path=Path("projects/demo_20260627/outputs/100000-accept-v1"),
            renamed=False,
            message="ok",
        )

    def delete_project(self, project_id, permanent=False):
        self.deleted.append((project_id, permanent))
        return DeleteProjectResult(
            project_id=project_id,
            deleted_path=Path("projects/demo_20260627"),
            trash_path=None if permanent else Path("projects/.trash/demo_20260627"),
            permanent=permanent,
            message="deleted",
        )

    def save_model_profile(self, request):
        self.received_model_profile_request = request
        return ModelProfile(
            profile_id=request.profile_id,
            name=request.name,
            provider=request.provider,
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model,
            enable_search=request.enable_search,
            model_family=request.model_family,
            vision=request.vision,
            function_calling=request.function_calling,
            json_output=request.json_output,
            structured_output=request.structured_output,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
        )

    def activate_model_profile(self, role, profile_id):
        self.activated.append((role, profile_id))
        profile = self.list_model_profiles()[0]
        return ActiveModelProfile(role=role, profile_id=profile_id, profile=profile)

    def check_model_connections(self):
        return (
            ModelConnectionStatus(
                role="writer",
                model="qwen-plus",
                ok=True,
                message="ok",
                elapsed_seconds=0.1,
            ),
        )

    def _result(self, version):
        return RevisionRunResult(
            project_id="demo_20260627",
            project_path=Path("projects/demo_20260627"),
            version=version,
            version_path=Path(f"projects/demo_20260627/outputs/100000-pending-v{version}"),
            latest_path=Path("projects/demo_20260627/latest"),
            status="pending",
            mode="dry-run",
            requested_cycles=1,
            actual_cycles=1,
            stopped_early=False,
            stop_reason=None,
            artifacts=ArtifactLinks(
                final_md=Path("projects/demo_20260627/latest/final_draft/final.md")
            ),
        )


class WebApiEndpointTests(TestCase):
    def test_list_projects_endpoint(self):
        client = TestClient(create_app(application=FakeWebApplication()))

        response = client.get("/api/projects")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["projects"][0]["project_id"], "demo_20260627")

    def test_project_detail_endpoint(self):
        client = TestClient(create_app(application=FakeWebApplication()))

        response = client.get("/api/projects/demo_20260627")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["project_id"], "demo_20260627")
        self.assertEqual(response.json()["versions"][0]["artifacts"]["final_md"], "projects/demo_20260627/latest/final_draft/final.md")

    def test_list_model_profiles_endpoint(self):
        client = TestClient(create_app(application=FakeWebApplication()))

        response = client.get("/api/model-profiles")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profiles"][0]["profile_id"], "writer-qwen")

    def test_get_active_model_profile_endpoint(self):
        client = TestClient(create_app(application=FakeWebApplication()))

        response = client.get("/api/model-profiles/active/writer")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile"]["profile_id"], "writer-qwen")

    def test_start_project_endpoint_records_completed_run(self):
        fake_app = FakeWebApplication()
        client = TestClient(
            create_app(
                application=fake_app,
                run_store=InMemoryRunStore(),
                run_synchronously=True,
            )
        )

        response = client.post(
            "/api/projects/start",
            json={"requirements_text": "请写一份计划", "cycles": 1, "dry_run": True},
        )
        poll = client.get(f"/api/runs/{response.json()['run_id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(poll.json()["status"], "completed")
        self.assertEqual(poll.json()["result"]["version"], 1)
        self.assertEqual(poll.json()["events"][0]["display_message"], "writer 完成（1/1，用时 0.2 秒）")
        self.assertIsInstance(fake_app.received_start_request, StartProjectRequest)
        self.assertEqual(fake_app.received_start_request.requirements_text, "请写一份计划")

    def test_start_project_requires_requirements(self):
        client = TestClient(
            create_app(
                application=FakeWebApplication(),
                run_store=InMemoryRunStore(),
                run_synchronously=True,
            )
        )

        response = client.post("/api/projects/start", json={"requirements_text": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "requirements_text is required")

    def test_continue_project_endpoint_records_completed_run(self):
        fake_app = FakeWebApplication()
        client = TestClient(
            create_app(
                application=fake_app,
                run_store=InMemoryRunStore(),
                run_synchronously=True,
            )
        )

        response = client.post(
            "/api/projects/demo_20260627/continue",
            json={"feedback_text": "请继续压缩篇幅", "cycles": 1},
        )
        poll = client.get(f"/api/runs/{response.json()['run_id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(poll.json()["result"]["version"], 2)
        self.assertIsInstance(fake_app.received_continue_request, ContinueRevisionRequest)
        self.assertEqual(fake_app.received_continue_request.project_id, "demo_20260627")

    def test_decision_endpoint(self):
        fake_app = FakeWebApplication()
        client = TestClient(create_app(application=fake_app))

        response = client.post(
            "/api/projects/demo_20260627/decision",
            json={"decision": "accept"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accept")
        self.assertEqual(fake_app.decisions, [("demo_20260627", "accept")])

    def test_delete_project_endpoint_supports_permanent(self):
        fake_app = FakeWebApplication()
        client = TestClient(create_app(application=fake_app))

        response = client.request(
            "DELETE",
            "/api/projects/demo_20260627",
            json={"permanent": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["permanent"])
        self.assertEqual(fake_app.deleted, [("demo_20260627", True)])

    def test_save_and_activate_model_profile(self):
        fake_app = FakeWebApplication()
        client = TestClient(create_app(application=fake_app))

        saved = client.post(
            "/api/model-profiles",
            json={"profile_id": "p1", "name": "P1", "model": "qwen-plus"},
        )
        activated = client.post(
            "/api/model-profiles/p1/activate",
            json={"role": "writer"},
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["profile_id"], "p1")
        self.assertIsInstance(fake_app.received_model_profile_request, ModelProfileRequest)
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["role"], "writer")
        self.assertEqual(fake_app.activated, [("writer", "p1")])

    def test_check_model_connections_endpoint(self):
        client = TestClient(create_app(application=FakeWebApplication()))

        response = client.post("/api/model-connections/check")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["connections"][0]["ok"])

    def test_open_artifact_endpoint_uses_injected_opener_for_project_path(self):
        opened = []
        with TemporaryDirectory() as temp_dir:
            projects_root = Path(temp_dir) / "projects"
            artifact = projects_root / "demo" / "latest" / "final_draft" / "final.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("draft", encoding="utf-8")
            client = TestClient(
                create_app(
                    application=FakeWebApplication(),
                    opener=lambda path, mode: opened.append((path, mode)),
                    projects_root=projects_root,
                )
            )

            response = client.post(
                "/api/artifacts/open",
                json={"path": artifact.as_posix(), "mode": "open"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "opened")
        self.assertEqual(opened, [(artifact.resolve(), "open")])

    def test_open_artifact_endpoint_rejects_paths_outside_projects_root(self):
        opened = []
        with TemporaryDirectory() as temp_dir:
            projects_root = Path(temp_dir) / "projects"
            projects_root.mkdir()
            outside = Path(temp_dir) / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            client = TestClient(
                create_app(
                    application=FakeWebApplication(),
                    opener=lambda path, mode: opened.append((path, mode)),
                    projects_root=projects_root,
                )
            )

            response = client.post(
                "/api/artifacts/open",
                json={"path": outside.as_posix(), "mode": "open"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(opened, [])

    def test_open_artifact_endpoint_supports_reveal_mode(self):
        opened = []
        with TemporaryDirectory() as temp_dir:
            projects_root = Path(temp_dir) / "projects"
            version_dir = projects_root / "demo" / "outputs" / "100000-pending-v1"
            version_dir.mkdir(parents=True)
            client = TestClient(
                create_app(
                    application=FakeWebApplication(),
                    opener=lambda path, mode: opened.append((path, mode)),
                    projects_root=projects_root,
                )
            )

            response = client.post(
                "/api/artifacts/open",
                json={"path": version_dir.as_posix(), "mode": "reveal"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(opened, [(version_dir.resolve(), "reveal")])
