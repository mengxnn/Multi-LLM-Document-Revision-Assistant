from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ArtifactLinks:
    final_docx: Path | None = None
    final_md: Path | None = None
    revision_summary_docx: Path | None = None
    revision_summary_md: Path | None = None
    final_review_report_docx: Path | None = None
    final_review_report_md: Path | None = None
    run_log: Path | None = None


@dataclass(frozen=True)
class VersionSummary:
    name: str
    version: int | None
    status: str
    mode: str
    created_at: str
    path: Path
    is_latest: bool
    artifacts: ArtifactLinks = field(default_factory=ArtifactLinks)


@dataclass(frozen=True)
class ProjectSummary:
    project_id: str
    title: str
    created_date: str
    path: Path
    latest_status: str = ""
    latest_version: int | None = None
    latest_mode: str = ""


@dataclass(frozen=True)
class ProjectDetail:
    summary: ProjectSummary
    versions: tuple[VersionSummary, ...]
    inputs: dict[str, Path]


@dataclass(frozen=True)
class DecisionOutcome:
    status: str
    version_path: Path
    renamed: bool
    message: str


@dataclass(frozen=True)
class DeleteProjectResult:
    project_id: str
    deleted_path: Path
    trash_path: Path | None
    permanent: bool
    message: str


@dataclass(frozen=True)
class ModelConnectionStatus:
    role: str
    model: str
    ok: bool
    message: str
    elapsed_seconds: float


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    name: str
    provider: str
    api_key: str
    base_url: str
    model: str
    enable_search: bool = False
    model_family: str = "unknown"
    vision: bool = False
    function_calling: bool = False
    json_output: bool = False
    structured_output: bool = False
    timeout_seconds: int = 60
    max_retries: int = 1


@dataclass(frozen=True)
class ModelProfileRequest:
    profile_id: str
    name: str
    model: str
    provider: str = "openai-compatible"
    api_key: str = ""
    base_url: str = ""
    enable_search: bool = False
    model_family: str = "unknown"
    vision: bool = False
    function_calling: bool = False
    json_output: bool = False
    structured_output: bool = False
    timeout_seconds: int = 60
    max_retries: int = 1


@dataclass(frozen=True)
class ActiveModelProfile:
    role: str
    profile_id: str
    profile: ModelProfile


class RevisionApplicationError(Exception):
    def __init__(self, message: str, *, stage: str = "validation") -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class StartProjectRequest:
    requirements_path: str | Path | None = None
    requirements_text: str | None = None
    source_path: str | Path | None = None
    source_text: str | None = None
    meeting_notes_path: str | Path | None = None
    meeting_notes_text: str | None = None
    project_title: str | None = None
    project_title_language: str = "auto"
    cycles: int = 2
    dry_run: bool = False
    summary_mode: str = "rule"
    writer_model: str | None = None
    reviewer_model: str | None = None
    writer_prompt_path: str | Path = Path("config/writer_system_prompt.md")
    reviewer_prompt_path: str | Path = Path("config/reviewer_system_prompt.md")


@dataclass(frozen=True)
class ContinueRevisionRequest:
    project_id: str | Path
    base_version_path: str | Path | None = None
    feedback_path: str | Path | None = None
    feedback_text: str | None = None
    cycles: int = 2
    dry_run: bool = False
    summary_mode: str = "rule"
    writer_model: str | None = None
    reviewer_model: str | None = None
    writer_prompt_path: str | Path = Path("config/writer_system_prompt.md")
    reviewer_prompt_path: str | Path = Path("config/reviewer_system_prompt.md")


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    message: str
    cycle: int | None = None
    total_cycles: int | None = None
    elapsed_seconds: float | None = None

    def display_message(self) -> str:
        details: list[str] = []
        if self.cycle is not None and self.total_cycles is not None:
            details.append(f"{self.cycle}/{self.total_cycles}")
        if self.elapsed_seconds is not None:
            details.append(f"用时 {self.elapsed_seconds:.1f} 秒")
        if not details:
            return self.message
        return f"{self.message}（{'，'.join(details)}）"


@dataclass(frozen=True)
class RevisionRunResult:
    project_id: str
    project_path: Path
    version: int
    version_path: Path
    latest_path: Path | None
    status: str
    mode: str
    requested_cycles: int
    actual_cycles: int
    stopped_early: bool
    stop_reason: str | None
    artifacts: ArtifactLinks
    warnings: tuple[str, ...] = ()
