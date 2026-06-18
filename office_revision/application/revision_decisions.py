from __future__ import annotations

import json
from pathlib import Path

from ..decision_flow import apply_decision_to_session
from .contracts import DecisionOutcome
from .project_queries import ProjectQueryService


class DecisionService:
    def __init__(self, projects: ProjectQueryService) -> None:
        self.projects = projects

    def apply_revision_decision(
        self,
        project: str | Path,
        decision: str,
        *,
        version_dir: str | Path | None = None,
        dry_run: bool | None = None,
    ) -> DecisionOutcome:
        project_dir = self.projects.resolve_project(project)
        if version_dir is not None:
            session_dir = Path(version_dir).resolve()
            if project_dir not in session_dir.parents:
                raise ValueError("version directory is outside the project")
            output_root = session_dir.parent
            result = apply_decision_to_session(
                output_root,
                session_dir,
                decision,
                prefer_session_command=True,
                update_latest=_is_latest(project_dir, session_dir),
            )
        else:
            output_root, session_dir = _resolve_latest_session(project_dir, dry_run=dry_run)
            result = apply_decision_to_session(
                output_root,
                session_dir,
                decision,
                update_latest=True,
            )
        return DecisionOutcome(
            status=result.status,
            version_path=result.session_dir,
            renamed=result.renamed,
            message=result.message,
        )


def _resolve_latest_session(project_dir: Path, *, dry_run: bool | None) -> tuple[Path, Path]:
    output_root = _select_output_root(project_dir, dry_run=dry_run)
    latest = _read_latest(project_dir)
    version_dir = latest.get("version_dir")
    if isinstance(version_dir, str) and latest.get("output_root") == output_root.name:
        candidate = output_root / version_dir
        if candidate.exists():
            return output_root, candidate
    raise FileNotFoundError(f"latest version not found under {output_root}")


def _select_output_root(project_dir: Path, *, dry_run: bool | None) -> Path:
    if dry_run is True:
        return project_dir / "dry_run_outputs"
    if dry_run is False:
        return project_dir / "outputs"
    latest = _read_latest(project_dir)
    output_root = latest.get("output_root")
    if output_root in {"outputs", "dry_run_outputs"}:
        return project_dir / str(output_root)
    if (project_dir / "outputs" / "latest").exists():
        return project_dir / "outputs"
    return project_dir / "dry_run_outputs"


def _is_latest(project_dir: Path, session_dir: Path) -> bool:
    latest = _read_latest(project_dir)
    return (
        latest.get("version_dir") == session_dir.name
        and latest.get("output_root") == session_dir.parent.name
    )


def _read_latest(project_dir: Path) -> dict:
    path = project_dir / "metadata" / "latest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
