from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ARTIFACT_FALLBACKS = {
    "final_docx": ("final/final.docx", "final.docx"),
    "final_md": ("final/final.md", "final.md"),
    "review_md": ("reviews/review.md", "review.md"),
    "changes_summary_docx": (
        "changes_summary/changes_summary.docx",
        "summaries/changes_summary.docx",
        "changes_summary.docx",
    ),
    "changes_summary_md": (
        "changes_summary/changes_summary.md",
        "summaries/changes_summary.md",
        "changes_summary.md",
    ),
    "run_log": ("metadata/run_log.json", "run_log.json"),
    "session_status": ("metadata/session_status.json", "session_status.json"),
}


@dataclass(frozen=True)
class VersionLayout:
    root: Path

    @property
    def final_dir(self) -> Path:
        return self.root / "final"

    @property
    def reviews_dir(self) -> Path:
        return self.root / "reviews"

    @property
    def changes_summary_dir(self) -> Path:
        return self.root / "changes_summary"

    @property
    def summaries_dir(self) -> Path:
        return self.changes_summary_dir

    @property
    def metadata_dir(self) -> Path:
        return self.root / "metadata"

    @property
    def final_docx(self) -> Path:
        return self.final_dir / "final.docx"

    @property
    def final_md(self) -> Path:
        return self.final_dir / "final.md"

    @property
    def review_md(self) -> Path:
        return self.reviews_dir / "review.md"

    @property
    def summary_docx(self) -> Path:
        return self.summaries_dir / "changes_summary.docx"

    @property
    def summary_md(self) -> Path:
        return self.summaries_dir / "changes_summary.md"

    @property
    def run_log(self) -> Path:
        return self.metadata_dir / "run_log.json"

    @property
    def session_status(self) -> Path:
        return self.metadata_dir / "session_status.json"

    @property
    def manifest(self) -> Path:
        return self.metadata_dir / "manifest.json"

    @property
    def compat_final_docx(self) -> Path:
        return self.root / "final.docx"

    @property
    def compat_final_md(self) -> Path:
        return self.root / "final.md"

    @property
    def compat_review_md(self) -> Path:
        return self.root / "review.md"

    @property
    def compat_summary_docx(self) -> Path:
        return self.root / "changes_summary.docx"

    @property
    def compat_summary_md(self) -> Path:
        return self.root / "changes_summary.md"

    @property
    def compat_run_log(self) -> Path:
        return self.root / "run_log.json"

    @property
    def compat_session_status(self) -> Path:
        return self.root / "session_status.json"

    def ensure_dirs(self) -> None:
        self.final_dir.mkdir(parents=True, exist_ok=True)
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        self.changes_summary_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)


def relative_to_version(path: Path, version_dir: Path) -> str:
    return path.relative_to(version_dir).as_posix()


def version_number_from_dir(version_dir: str | Path) -> int | None:
    match = re.search(r"-v(\d+)$", Path(version_dir).name)
    return int(match.group(1)) if match else None


def status_from_dir(version_dir: str | Path) -> str:
    match = re.search(r"-(pending|accept|continue|abandon)-v\d+$", Path(version_dir).name)
    return match.group(1) if match else "pending"


def source_type_from_path(source_path: Path | None) -> str:
    if source_path is None:
        return "none"
    suffix = source_path.suffix.lower().lstrip(".")
    return suffix or "unknown"


def structured_manifest(
    layout: VersionLayout,
    *,
    project_name: str,
    version: int | None,
    status: str | None,
    mode: str,
    source_type: str,
    round_review_paths: list[Path],
    parent_version: str | None = None,
) -> dict[str, Any]:
    round_reviews = [relative_to_version(path, layout.root) for path in round_review_paths]
    final_review = round_reviews[-1] if round_reviews else relative_to_version(layout.compat_review_md, layout.root)
    files = {
        "final_docx": relative_to_version(layout.final_docx, layout.root),
        "final_md": relative_to_version(layout.final_md, layout.root),
        "review_md": final_review,
        "round_reviews": round_reviews,
        "changes_summary_docx": relative_to_version(layout.summary_docx, layout.root),
        "changes_summary_md": relative_to_version(layout.summary_md, layout.root),
        "run_log": relative_to_version(layout.run_log, layout.root),
        "session_status": relative_to_version(layout.session_status, layout.root),
    }
    return {
        "schema_version": 1,
        "project_name": project_name,
        "version": version,
        "status": status or status_from_dir(layout.root),
        "version_dir": layout.root.name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "parent_version": parent_version,
        "mode": mode,
        "source_type": source_type,
        "files": files,
    }


def write_manifest(layout: VersionLayout, manifest: dict[str, Any]) -> None:
    layout.metadata_dir.mkdir(parents=True, exist_ok=True)
    layout.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def update_manifest_identity(version_dir: str | Path, *, status: str | None = None) -> None:
    layout = VersionLayout(Path(version_dir))
    manifest = read_manifest(layout.root)
    if manifest is None:
        return
    manifest["version_dir"] = layout.root.name
    manifest["version"] = version_number_from_dir(layout.root)
    manifest["status"] = status or status_from_dir(layout.root)
    write_manifest(layout, manifest)


def read_manifest(version_dir: str | Path) -> dict[str, Any] | None:
    manifest_path = VersionLayout(Path(version_dir)).manifest
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def resolve_artifact(version_dir: str | Path, artifact_key: str) -> Path:
    root = Path(version_dir)
    manifest = read_manifest(root)
    if manifest:
        relative = manifest.get("files", {}).get(artifact_key)
        if isinstance(relative, str):
            candidate = root / relative
            if candidate.exists():
                return candidate

    for relative in ARTIFACT_FALLBACKS.get(artifact_key, ()):
        candidate = root / relative
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"{artifact_key} not found under {root}")
