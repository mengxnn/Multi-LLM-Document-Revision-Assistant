from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from office_revision.application import RevisionApplication
from office_revision.application.contracts import (
    ContinueRevisionRequest,
    ModelProfileRequest,
    RevisionApplicationError,
    StartProjectRequest,
)
from office_revision.web.runs import InMemoryRunStore
from office_revision.web.schemas import (
    active_model_profile_to_dict,
    decision_outcome_to_dict,
    delete_project_result_to_dict,
    model_connection_status_to_dict,
    model_profile_to_dict,
    project_detail_to_dict,
    project_summary_to_dict,
    run_record_to_dict,
)


def create_app(
    application: Any | None = None,
    run_store: InMemoryRunStore | None = None,
    run_synchronously: bool = False,
    opener: Callable[[Path, str], None] | None = None,
    projects_root: Path | str = Path("projects"),
) -> FastAPI:
    revision_app = application or RevisionApplication()
    runs = run_store or InMemoryRunStore()
    executor = ThreadPoolExecutor(max_workers=2)
    artifact_opener = opener or _open_local_path
    safe_projects_root = Path(projects_root).resolve()
    app = FastAPI(title="多 Agent 办公文档修订助手")
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/projects")
    def list_projects() -> dict[str, object]:
        return {
            "projects": [
                project_summary_to_dict(project)
                for project in revision_app.list_projects()
            ]
        }

    @app.post("/api/projects/start")
    def start_project(payload: dict[str, object]) -> dict[str, str]:
        requirements_text = _optional_string(payload.get("requirements_text"))
        requirements_path = _optional_string(payload.get("requirements_path"))
        if not requirements_text and not requirements_path:
            raise HTTPException(
                status_code=400,
                detail="requirements_text is required",
            )

        request = StartProjectRequest(
            requirements_text=requirements_text,
            requirements_path=requirements_path,
            source_text=_optional_string(payload.get("source_text")),
            source_path=_optional_string(payload.get("source_path")),
            meeting_notes_text=_optional_string(payload.get("meeting_notes_text")),
            meeting_notes_path=_optional_string(payload.get("meeting_notes_path")),
            project_title=_optional_string(payload.get("project_title")),
            cycles=_int_value(payload.get("cycles"), default=2),
            dry_run=_bool_value(payload.get("dry_run")),
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

        _run_worker(worker, executor=executor, run_synchronously=run_synchronously)
        return {"run_id": record.run_id}

    @app.get("/api/projects/{project_id}")
    def get_project_detail(project_id: str) -> dict[str, object]:
        return project_detail_to_dict(revision_app.get_project_details(project_id))

    @app.post("/api/projects/{project_id}/continue")
    def continue_project(project_id: str, payload: dict[str, object]) -> dict[str, str]:
        request = ContinueRevisionRequest(
            project_id=project_id,
            base_version_path=_optional_string(payload.get("base_version_path")),
            feedback_text=_optional_string(payload.get("feedback_text")),
            feedback_path=_optional_string(payload.get("feedback_path")),
            cycles=_int_value(payload.get("cycles"), default=2),
            dry_run=_bool_value(payload.get("dry_run")),
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

        _run_worker(worker, executor=executor, run_synchronously=run_synchronously)
        return {"run_id": record.run_id}

    @app.post("/api/projects/{project_id}/decision")
    def apply_decision(project_id: str, payload: dict[str, object]) -> dict[str, object]:
        decision = _optional_string(payload.get("decision"))
        if not decision:
            raise HTTPException(status_code=400, detail="decision is required")
        outcome = revision_app.apply_revision_decision(project_id, decision)
        return decision_outcome_to_dict(outcome)

    @app.delete("/api/projects/{project_id}")
    def delete_project(
        project_id: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = revision_app.delete_project(
            project_id,
            permanent=_bool_value((payload or {}).get("permanent")),
        )
        return delete_project_result_to_dict(result)

    @app.get("/api/model-profiles")
    def list_model_profiles() -> dict[str, object]:
        return {
            "profiles": [
                model_profile_to_dict(profile)
                for profile in revision_app.list_model_profiles()
            ]
        }

    @app.post("/api/model-profiles")
    def save_model_profile(payload: dict[str, object]) -> dict[str, object]:
        request = ModelProfileRequest(
            profile_id=str(payload.get("profile_id") or ""),
            name=str(payload.get("name") or ""),
            model=str(payload.get("model") or ""),
            provider=str(payload.get("provider") or "openai-compatible"),
            api_key=str(payload.get("api_key") or ""),
            base_url=str(payload.get("base_url") or ""),
            enable_search=_bool_value(payload.get("enable_search")),
            model_family=str(payload.get("model_family") or "unknown"),
            vision=_bool_value(payload.get("vision")),
            function_calling=_bool_value(payload.get("function_calling")),
            json_output=_bool_value(payload.get("json_output")),
            structured_output=_bool_value(payload.get("structured_output")),
            timeout_seconds=_int_value(payload.get("timeout_seconds"), default=60),
            max_retries=_int_value(payload.get("max_retries"), default=1),
        )
        profile = revision_app.save_model_profile(request)
        return model_profile_to_dict(profile)

    @app.get("/api/model-profiles/active/{role}")
    def get_active_model_profile(role: str) -> dict[str, object | None]:
        active = revision_app.get_active_model_profile(role)
        if active is None:
            return {"profile": None}
        return active_model_profile_to_dict(active)

    @app.post("/api/model-profiles/{profile_id}/activate")
    def activate_model_profile(
        profile_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        role = _optional_string(payload.get("role"))
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

    @app.post("/api/artifacts/open")
    def open_artifact(payload: dict[str, object]) -> dict[str, object]:
        path_text = _optional_string(payload.get("path"))
        mode = str(payload.get("mode") or "open")
        if not path_text:
            raise HTTPException(status_code=400, detail="path is required")
        if mode not in {"open", "reveal"}:
            raise HTTPException(status_code=400, detail="unsupported open mode")

        path = _resolve_project_path(path_text, projects_root=safe_projects_root)
        if not _is_relative_to(path, safe_projects_root):
            raise HTTPException(status_code=403, detail="path is outside projects")
        if not path.exists():
            raise HTTPException(status_code=404, detail="path not found")

        artifact_opener(path, mode)
        return {"status": "opened", "path": path.as_posix(), "mode": mode}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        try:
            record = runs.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        return run_record_to_dict(record)

    return app


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _int_value(value: object, *, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _bool_value(value: object) -> bool:
    return bool(value)


def _run_worker(
    worker: Any,
    *,
    executor: ThreadPoolExecutor,
    run_synchronously: bool,
) -> None:
    if run_synchronously:
        worker()
    else:
        executor.submit(worker)


def _resolve_project_path(path_text: str, *, projects_root: Path) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.parts and candidate.parts[0] == projects_root.name:
        return (Path.cwd() / candidate).resolve()
    return (projects_root / candidate).resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _open_local_path(path: Path, mode: str) -> None:
    if mode == "reveal":
        if sys.platform.startswith("win") and path.is_file():
            subprocess.Popen(["explorer", f"/select,{path}"])
            return
        target = path if path.is_dir() else path.parent
    else:
        target = path

    if hasattr(os, "startfile"):
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
