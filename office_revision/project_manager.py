from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .project_paths import VersionLayout, status_from_dir, version_number_from_dir


WINDOWS_FORBIDDEN_CHARS = r'<>:"/\|?*'
DOCUMENT_TYPE_TITLES = ("调研报告", "项目实施方案", "实施方案", "申请书", "论文", "汇报材料", "工作方案")


@dataclass(frozen=True)
class ProjectContext:
    project_dir: Path
    title: str
    created_date: str

    @property
    def inputs_dir(self) -> Path:
        return self.project_dir / "inputs"

    @property
    def outputs_dir(self) -> Path:
        return self.project_dir / "outputs"

    @property
    def dry_run_outputs_dir(self) -> Path:
        return self.project_dir / "dry_run_outputs"


def sanitize_project_title(title: str, *, max_length: int = 30) -> str:
    cleaned = title.strip()
    for char in WINDOWS_FORBIDDEN_CHARS:
        cleaned = cleaned.replace(char, "")
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._ ")
    if not cleaned:
        return "document"
    return cleaned[:max_length].rstrip("._ ")


def make_project_directory_name(title: str, date_text: str) -> str:
    return f"{sanitize_project_title(title)}_{date_text}"


def fallback_project_title(
    source_path: Path | None,
    source_text: str,
    requirements: str,
) -> str:
    explicit_title = _explicit_requirement_title(requirements)
    if explicit_title:
        return sanitize_project_title(explicit_title)

    if source_path is not None and source_path.stem:
        return sanitize_project_title(source_path.stem)

    heading = _first_markdown_heading(source_text) or _first_markdown_heading(requirements)
    if heading:
        return sanitize_project_title(heading)

    document_type = _document_type_title(requirements)
    if document_type:
        return sanitize_project_title(document_type)

    compact = re.sub(r"\s+", "", requirements)
    return sanitize_project_title(compact[:18] or "document")


def create_project_context(
    *,
    projects_root: str | Path,
    title: str,
    created_date: str,
) -> ProjectContext:
    root = Path(projects_root)
    project_dir = _unique_project_dir(root, make_project_directory_name(title, created_date))
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "inputs").mkdir(exist_ok=True)
    (project_dir / "outputs").mkdir(exist_ok=True)
    (project_dir / "dry_run_outputs").mkdir(exist_ok=True)
    return ProjectContext(project_dir=project_dir, title=sanitize_project_title(title), created_date=created_date)


def snapshot_project_inputs(
    context: ProjectContext,
    *,
    source_path: Path | None,
    requirements_path: Path,
    meeting_notes_path: Path | None,
) -> None:
    context.inputs_dir.mkdir(parents=True, exist_ok=True)
    if source_path is not None and source_path.exists():
        shutil.copy2(source_path, context.inputs_dir / source_path.name)
    if requirements_path.exists():
        shutil.copy2(requirements_path, context.inputs_dir / requirements_path.name)
    if meeting_notes_path is not None and meeting_notes_path.exists():
        shutil.copy2(meeting_notes_path, context.inputs_dir / meeting_notes_path.name)
    write_project_metadata(context)


def write_project_metadata(context: ProjectContext) -> None:
    context.project_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "project_id": context.project_dir.name,
            "title": context.title,
            "created_date": context.created_date,
        },
        ensure_ascii=False,
        indent=2,
    )
    (context.project_dir / "project.json").write_text(payload, encoding="utf-8")
    metadata_dir = context.project_dir / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    (metadata_dir / "project.json").write_text(payload, encoding="utf-8")


def write_final_suggested_project_title(context: ProjectContext, title: str) -> None:
    suggested_title = sanitize_project_title(title)
    metadata_dir = context.project_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    for path in (context.project_dir / "project.json", metadata_dir / "project.json"):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {
                "project_id": context.project_dir.name,
                "title": context.title,
                "created_date": context.created_date,
            }
        data.setdefault("project_id", context.project_dir.name)
        data.setdefault("title", context.title)
        data.setdefault("created_date", context.created_date)
        data["final_suggested_title"] = suggested_title
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_session_status(output_dir: str | Path, *, status: str = "pending", current_version: str = "latest") -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "status": status,
            "current_version": current_version,
        },
        ensure_ascii=False,
        indent=2,
    )
    (target / "session_status.json").write_text(payload, encoding="utf-8")
    layout = VersionLayout(target)
    layout.metadata_dir.mkdir(parents=True, exist_ok=True)
    layout.session_status.write_text(payload, encoding="utf-8")


def write_latest_session(output_root: str | Path, session_dir: Path) -> None:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "latest_session.json").write_text(
        json.dumps({"session_dir": str(session_dir)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metadata_dir = root.parent / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "latest.json").write_text(
        json.dumps(
            {
                "session_dir": str(session_dir),
                "version_dir": session_dir.name,
                "version": version_number_from_dir(session_dir),
                "status": status_from_dir(session_dir),
                "output_root": root.name,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _first_markdown_heading(text: str) -> str | None:
    for line in text.splitlines():
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return None


def _explicit_requirement_title(requirements: str) -> str | None:
    patterns = (
        r"(?:^|\n|[，,。；;])\s*(?:题目|标题)\s*[:：]\s*(.+)",
        r"(?:^|\n|[，,。；;])\s*(?:题目|标题)\s*(?:为|是)\s*[:：]?\s*(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, requirements)
        if match:
            return _clean_extracted_title(match.group(1))
    return None


def _clean_extracted_title(text: str) -> str:
    title = text.strip().strip("「」《》“”\"'")
    title = re.split(r"[\n。；;，,]", title, maxsplit=1)[0]
    return title.strip().strip("「」《》“”\"'")


def _document_type_title(requirements: str) -> str | None:
    for document_type in DOCUMENT_TYPE_TITLES:
        if document_type in requirements:
            return document_type
    return None


def _unique_project_dir(root: Path, base_name: str) -> Path:
    candidate = root / base_name
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = root / f"{base_name}_{index:02d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"too many projects with the same name under {root}")
