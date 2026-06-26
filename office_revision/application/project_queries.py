from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..project_paths import read_manifest, status_from_dir, version_number_from_dir
from .contracts import ArtifactLinks, ProjectDetail, ProjectSummary, VersionSummary


ARTIFACT_KEYS = (
    "final_docx",
    "final_md",
    "revision_summary_docx",
    "revision_summary_md",
    "final_review_report_docx",
    "final_review_report_md",
    "run_log",
)


class ProjectQueryService:
    def __init__(self, projects_root: str | Path = "projects") -> None:
        self.projects_root = Path(projects_root)

    def list_projects(self) -> tuple[ProjectSummary, ...]:
        if not self.projects_root.exists():
            return ()
        projects = [
            self._summary(path)
            for path in self.projects_root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        ]
        projects.sort(key=lambda item: (item.created_date, item.project_id), reverse=True)
        return tuple(projects)

    def get_project_details(self, project: str | Path) -> ProjectDetail:
        project_dir = self.resolve_project(project)
        summary = self._summary(project_dir)
        latest = _read_json(project_dir / "metadata" / "latest.json")
        versions = []
        for mode, output_name in (("real", "outputs"), ("dry_run", "dry_run_outputs")):
            output_root = project_dir / output_name
            if not output_root.exists():
                continue
            for version_dir in output_root.iterdir():
                if not version_dir.is_dir() or version_dir.name == "latest":
                    continue
                versions.append(_version_summary(version_dir, mode=mode, latest=latest))
        versions.sort(key=lambda item: (item.version or 0, item.created_at, item.name), reverse=True)
        inputs_dir = project_dir / "inputs"
        inputs = {
            path.name: path
            for path in inputs_dir.iterdir()
            if inputs_dir.exists() and path.is_file()
        } if inputs_dir.exists() else {}
        return ProjectDetail(summary=summary, versions=tuple(versions), inputs=inputs)

    def resolve_project(self, project: str | Path) -> Path:
        candidate = Path(project)
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
        candidate = self.projects_root / str(project)
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
        raise FileNotFoundError(f"project not found: {project}")

    def _summary(self, project_dir: Path) -> ProjectSummary:
        metadata = _read_json(project_dir / "metadata" / "project.json")
        latest = _read_json(project_dir / "metadata" / "latest.json")
        return ProjectSummary(
            project_id=str(metadata.get("project_id") or project_dir.name),
            title=str(metadata.get("title") or project_dir.name),
            created_date=str(metadata.get("created_date") or ""),
            path=project_dir.resolve(),
            latest_status=str(latest.get("status") or ""),
            latest_version=_optional_int(latest.get("version")),
            latest_mode=_latest_mode(latest),
        )


def _version_summary(version_dir: Path, *, mode: str, latest: dict[str, Any]) -> VersionSummary:
    manifest = read_manifest(version_dir) or {}
    created_at = str(manifest.get("created_at") or "")
    status = str(manifest.get("status") or status_from_dir(version_dir))
    version = _optional_int(manifest.get("version"))
    if version is None:
        version = version_number_from_dir(version_dir)
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    artifact_values = {}
    for key in ARTIFACT_KEYS:
        relative = files.get(key) if isinstance(files, dict) else None
        candidate = version_dir / relative if isinstance(relative, str) and relative else None
        artifact_values[key] = candidate if candidate is not None and candidate.exists() else None
    return VersionSummary(
        name=version_dir.name,
        version=version,
        status=status,
        mode=str(manifest.get("mode") or mode),
        created_at=created_at,
        path=version_dir.resolve(),
        is_latest=(
            latest.get("version_dir") == version_dir.name
            and latest.get("output_root") == version_dir.parent.name
        ),
        artifacts=ArtifactLinks(**artifact_values),
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _latest_mode(latest: dict[str, Any]) -> str:
    output_root = latest.get("output_root")
    if output_root == "dry_run_outputs":
        return "dry_run"
    if output_root == "outputs":
        return "real"
    return ""
