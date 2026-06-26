from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .contracts import DeleteProjectResult, RevisionApplicationError
from .project_queries import ProjectQueryService


class ProjectDeletionService:
    def __init__(
        self,
        projects_root: str | Path = "projects",
        project_queries: ProjectQueryService | None = None,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.project_queries = project_queries or ProjectQueryService(projects_root)

    def delete_project(
        self,
        project: str | Path,
        *,
        permanent: bool = False,
        deleted_at: str | None = None,
    ) -> DeleteProjectResult:
        project_dir = self._resolve_safe_project(project)
        project_id = project_dir.name

        if permanent:
            try:
                shutil.rmtree(project_dir)
            except OSError as exc:
                raise RevisionApplicationError(
                    f"failed to permanently delete project: {exc}",
                    stage="deleting_project",
                ) from exc
            return DeleteProjectResult(
                project_id=project_id,
                deleted_path=project_dir,
                trash_path=None,
                permanent=True,
                message=f"Project permanently deleted: {project_id}",
            )

        trash_root = self.projects_root.resolve() / ".trash"
        trash_root.mkdir(parents=True, exist_ok=True)
        timestamp = deleted_at or datetime.now().strftime("%Y%m%d_%H%M%S")
        trash_path = self._unique_trash_path(trash_root / f"{project_id}_deleted_{timestamp}")
        try:
            project_dir.rename(trash_path)
        except OSError as exc:
            raise RevisionApplicationError(
                f"failed to move project to trash: {exc}",
                stage="deleting_project",
            ) from exc
        return DeleteProjectResult(
            project_id=project_id,
            deleted_path=project_dir,
            trash_path=trash_path,
            permanent=False,
            message=f"Project moved to trash: {trash_path}",
        )

    def _resolve_safe_project(self, project: str | Path) -> Path:
        try:
            project_dir = self.project_queries.resolve_project(project).resolve()
        except FileNotFoundError as exc:
            raise RevisionApplicationError(str(exc), stage="deleting_project") from exc

        root = self.projects_root.resolve()
        if project_dir == root:
            raise RevisionApplicationError(
                "refusing to delete the projects root directory",
                stage="deleting_project",
            )
        try:
            project_dir.relative_to(root)
        except ValueError as exc:
            raise RevisionApplicationError(
                f"refusing to delete a project outside projects root: {project_dir}",
                stage="deleting_project",
            ) from exc
        if any(part == ".trash" for part in project_dir.relative_to(root).parts):
            raise RevisionApplicationError(
                "refusing to delete a project already inside .trash",
                stage="deleting_project",
            )
        return project_dir

    @staticmethod
    def _unique_trash_path(base: Path) -> Path:
        if not base.exists():
            return base
        for index in range(2, 1000):
            candidate = base.parent / f"{base.name}_{index:02d}"
            if not candidate.exists():
                return candidate
        raise RevisionApplicationError(
            f"too many deleted projects with the same name under {base.parent}",
            stage="deleting_project",
        )
