from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..autogen_runner import generate_llm_project_title, run_autogen_revision_loop
from ..continue_flow import ensure_feedback_template
from ..document_io import read_source_text
from ..dry_run import dry_run_reviewer, dry_run_writer
from ..input_inspection import write_input_summaries
from ..project_manager import (
    create_project_context,
    fallback_project_title,
    finalize_project_title,
    write_latest_metadata,
    write_project_metadata,
    write_session_status,
)
from ..project_paths import VersionLayout
from ..revision_outputs import build_summary_generation, prepare_output_dir, write_outputs
from ..workflow import RevisionRequest, run_revision_loop
from .contracts import (
    ArtifactLinks,
    ProgressEvent,
    RevisionApplicationError,
    RevisionRunResult,
    StartProjectRequest,
)
from .model_profiles import load_active_role_settings


ProgressCallback = Callable[[ProgressEvent], None]


class NewProjectService:
    def __init__(
        self,
        projects_root: str | Path = "projects",
        config_path: str | Path = "config/settings.env",
        *,
        model_profiles_path: str | Path = "config/model_profiles.json",
        real_runner=None,
        title_generator=None,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.config_path = Path(config_path)
        self.model_profiles_path = Path(model_profiles_path)
        self.real_runner = real_runner or run_autogen_revision_loop
        self.title_generator = title_generator or generate_llm_project_title

    def start_new_project(
        self,
        request: StartProjectRequest,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> RevisionRunResult:
        self._validate_request(request)
        emit = lambda stage, message, cycle=None, total=None, elapsed_seconds=None: self._emit(
            on_progress, stage, message, cycle, total, elapsed_seconds
        )
        emit("reading_inputs", "读取输入文件")
        requirements, _ = self._read_value(
            request.requirements_path, request.requirements_text, "requirements", required=True
        )
        source_text, source_path = self._read_value(
            request.source_path, request.source_text, "source", required=False
        )
        meeting_notes, _ = self._read_value(
            request.meeting_notes_path, request.meeting_notes_text, "meeting notes", required=False
        )

        emit("creating_project", "创建项目并保存输入")
        initial_title = request.project_title or fallback_project_title(
            source_path, source_text, requirements
        )
        context = create_project_context(
            projects_root=self.projects_root,
            title=initial_title,
            created_date=datetime.now().strftime("%Y%m%d"),
        )
        self._write_snapshots(
            context.inputs_dir,
            requirements=requirements,
            requirements_path=Path(request.requirements_path) if request.requirements_path else None,
            source_text=source_text,
            source_path=source_path,
            meeting_notes=meeting_notes,
            meeting_notes_path=Path(request.meeting_notes_path) if request.meeting_notes_path else None,
        )
        write_project_metadata(context)
        ensure_feedback_template(context.inputs_dir)
        write_input_summaries(context.project_dir)

        writer_settings, reviewer_settings = self._settings(request)
        workflow_request = RevisionRequest(
            source_text=source_text,
            requirements=requirements,
            meeting_notes=meeting_notes,
            cycles=request.cycles,
            title=initial_title,
            source_path=str(source_path) if source_path else None,
            meeting_notes_path=str(request.meeting_notes_path) if request.meeting_notes_path else None,
        )

        def workflow_progress(
            stage: str,
            cycle: int,
            total: int,
            elapsed_seconds: float | None = None,
        ) -> None:
            role = "writer" if stage.startswith("writer_") else "reviewer"
            action = "生成" if role == "writer" else "审查"
            if stage.endswith("_completed"):
                message = f"{role} 第 {cycle} 轮{action}完成"
            else:
                message = f"{role} 第 {cycle} 轮{action}中"
            emit(stage, message, cycle, total, elapsed_seconds)

        try:
            if request.dry_run:
                result = run_revision_loop(
                    workflow_request,
                    writer=dry_run_writer,
                    reviewer=dry_run_reviewer,
                    on_progress=workflow_progress,
                )
            else:
                result = self.real_runner(
                    workflow_request,
                    writer_settings=writer_settings,
                    reviewer_settings=reviewer_settings,
                    writer_prompt_path=str(request.writer_prompt_path),
                    reviewer_prompt_path=str(request.reviewer_prompt_path),
                    on_progress=workflow_progress,
                )
        except Exception as exc:
            self._cleanup_failed_project(context)
            raise RevisionApplicationError(str(exc), stage="running_revision") from exc

        warnings: list[str] = []
        if not request.dry_run:
            emit("renaming_project", "生成最终建议项目名")
            try:
                final_title = self.title_generator(
                    source_text=result.final_text,
                    requirements=requirements,
                    meeting_notes=meeting_notes,
                    reviewer_settings=reviewer_settings,
                    language=request.project_title_language,
                ).strip()
                if final_title:
                    context, rename_result = finalize_project_title(context, final_title)
                    if rename_result.status == "failed":
                        warnings.append(f"project rename failed: {rename_result.reason}")
            except Exception as exc:
                warnings.append(f"project title generation failed: {exc}")

        emit("generating_summary", "生成修改说明汇总")
        summary = build_summary_generation(
            result, mode=request.summary_mode, reviewer_settings=reviewer_settings
        )
        output_root = context.dry_run_outputs_dir if request.dry_run else context.outputs_dir
        version_dir = output_root / f"{datetime.now().strftime('%H%M%S')}-pending-v1"
        emit("generating_final_review", "生成最终人工复核报告")
        emit("saving_outputs", "保存 v1 和 latest")
        mode = "dry-run" if request.dry_run else "real"
        write_outputs(
            result,
            version_dir,
            source_path=source_path,
            summary_generation=summary,
            mode=mode,
            status="pending",
        )
        write_session_status(version_dir, current_version="v1")

        latest_dir = output_root / "latest"
        latest_path: Path | None = None
        if prepare_output_dir(latest_dir):
            write_outputs(
                result,
                latest_dir,
                source_path=source_path,
                summary_generation=summary,
                mode=mode,
                status="pending",
            )
            write_session_status(latest_dir, current_version="v1")
            latest_path = latest_dir
        else:
            warnings.append("latest directory is locked and was not refreshed")
        write_latest_metadata(output_root, version_dir)

        layout = VersionLayout(version_dir)
        emit("completed", "运行完成")
        return RevisionRunResult(
            project_id=context.project_dir.name,
            project_path=context.project_dir,
            version=1,
            version_path=version_dir,
            latest_path=latest_path,
            status="pending",
            mode=mode,
            requested_cycles=request.cycles,
            actual_cycles=len(result.passes),
            stopped_early=result.stopped_early,
            stop_reason=result.stop_reason,
            artifacts=ArtifactLinks(
                final_docx=layout.final_docx if layout.final_docx.exists() else None,
                final_md=layout.final_md if layout.final_md.exists() else None,
                revision_summary_docx=layout.revision_summary_docx,
                revision_summary_md=layout.revision_summary_md,
                final_review_report_docx=layout.final_review_report_docx,
                final_review_report_md=layout.final_review_report_md,
                run_log=layout.run_log,
            ),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _emit(callback, stage, message, cycle=None, total=None, elapsed_seconds=None) -> None:
        if callback:
            callback(ProgressEvent(stage, message, cycle, total, elapsed_seconds))

    @staticmethod
    def _validate_request(request: StartProjectRequest) -> None:
        for label, path, text in (
            ("requirements", request.requirements_path, request.requirements_text),
            ("source", request.source_path, request.source_text),
            ("meeting notes", request.meeting_notes_path, request.meeting_notes_text),
        ):
            if path is not None and text is not None and text.strip():
                raise RevisionApplicationError(f"{label} path and text cannot both be provided")
        if request.cycles <= 0:
            raise RevisionApplicationError("cycles must be greater than 0")
        if request.summary_mode not in {"rule", "llm"}:
            raise RevisionApplicationError("summary_mode must be rule or llm")
        if request.project_title_language not in {"auto", "zh", "en"}:
            raise RevisionApplicationError("project_title_language must be auto, zh, or en")
        if request.source_path and Path(request.source_path).suffix.lower() not in {".docx", ".md", ".pdf", ".txt"}:
            raise RevisionApplicationError("source must be a .docx, .md, .pdf, or .txt file")

    @staticmethod
    def _read_value(path, text, label, *, required):
        if path is not None:
            path = Path(path)
            if not path.exists():
                raise RevisionApplicationError(f"{label} file not found: {path}")
            try:
                value = read_source_text(path).strip()
            except ValueError as exc:
                raise RevisionApplicationError(f"{label} file cannot be read: {exc}") from exc
            resolved_path = path
        else:
            value = (text or "").strip()
            resolved_path = None
        if required and not value:
            raise RevisionApplicationError(f"{label} is required and cannot be empty")
        return value, resolved_path

    @staticmethod
    def _write_snapshots(
        inputs_dir,
        *,
        requirements,
        requirements_path,
        source_text,
        source_path,
        meeting_notes,
        meeting_notes_path,
    ):
        inputs_dir.mkdir(parents=True, exist_ok=True)
        (inputs_dir / "requirements.md").write_text(requirements, encoding="utf-8")
        if requirements_path and requirements_path.suffix.lower() == ".pdf":
            shutil.copy2(requirements_path, inputs_dir / "requirements.pdf")
        if source_text:
            if source_path:
                shutil.copy2(source_path, inputs_dir / f"source{source_path.suffix.lower()}")
                if source_path.suffix.lower() == ".pdf":
                    (inputs_dir / "source_extracted.md").write_text(source_text, encoding="utf-8")
            else:
                (inputs_dir / "source.md").write_text(source_text, encoding="utf-8")
        if meeting_notes:
            (inputs_dir / "meeting_notes.md").write_text(meeting_notes, encoding="utf-8")
            if meeting_notes_path and meeting_notes_path.suffix.lower() == ".pdf":
                shutil.copy2(meeting_notes_path, inputs_dir / "meeting_notes.pdf")

    @staticmethod
    def _cleanup_failed_project(context) -> None:
        if not context.project_dir.exists():
            return
        if _has_version_outputs(context.outputs_dir) or _has_version_outputs(context.dry_run_outputs_dir):
            return
        shutil.rmtree(context.project_dir, ignore_errors=True)

    def _settings(self, request):
        writer = load_active_role_settings(
            config_path=self.config_path,
            profile_path=self.model_profiles_path,
            role="WRITER",
            default_model=request.writer_model or "gpt-4.1",
        )
        reviewer = load_active_role_settings(
            config_path=self.config_path,
            profile_path=self.model_profiles_path,
            role="REVIEWER",
            default_model=request.reviewer_model or "gpt-4.1",
        )
        if request.writer_model:
            writer = replace(writer, model=request.writer_model)
        if request.reviewer_model:
            reviewer = replace(reviewer, model=request.reviewer_model)
        return writer, reviewer


def _has_version_outputs(output_root: Path) -> bool:
    if not output_root.exists():
        return False
    return any(path.is_dir() and path.name != "latest" for path in output_root.iterdir())
