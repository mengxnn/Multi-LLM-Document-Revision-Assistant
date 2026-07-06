from __future__ import annotations

from pathlib import Path
from typing import Any

from office_revision.application.contracts import (
    ActiveModelProfile,
    ArtifactLinks,
    DecisionOutcome,
    DeleteProjectResult,
    InputSummary,
    ModelConnectionStatus,
    ModelProfile,
    ProgressEvent,
    ProjectDetail,
    ProjectSummary,
    RevisionRunResult,
    VersionSummary,
)
from office_revision.web.runs import RunRecord


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
        "final_review_report_docx": path_to_string(
            artifacts.final_review_report_docx
        ),
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


def input_summary_to_dict(summary: InputSummary) -> dict[str, Any]:
    return {
        "name": summary.name,
        "kind": summary.kind,
        "size_bytes": summary.size_bytes,
        "extracted_chars": summary.extracted_chars,
        "warnings": list(summary.warnings),
    }


def project_detail_to_dict(detail: ProjectDetail) -> dict[str, Any]:
    return {
        "summary": project_summary_to_dict(detail.summary),
        "versions": [version_summary_to_dict(version) for version in detail.versions],
        "inputs": {name: path_to_string(path) for name, path in detail.inputs.items()},
        "input_summaries": {
            name: input_summary_to_dict(summary)
            for name, summary in detail.input_summaries.items()
        },
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


def run_record_to_dict(record: RunRecord) -> dict[str, Any]:
    return {
        "run_id": record.run_id,
        "kind": record.kind,
        "status": record.status,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "events": [progress_event_to_dict(event) for event in record.events],
        "result": revision_result_to_dict(record.result) if record.result else None,
        "error": record.error,
        "project_id": record.project_id,
    }
