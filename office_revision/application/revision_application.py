from __future__ import annotations

from pathlib import Path
from typing import Callable

from .contracts import (
    ContinueRevisionRequest,
    DeleteProjectResult,
    DecisionOutcome,
    ModelConnectionStatus,
    ProgressEvent,
    ProjectDetail,
    ProjectSummary,
    RevisionRunResult,
    StartProjectRequest,
)
from .continued_revisions import ContinuedRevisionService
from .model_connections import ModelConnectionService
from .project_deletions import ProjectDeletionService
from .new_projects import NewProjectService
from .project_queries import ProjectQueryService
from .revision_decisions import DecisionService


class RevisionApplication:
    def __init__(
        self,
        *,
        projects_root: str | Path = "projects",
        config_path: str | Path = "config/settings.env",
        project_service: ProjectQueryService | None = None,
        decision_service: DecisionService | None = None,
        connection_service: ModelConnectionService | None = None,
        new_project_service: NewProjectService | None = None,
        continued_revision_service: ContinuedRevisionService | None = None,
        deletion_service: ProjectDeletionService | None = None,
    ) -> None:
        self.project_queries = project_service or ProjectQueryService(projects_root)
        self.revision_decisions = decision_service or DecisionService(self.project_queries)
        self.model_connections = connection_service or ModelConnectionService(config_path)
        self.new_projects = new_project_service or NewProjectService(projects_root, config_path)
        self.continued_revisions = continued_revision_service or ContinuedRevisionService(projects_root, config_path)
        self.project_deletions = deletion_service or ProjectDeletionService(projects_root, self.project_queries)

    def start_new_project(
        self,
        request: StartProjectRequest,
        *,
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RevisionRunResult:
        return self.new_projects.start_new_project(request, on_progress=on_progress)

    def continue_existing_revision(
        self,
        request: ContinueRevisionRequest,
        *,
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> RevisionRunResult:
        return self.continued_revisions.continue_existing_revision(request, on_progress=on_progress)

    def list_projects(self) -> tuple[ProjectSummary, ...]:
        return self.project_queries.list_projects()

    def get_project_details(self, project: str | Path) -> ProjectDetail:
        return self.project_queries.get_project_details(project)

    def apply_revision_decision(
        self,
        project: str | Path,
        decision: str,
        *,
        version_dir: str | Path | None = None,
        dry_run: bool | None = None,
    ) -> DecisionOutcome:
        return self.revision_decisions.apply_revision_decision(
            project,
            decision,
            version_dir=version_dir,
            dry_run=dry_run,
        )

    def delete_project(
        self,
        project: str | Path,
        *,
        permanent: bool = False,
        deleted_at: str | None = None,
    ) -> DeleteProjectResult:
        return self.project_deletions.delete_project(
            project,
            permanent=permanent,
            deleted_at=deleted_at,
        )

    def check_model_connections(self) -> tuple[ModelConnectionStatus, ...]:
        return self.model_connections.check_model_connections()
