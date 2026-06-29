# Local HTML GUI MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local browser-based GUI MVP that lets users manage projects, run new/continued revisions, view progress, manage model profiles, check connections, and apply project decisions through a FastAPI-backed local HTML page.

**Architecture:** Add a thin `office_revision.web` adapter around the existing `RevisionApplication` facade. Long-running revision calls execute in a local in-memory background run store; the browser polls run status. The frontend starts as plain HTML/CSS/JavaScript served by the same local FastAPI app.

**Tech Stack:** Python, FastAPI, Uvicorn, Starlette TestClient, plain HTML/CSS/JavaScript, existing `office_revision.application` services.

---

## File Structure

- Create `office_revision/web/__init__.py`
  - Exposes the web app package.
- Create `office_revision/web/schemas.py`
  - Defines JSON-safe serializers and request parsing helpers for HTTP routes.
- Create `office_revision/web/runs.py`
  - Defines `RunRecord` and `InMemoryRunStore` for background run tracking.
- Create `office_revision/web/app.py`
  - Creates the FastAPI application, mounts static files, and defines API routes.
- Create `office_revision/web/static/index.html`
  - Provides the first single-page local GUI.
- Create `office_revision/web/static/styles.css`
  - Provides basic layout and state styling.
- Create `office_revision/web/static/app.js`
  - Provides browser-side API calls and UI rendering.
- Create `run_gui.py`
  - Starts the local GUI server on `127.0.0.1`.
- Modify `requirements.txt`
  - Add FastAPI, Uvicorn, and multipart upload support.
- Create `tests/test_web_runs.py`
  - Unit tests for the in-memory run store.
- Create `tests/test_web_api.py`
  - API tests with injected fake application services.
- Create `tests/test_web_static.py`
  - Static frontend smoke tests.
- Modify `.gitignore`
  - Ignore temporary GUI upload/runtime files if the implementation creates a local temp directory under the project.

## Task 1: Add Web Dependencies and Package Skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `office_revision/web/__init__.py`
- Create: `office_revision/web/app.py`
- Test: `tests/test_web_static.py`

- [ ] **Step 1: Write the failing static-app smoke test**

Create `tests/test_web_static.py`:

```python
from fastapi.testclient import TestClient

from office_revision.web.app import create_app


def test_web_root_serves_html_page():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "多 Agent 办公文档修订助手" in response.text
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_static
```

Expected: FAIL or import error because `office_revision.web.app` does not exist.

- [ ] **Step 3: Add dependencies**

Modify `requirements.txt` so it contains:

```text
autogen-agentchat
autogen-ext[openai]
python-docx
fastapi
uvicorn
python-multipart
```

If the local virtual environment does not already have these packages, install them:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- [ ] **Step 4: Add web package skeleton**

Create `office_revision/web/__init__.py`:

```python
"""Local web GUI for the office revision assistant."""
```

Create `office_revision/web/app.py`:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def create_app() -> FastAPI:
    app = FastAPI(title="多 Agent 办公文档修订助手")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>多 Agent 办公文档修订助手</title>
  </head>
  <body>
    <h1>多 Agent 办公文档修订助手</h1>
  </body>
</html>
"""

    return app
```

- [ ] **Step 5: Run the test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_static
```

Expected: PASS.

## Task 2: Add JSON Serialization Helpers

**Files:**
- Create: `office_revision/web/schemas.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Write failing serializer tests**

Create `tests/test_web_api.py`:

```python
from pathlib import Path
from unittest import TestCase

from office_revision.application.contracts import (
    ArtifactLinks,
    ProjectSummary,
    RevisionRunResult,
)
from office_revision.web.schemas import path_to_string, revision_result_to_dict, project_summary_to_dict


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
            latest_mode="real",
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
            artifacts=ArtifactLinks(final_md=Path("projects/demo_20260627/latest/final_draft/final.md")),
            warnings=("latest locked",),
        )

        payload = revision_result_to_dict(result)

        self.assertEqual(payload["project_id"], "demo_20260627")
        self.assertEqual(payload["artifacts"]["final_md"], "projects/demo_20260627/latest/final_draft/final.md")
        self.assertEqual(payload["warnings"], ["latest locked"])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api
```

Expected: FAIL because `office_revision.web.schemas` does not exist.

- [ ] **Step 3: Implement serializers**

Create `office_revision/web/schemas.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from office_revision.application.contracts import (
    ArtifactLinks,
    ModelProfile,
    ProgressEvent,
    ProjectDetail,
    ProjectSummary,
    RevisionRunResult,
    VersionSummary,
)


def path_to_string(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.as_posix()


def artifacts_to_dict(artifacts: ArtifactLinks) -> dict[str, str | None]:
    return {
        "final_docx": path_to_string(artifacts.final_docx),
        "final_md": path_to_string(artifacts.final_md),
        "revision_summary_docx": path_to_string(artifacts.revision_summary_docx),
        "revision_summary_md": path_to_string(artifacts.revision_summary_md),
        "final_review_report_docx": path_to_string(artifacts.final_review_report_docx),
        "final_review_report_md": path_to_string(artifacts.final_review_report_md),
        "run_log": path_to_string(artifacts.run_log),
    }


def project_summary_to_dict(summary: ProjectSummary) -> dict[str, Any]:
    return {
        "project_id": summary.project_id,
        "title": summary.title,
        "created_date": summary.created_date,
        "path": path_to_string(summary.path),
        "latest_status": summary.latest_status,
        "latest_version": summary.latest_version,
        "latest_mode": summary.latest_mode,
    }


def version_summary_to_dict(version: VersionSummary) -> dict[str, Any]:
    return {
        "name": version.name,
        "version": version.version,
        "status": version.status,
        "mode": version.mode,
        "created_at": version.created_at,
        "path": path_to_string(version.path),
        "is_latest": version.is_latest,
        "artifacts": artifacts_to_dict(version.artifacts),
    }


def project_detail_to_dict(detail: ProjectDetail) -> dict[str, Any]:
    return {
        "summary": project_summary_to_dict(detail.summary),
        "versions": [version_summary_to_dict(version) for version in detail.versions],
        "inputs": {name: path_to_string(path) for name, path in detail.inputs.items()},
    }


def progress_event_to_dict(event: ProgressEvent) -> dict[str, Any]:
    return {
        "stage": event.stage,
        "message": event.message,
        "display_message": event.display_message(),
        "cycle": event.cycle,
        "total_cycles": event.total_cycles,
        "elapsed_seconds": event.elapsed_seconds,
    }


def revision_result_to_dict(result: RevisionRunResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "project_path": path_to_string(result.project_path),
        "version": result.version,
        "version_path": path_to_string(result.version_path),
        "latest_path": path_to_string(result.latest_path),
        "status": result.status,
        "mode": result.mode,
        "requested_cycles": result.requested_cycles,
        "actual_cycles": result.actual_cycles,
        "stopped_early": result.stopped_early,
        "stop_reason": result.stop_reason,
        "artifacts": artifacts_to_dict(result.artifacts),
        "warnings": list(result.warnings),
    }


def model_profile_to_dict(profile: ModelProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "provider": profile.provider,
        "api_key": profile.api_key,
        "base_url": profile.base_url,
        "model": profile.model,
        "enable_search": profile.enable_search,
        "model_family": profile.model_family,
        "vision": profile.vision,
        "function_calling": profile.function_calling,
        "json_output": profile.json_output,
        "structured_output": profile.structured_output,
        "timeout_seconds": profile.timeout_seconds,
        "max_retries": profile.max_retries,
    }
```

- [ ] **Step 4: Run serializer tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api
```

Expected: PASS.

## Task 3: Add In-Memory Run Store

**Files:**
- Create: `office_revision/web/runs.py`
- Modify: `tests/test_web_runs.py`

- [ ] **Step 1: Write failing run-store tests**

Create `tests/test_web_runs.py`:

```python
from unittest import TestCase

from office_revision.application.contracts import ProgressEvent
from office_revision.web.runs import InMemoryRunStore


class InMemoryRunStoreTests(TestCase):
    def test_create_run_starts_as_queued(self):
        store = InMemoryRunStore()

        record = store.create_run(kind="start_project", project_id=None)

        self.assertEqual(record.status, "queued")
        self.assertEqual(record.kind, "start_project")
        self.assertIsNone(record.project_id)
        self.assertEqual(record.events, ())

    def test_append_event_preserves_order(self):
        store = InMemoryRunStore()
        record = store.create_run(kind="continue_revision", project_id="demo")

        store.mark_running(record.run_id)
        store.append_event(record.run_id, ProgressEvent(stage="reading_inputs", message="读取输入文件"))
        store.append_event(record.run_id, ProgressEvent(stage="completed", message="运行完成"))

        updated = store.get_run(record.run_id)

        self.assertEqual(updated.status, "running")
        self.assertEqual([event.stage for event in updated.events], ["reading_inputs", "completed"])

    def test_mark_failed_records_error_and_stage(self):
        store = InMemoryRunStore()
        record = store.create_run(kind="start_project", project_id=None)

        store.mark_failed(record.run_id, stage="validation", message="requirements is required")

        updated = store.get_run(record.run_id)

        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.error, {"stage": "validation", "message": "requirements is required"})
        self.assertIsNotNone(updated.finished_at)
```

- [ ] **Step 2: Run run-store tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_runs
```

Expected: FAIL because `office_revision.web.runs` does not exist.

- [ ] **Step 3: Implement run store**

Create `office_revision/web/runs.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from office_revision.application.contracts import ProgressEvent, RevisionRunResult


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    kind: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    events: tuple[ProgressEvent, ...] = ()
    result: RevisionRunResult | None = None
    error: dict[str, str] | None = None
    project_id: str | None = None


class InMemoryRunStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, RunRecord] = {}

    def create_run(self, *, kind: str, project_id: str | None) -> RunRecord:
        record = RunRecord(
            run_id=uuid4().hex,
            kind=kind,
            status="queued",
            created_at=utc_now_iso(),
            project_id=project_id,
        )
        with self._lock:
            self._runs[record.run_id] = record
        return record

    def get_run(self, run_id: str) -> RunRecord:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            return self._runs[run_id]

    def mark_running(self, run_id: str) -> RunRecord:
        return self._update(run_id, status="running", started_at=utc_now_iso())

    def append_event(self, run_id: str, event: ProgressEvent) -> RunRecord:
        with self._lock:
            record = self._runs[run_id]
            updated = replace(record, events=record.events + (event,))
            self._runs[run_id] = updated
            return updated

    def mark_completed(self, run_id: str, result: RevisionRunResult) -> RunRecord:
        return self._update(run_id, status="completed", finished_at=utc_now_iso(), result=result)

    def mark_failed(self, run_id: str, *, stage: str, message: str) -> RunRecord:
        return self._update(
            run_id,
            status="failed",
            finished_at=utc_now_iso(),
            error={"stage": stage, "message": message},
        )

    def _update(self, run_id: str, **changes: Any) -> RunRecord:
        with self._lock:
            record = self._runs[run_id]
            updated = replace(record, **changes)
            self._runs[run_id] = updated
            return updated
```

- [ ] **Step 4: Run run-store tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_runs
```

Expected: PASS.

## Task 4: Add Read-Only Project and Model Profile API Endpoints

**Files:**
- Modify: `office_revision/web/app.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add fake application and failing endpoint tests**

Append to `tests/test_web_api.py`:

```python
from office_revision.application.contracts import ModelProfile
from office_revision.web.app import create_app
from fastapi.testclient import TestClient


class FakeReadOnlyApplication:
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
            return self.list_model_profiles()[0]
        return None


class WebReadOnlyApiTests(TestCase):
    def test_list_projects_endpoint(self):
        client = TestClient(create_app(application=FakeReadOnlyApplication()))

        response = client.get("/api/projects")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["projects"][0]["project_id"], "demo_20260627")

    def test_list_model_profiles_endpoint(self):
        client = TestClient(create_app(application=FakeReadOnlyApplication()))

        response = client.get("/api/model-profiles")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profiles"][0]["profile_id"], "writer-qwen")

    def test_get_active_model_profile_endpoint(self):
        client = TestClient(create_app(application=FakeReadOnlyApplication()))

        response = client.get("/api/model-profiles/active/writer")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile"]["profile_id"], "writer-qwen")
```

- [ ] **Step 2: Run endpoint tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api
```

Expected: FAIL because `create_app()` does not accept injected `application` and endpoints do not exist.

- [ ] **Step 3: Implement read-only endpoints**

Replace `office_revision/web/app.py` with:

```python
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from office_revision.application import RevisionApplication
from office_revision.web.schemas import model_profile_to_dict, project_summary_to_dict


def create_app(application: RevisionApplication | None = None) -> FastAPI:
    revision_app = application or RevisionApplication()
    app = FastAPI(title="多 Agent 办公文档修订助手")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>多 Agent 办公文档修订助手</title>
  </head>
  <body>
    <h1>多 Agent 办公文档修订助手</h1>
  </body>
</html>
"""

    @app.get("/api/projects")
    def list_projects() -> dict[str, object]:
        return {"projects": [project_summary_to_dict(project) for project in revision_app.list_projects()]}

    @app.get("/api/model-profiles")
    def list_model_profiles() -> dict[str, object]:
        return {"profiles": [model_profile_to_dict(profile) for profile in revision_app.list_model_profiles()]}

    @app.get("/api/model-profiles/active/{role}")
    def get_active_model_profile(role: str) -> dict[str, object]:
        profile = revision_app.get_active_model_profile(role)
        if profile is None:
            raise HTTPException(status_code=404, detail=f"No active model profile for {role}")
        return {"profile": model_profile_to_dict(profile)}

    return app
```

- [ ] **Step 4: Run endpoint tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api
```

Expected: PASS.

## Task 5: Add Run Polling and Dry-Run Start Project Endpoint

**Files:**
- Modify: `office_revision/web/app.py`
- Modify: `office_revision/web/schemas.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add fake start-project tests**

Append to `tests/test_web_api.py`:

```python
from office_revision.application.contracts import StartProjectRequest, ProgressEvent, ArtifactLinks, RevisionRunResult
from office_revision.web.runs import InMemoryRunStore


class FakeStartProjectApplication(FakeReadOnlyApplication):
    def __init__(self):
        self.received_request = None

    def start_new_project(self, request, *, on_progress=None):
        self.received_request = request
        if on_progress is not None:
            on_progress(ProgressEvent(stage="reading_inputs", message="读取输入文件"))
            on_progress(ProgressEvent(stage="completed", message="运行完成"))
        return RevisionRunResult(
            project_id="demo_20260627",
            project_path=Path("projects/demo_20260627"),
            version=1,
            version_path=Path("projects/demo_20260627/outputs/100000-pending-v1"),
            latest_path=Path("projects/demo_20260627/latest"),
            status="pending",
            mode="dry-run",
            requested_cycles=request.cycles,
            actual_cycles=request.cycles,
            stopped_early=False,
            stop_reason=None,
            artifacts=ArtifactLinks(final_md=Path("projects/demo_20260627/latest/final_draft/final.md")),
        )


class WebStartProjectApiTests(TestCase):
    def test_start_project_returns_run_id_and_polling_result(self):
        fake_app = FakeStartProjectApplication()
        run_store = InMemoryRunStore()
        client = TestClient(create_app(application=fake_app, run_store=run_store, run_synchronously=True))

        response = client.post(
            "/api/projects/start",
            json={"requirements_text": "请写一份项目简介", "cycles": 1, "dry_run": True},
        )

        self.assertEqual(response.status_code, 200)
        run_id = response.json()["run_id"]
        self.assertIsInstance(fake_app.received_request, StartProjectRequest)
        self.assertEqual(fake_app.received_request.requirements_text, "请写一份项目简介")

        poll = client.get(f"/api/runs/{run_id}")

        self.assertEqual(poll.status_code, 200)
        payload = poll.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual([event["stage"] for event in payload["events"]], ["reading_inputs", "completed"])
        self.assertEqual(payload["result"]["project_id"], "demo_20260627")

    def test_start_project_requires_requirements(self):
        client = TestClient(create_app(application=FakeStartProjectApplication(), run_store=InMemoryRunStore(), run_synchronously=True))

        response = client.post("/api/projects/start", json={"requirements_text": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertIn("requirements", response.json()["detail"])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api
```

Expected: FAIL because run endpoints and start endpoint do not exist.

- [ ] **Step 3: Add run serializer**

Append to `office_revision/web/schemas.py`:

```python
from office_revision.web.runs import RunRecord


def run_record_to_dict(record: RunRecord) -> dict[str, Any]:
    return {
        "run_id": record.run_id,
        "kind": record.kind,
        "status": record.status,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "events": [progress_event_to_dict(event) for event in record.events],
        "result": revision_result_to_dict(record.result) if record.result is not None else None,
        "error": record.error,
        "project_id": record.project_id,
    }
```

- [ ] **Step 4: Implement start and run endpoints**

Modify `office_revision/web/app.py`:

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from office_revision.application import RevisionApplication
from office_revision.application.contracts import RevisionApplicationError, StartProjectRequest
from office_revision.web.runs import InMemoryRunStore
from office_revision.web.schemas import (
    model_profile_to_dict,
    project_summary_to_dict,
    run_record_to_dict,
)


def create_app(
    application: RevisionApplication | None = None,
    run_store: InMemoryRunStore | None = None,
    *,
    run_synchronously: bool = False,
) -> FastAPI:
    revision_app = application or RevisionApplication()
    runs = run_store or InMemoryRunStore()
    executor = ThreadPoolExecutor(max_workers=1)
    app = FastAPI(title="多 Agent 办公文档修订助手")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>多 Agent 办公文档修订助手</title>
  </head>
  <body>
    <h1>多 Agent 办公文档修订助手</h1>
  </body>
</html>
"""

    @app.get("/api/projects")
    def list_projects() -> dict[str, object]:
        return {"projects": [project_summary_to_dict(project) for project in revision_app.list_projects()]}

    @app.get("/api/model-profiles")
    def list_model_profiles() -> dict[str, object]:
        return {"profiles": [model_profile_to_dict(profile) for profile in revision_app.list_model_profiles()]}

    @app.get("/api/model-profiles/active/{role}")
    def get_active_model_profile(role: str) -> dict[str, object]:
        profile = revision_app.get_active_model_profile(role)
        if profile is None:
            raise HTTPException(status_code=404, detail=f"No active model profile for {role}")
        return {"profile": model_profile_to_dict(profile)}

    @app.post("/api/projects/start")
    def start_project(payload: dict[str, object]) -> dict[str, str]:
        requirements_text = str(payload.get("requirements_text") or "")
        if not requirements_text.strip() and not payload.get("requirements_path"):
            raise HTTPException(status_code=400, detail="requirements_text or requirements_path is required")
        request = StartProjectRequest(
            requirements_text=requirements_text,
            source_text=str(payload.get("source_text") or "") or None,
            meeting_notes_text=str(payload.get("meeting_notes_text") or "") or None,
            project_title=str(payload.get("project_title") or "") or None,
            cycles=int(payload.get("cycles") or 2),
            dry_run=bool(payload.get("dry_run") or False),
            summary_mode=str(payload.get("summary_mode") or "rule"),
        )
        record = runs.create_run(kind="start_project", project_id=None)

        def worker() -> None:
            runs.mark_running(record.run_id)
            try:
                result = revision_app.start_new_project(
                    request,
                    on_progress=lambda event: runs.append_event(record.run_id, event),
                )
                runs.mark_completed(record.run_id, result)
            except RevisionApplicationError as exc:
                runs.mark_failed(record.run_id, stage=exc.stage, message=str(exc))
            except Exception as exc:
                runs.mark_failed(record.run_id, stage="unexpected", message=str(exc))

        if run_synchronously:
            worker()
        else:
            executor.submit(worker)
        return {"run_id": record.run_id}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        try:
            return run_record_to_dict(runs.get_run(run_id))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    return app
```

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api tests.test_web_runs tests.test_web_static
```

Expected: PASS.

## Task 6: Add Continue, Decision, Delete, Model Save/Activate, and Connection Endpoints

**Files:**
- Modify: `office_revision/web/app.py`
- Modify: `office_revision/web/schemas.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add endpoint tests with fake application**

Append focused tests to `tests/test_web_api.py`:

```python
from office_revision.application.contracts import ContinueRevisionRequest, DecisionOutcome, DeleteProjectResult, ModelConnectionStatus, ModelProfileRequest, ActiveModelProfile


class FakeFullApplication(FakeStartProjectApplication):
    def continue_existing_revision(self, request, *, on_progress=None):
        self.received_continue_request = request
        if on_progress is not None:
            on_progress(ProgressEvent(stage="reading_inputs", message="读取输入文件"))
        return RevisionRunResult(
            project_id=str(request.project_id),
            project_path=Path(f"projects/{request.project_id}"),
            version=2,
            version_path=Path(f"projects/{request.project_id}/outputs/100000-continue-v2"),
            latest_path=Path(f"projects/{request.project_id}/latest"),
            status="pending",
            mode="dry-run",
            requested_cycles=request.cycles,
            actual_cycles=request.cycles,
            stopped_early=False,
            stop_reason=None,
            artifacts=ArtifactLinks(final_md=Path(f"projects/{request.project_id}/latest/final_draft/final.md")),
        )

    def apply_revision_decision(self, project, decision, *, version_dir=None, dry_run=None):
        return DecisionOutcome(status=decision, version_path=Path(f"projects/{project}/latest"), renamed=False, message="ok")

    def delete_project(self, project, *, permanent=False, deleted_at=None):
        return DeleteProjectResult(
            project_id=str(project),
            deleted_path=Path(f"projects/{project}"),
            trash_path=None if permanent else Path(f"projects/.trash/{project}"),
            permanent=permanent,
            message="deleted",
        )

    def save_model_profile(self, request):
        self.received_model_request = request
        return ModelProfile(
            profile_id=request.profile_id,
            name=request.name,
            provider=request.provider,
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model,
        )

    def activate_model_profile(self, role, profile_id):
        profile = self.save_model_profile(
            ModelProfileRequest(profile_id=profile_id, name="Activated", model="qwen-plus")
        )
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


class WebMutationApiTests(TestCase):
    def test_continue_project_endpoint(self):
        fake_app = FakeFullApplication()
        client = TestClient(create_app(application=fake_app, run_store=InMemoryRunStore(), run_synchronously=True))

        response = client.post("/api/projects/demo_20260627/continue", json={"feedback_text": "请继续压缩篇幅", "cycles": 1})

        self.assertEqual(response.status_code, 200)
        poll = client.get(f"/api/runs/{response.json()['run_id']}")
        self.assertEqual(poll.json()["result"]["version"], 2)
        self.assertIsInstance(fake_app.received_continue_request, ContinueRevisionRequest)

    def test_decision_endpoint(self):
        client = TestClient(create_app(application=FakeFullApplication(), run_store=InMemoryRunStore(), run_synchronously=True))

        response = client.post("/api/projects/demo_20260627/decision", json={"decision": "accept"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accept")

    def test_delete_project_endpoint_supports_permanent(self):
        client = TestClient(create_app(application=FakeFullApplication(), run_store=InMemoryRunStore(), run_synchronously=True))

        response = client.request("DELETE", "/api/projects/demo_20260627", json={"permanent": True})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["permanent"])

    def test_save_and_activate_model_profile(self):
        client = TestClient(create_app(application=FakeFullApplication(), run_store=InMemoryRunStore(), run_synchronously=True))

        saved = client.post("/api/model-profiles", json={"profile_id": "p1", "name": "P1", "model": "qwen-plus"})
        activated = client.post("/api/model-profiles/p1/activate", json={"role": "writer"})

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["profile_id"], "p1")
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["role"], "writer")

    def test_check_model_connections_endpoint(self):
        client = TestClient(create_app(application=FakeFullApplication(), run_store=InMemoryRunStore(), run_synchronously=True))

        response = client.post("/api/model-connections/check")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["connections"][0]["ok"])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api
```

Expected: FAIL because mutation endpoints do not exist.

- [ ] **Step 3: Add serializers for decisions, deletions, connections, and active profiles**

Append to `office_revision/web/schemas.py`:

```python
from office_revision.application.contracts import (
    ActiveModelProfile,
    DecisionOutcome,
    DeleteProjectResult,
    ModelConnectionStatus,
)


def decision_outcome_to_dict(outcome: DecisionOutcome) -> dict[str, Any]:
    return {
        "status": outcome.status,
        "version_path": path_to_string(outcome.version_path),
        "renamed": outcome.renamed,
        "message": outcome.message,
    }


def delete_project_result_to_dict(result: DeleteProjectResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "deleted_path": path_to_string(result.deleted_path),
        "trash_path": path_to_string(result.trash_path),
        "permanent": result.permanent,
        "message": result.message,
    }


def model_connection_status_to_dict(status: ModelConnectionStatus) -> dict[str, Any]:
    return {
        "role": status.role,
        "model": status.model,
        "ok": status.ok,
        "message": status.message,
        "elapsed_seconds": status.elapsed_seconds,
    }


def active_model_profile_to_dict(active: ActiveModelProfile) -> dict[str, Any]:
    return {
        "role": active.role,
        "profile_id": active.profile_id,
        "profile": model_profile_to_dict(active.profile),
    }
```

- [ ] **Step 4: Implement mutation endpoints**

Modify imports in `office_revision/web/app.py`:

```python
from office_revision.application.contracts import (
    ContinueRevisionRequest,
    ModelProfileRequest,
    RevisionApplicationError,
    StartProjectRequest,
)
from office_revision.web.schemas import (
    active_model_profile_to_dict,
    decision_outcome_to_dict,
    delete_project_result_to_dict,
    model_connection_status_to_dict,
    model_profile_to_dict,
    project_summary_to_dict,
    run_record_to_dict,
)
```

Add routes before `return app`:

```python
    @app.post("/api/projects/{project_id}/continue")
    def continue_project(project_id: str, payload: dict[str, object]) -> dict[str, str]:
        request = ContinueRevisionRequest(
            project_id=project_id,
            feedback_text=str(payload.get("feedback_text") or "") or None,
            cycles=int(payload.get("cycles") or 2),
            dry_run=bool(payload.get("dry_run") or False),
            summary_mode=str(payload.get("summary_mode") or "rule"),
        )
        record = runs.create_run(kind="continue_revision", project_id=project_id)

        def worker() -> None:
            runs.mark_running(record.run_id)
            try:
                result = revision_app.continue_existing_revision(
                    request,
                    on_progress=lambda event: runs.append_event(record.run_id, event),
                )
                runs.mark_completed(record.run_id, result)
            except RevisionApplicationError as exc:
                runs.mark_failed(record.run_id, stage=exc.stage, message=str(exc))
            except Exception as exc:
                runs.mark_failed(record.run_id, stage="unexpected", message=str(exc))

        if run_synchronously:
            worker()
        else:
            executor.submit(worker)
        return {"run_id": record.run_id}

    @app.post("/api/projects/{project_id}/decision")
    def apply_decision(project_id: str, payload: dict[str, object]) -> dict[str, object]:
        decision = str(payload.get("decision") or "")
        if not decision:
            raise HTTPException(status_code=400, detail="decision is required")
        outcome = revision_app.apply_revision_decision(project_id, decision)
        return decision_outcome_to_dict(outcome)

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        permanent = bool((payload or {}).get("permanent") or False)
        result = revision_app.delete_project(project_id, permanent=permanent)
        return delete_project_result_to_dict(result)

    @app.post("/api/model-profiles")
    def save_model_profile(payload: dict[str, object]) -> dict[str, object]:
        request = ModelProfileRequest(
            profile_id=str(payload.get("profile_id") or ""),
            name=str(payload.get("name") or ""),
            model=str(payload.get("model") or ""),
            provider=str(payload.get("provider") or "openai-compatible"),
            api_key=str(payload.get("api_key") or ""),
            base_url=str(payload.get("base_url") or ""),
            enable_search=bool(payload.get("enable_search") or False),
            model_family=str(payload.get("model_family") or "unknown"),
            vision=bool(payload.get("vision") or False),
            function_calling=bool(payload.get("function_calling") or False),
            json_output=bool(payload.get("json_output") or False),
            structured_output=bool(payload.get("structured_output") or False),
            timeout_seconds=int(payload.get("timeout_seconds") or 60),
            max_retries=int(payload.get("max_retries") or 1),
        )
        profile = revision_app.save_model_profile(request)
        return model_profile_to_dict(profile)

    @app.post("/api/model-profiles/{profile_id}/activate")
    def activate_model_profile(profile_id: str, payload: dict[str, object]) -> dict[str, object]:
        role = str(payload.get("role") or "")
        if not role:
            raise HTTPException(status_code=400, detail="role is required")
        active = revision_app.activate_model_profile(role, profile_id)
        return active_model_profile_to_dict(active)

    @app.post("/api/model-connections/check")
    def check_model_connections() -> dict[str, object]:
        return {
            "connections": [
                model_connection_status_to_dict(status)
                for status in revision_app.check_model_connections()
            ]
        }
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api
```

Expected: PASS.

## Task 7: Replace Inline HTML With Static Frontend Files

**Files:**
- Modify: `office_revision/web/app.py`
- Create: `office_revision/web/static/index.html`
- Create: `office_revision/web/static/styles.css`
- Create: `office_revision/web/static/app.js`
- Modify: `tests/test_web_static.py`

- [ ] **Step 1: Add static asset tests**

Append to `tests/test_web_static.py`:

```python

def test_static_javascript_is_served():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "loadProjects" in response.text


def test_static_css_is_served():
    client = TestClient(create_app())

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert ".layout" in response.text
```

- [ ] **Step 2: Run static tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_static
```

Expected: FAIL because static files are not mounted.

- [ ] **Step 3: Add frontend files**

Create `office_revision/web/static/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>多 Agent 办公文档修订助手</title>
    <link rel="stylesheet" href="/static/styles.css">
  </head>
  <body>
    <header>
      <h1>多 Agent 办公文档修订助手</h1>
      <p>本地运行，项目和配置保存在当前工作目录。</p>
    </header>

    <main class="layout">
      <section class="panel">
        <h2>项目</h2>
        <button id="refresh-projects">刷新项目</button>
        <div id="projects"></div>
      </section>

      <section class="panel">
        <h2>新建项目</h2>
        <label>修改要求</label>
        <textarea id="requirements-text" rows="6" placeholder="请输入修改要求，必填"></textarea>
        <label>初稿，可选</label>
        <textarea id="source-text" rows="5" placeholder="可粘贴初稿；留空则按要求直接起草"></textarea>
        <label>会议纪要，可选</label>
        <textarea id="meeting-notes-text" rows="4"></textarea>
        <label>轮数</label>
        <input id="cycles" type="number" min="1" value="2">
        <label><input id="dry-run" type="checkbox"> dry-run 快速测试</label>
        <button id="start-project" disabled>开始修订</button>
      </section>

      <section class="panel">
        <h2>运行进度</h2>
        <div id="run-status">暂无运行</div>
        <ol id="run-events"></ol>
      </section>

      <section class="panel">
        <h2>模型配置</h2>
        <button id="refresh-profiles">刷新配置</button>
        <div id="profiles"></div>
      </section>
    </main>

    <script src="/static/app.js"></script>
  </body>
</html>
```

Create `office_revision/web/static/styles.css`:

```css
body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f6f7f9;
  color: #20242a;
}

header {
  padding: 24px 32px;
  background: #172033;
  color: white;
}

.layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  padding: 16px;
}

.panel {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 8px rgba(20, 30, 45, 0.08);
}

textarea,
input[type="number"] {
  width: 100%;
  box-sizing: border-box;
  margin: 6px 0 12px;
}

button {
  border: 0;
  border-radius: 8px;
  padding: 8px 12px;
  background: #2f6fed;
  color: white;
  cursor: pointer;
}

button:disabled {
  background: #aab3c2;
  cursor: not-allowed;
}

.item {
  border-top: 1px solid #e8ebf0;
  padding: 10px 0;
}
```

Create `office_revision/web/static/app.js`:

```javascript
const projectsEl = document.querySelector("#projects");
const profilesEl = document.querySelector("#profiles");
const requirementsEl = document.querySelector("#requirements-text");
const startButton = document.querySelector("#start-project");
const runStatusEl = document.querySelector("#run-status");
const runEventsEl = document.querySelector("#run-events");

function setText(el, text) {
  el.textContent = text;
}

async function loadProjects() {
  const response = await fetch("/api/projects");
  const payload = await response.json();
  projectsEl.innerHTML = "";
  for (const project of payload.projects) {
    const item = document.createElement("div");
    item.className = "item";
    item.textContent = `${project.title} (${project.project_id}) - v${project.latest_version || "-"} ${project.latest_status || ""}`;
    projectsEl.appendChild(item);
  }
}

async function loadModelProfiles() {
  const response = await fetch("/api/model-profiles");
  const payload = await response.json();
  profilesEl.innerHTML = "";
  for (const profile of payload.profiles) {
    const item = document.createElement("div");
    item.className = "item";
    item.textContent = `${profile.name} / ${profile.model}`;
    profilesEl.appendChild(item);
  }
}

function updateStartButton() {
  startButton.disabled = requirementsEl.value.trim().length === 0;
}

async function pollRun(runId) {
  const response = await fetch(`/api/runs/${runId}`);
  const payload = await response.json();
  setText(runStatusEl, payload.status);
  runEventsEl.innerHTML = "";
  for (const event of payload.events) {
    const item = document.createElement("li");
    item.textContent = event.display_message || event.message;
    runEventsEl.appendChild(item);
  }
  if (payload.status === "queued" || payload.status === "running") {
    window.setTimeout(() => pollRun(runId), 1000);
  }
}

async function startProject() {
  const response = await fetch("/api/projects/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      requirements_text: requirementsEl.value,
      source_text: document.querySelector("#source-text").value,
      meeting_notes_text: document.querySelector("#meeting-notes-text").value,
      cycles: Number(document.querySelector("#cycles").value || 2),
      dry_run: document.querySelector("#dry-run").checked
    })
  });
  const payload = await response.json();
  if (!response.ok) {
    setText(runStatusEl, payload.detail || "启动失败");
    return;
  }
  setText(runStatusEl, "started");
  pollRun(payload.run_id);
}

document.querySelector("#refresh-projects").addEventListener("click", loadProjects);
document.querySelector("#refresh-profiles").addEventListener("click", loadModelProfiles);
requirementsEl.addEventListener("input", updateStartButton);
startButton.addEventListener("click", startProject);

updateStartButton();
loadProjects();
loadModelProfiles();
```

- [ ] **Step 4: Mount static files and serve index file**

Modify `office_revision/web/app.py` imports:

```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
```

Replace the `/` route with:

```python
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")
```

- [ ] **Step 5: Run static tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_static
```

Expected: PASS.

## Task 8: Add Local GUI Launcher

**Files:**
- Create: `run_gui.py`
- Test: `tests/test_web_static.py`

- [ ] **Step 1: Add import smoke test for launcher**

Append to `tests/test_web_static.py`:

```python

def test_run_gui_module_imports():
    import run_gui

    assert callable(run_gui.main)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_static
```

Expected: FAIL because `run_gui.py` does not exist.

- [ ] **Step 3: Add launcher**

Create `run_gui.py`:

```python
from __future__ import annotations

import webbrowser

import uvicorn


def main() -> None:
    host = "127.0.0.1"
    port = 8765
    url = f"http://{host}:{port}"
    webbrowser.open(url)
    uvicorn.run("office_revision.web.app:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run launcher import test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_static
```

Expected: PASS.

Manual launch command after implementation:

```powershell
.\.venv\Scripts\python.exe run_gui.py
```

Expected: browser opens `http://127.0.0.1:8765`.

## Task 9: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused web tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_web_api tests.test_web_runs tests.test_web_static
```

Expected: all focused web tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Expected: all existing and new tests pass.

- [ ] **Step 3: Run compile check**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall -q office_revision tests
```

Expected: no output and exit code 0.

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors. Line-ending warnings may appear only if Git reports existing CRLF conversion warnings.

- [ ] **Step 5: Manual dry-run GUI test**

Run:

```powershell
.\.venv\Scripts\python.exe run_gui.py
```

In the browser:

1. Open `http://127.0.0.1:8765`.
2. Enter requirements text.
3. Enable dry-run.
4. Click start.
5. Confirm progress events appear.
6. Confirm a new project appears after refresh.
7. Confirm generated files exist under `projects/<project>/outputs/.../final_draft/`.

Expected: dry-run project completes without command-line arguments.

## Self-Review Notes

- The plan covers the approved GUI MVP design: local FastAPI server, plain HTML frontend, project/model profile endpoints, background run tracking, polling, start/continue/decision/delete/model connection actions, launcher, and tests.
- PDF support, trash restore, native exe packaging, and advanced document features are intentionally excluded from this MVP.
- The first implementation uses JSON text inputs. Multipart file upload support is included in dependencies but can be wired after the JSON MVP is stable if a smaller first slice is preferred.
- No Git commit is created by the assistant. If an implementation worker follows the generic skill header's commit steps, they must override that behavior for this project and leave committing to the user.
