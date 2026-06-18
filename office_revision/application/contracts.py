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
class ModelConnectionStatus:
    role: str
    model: str
    ok: bool
    message: str
    elapsed_seconds: float
