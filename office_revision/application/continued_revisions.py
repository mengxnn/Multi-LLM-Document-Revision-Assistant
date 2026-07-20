from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..autogen_runner import generate_llm_feedback_analysis, run_autogen_revision_loop
from ..continue_flow import (
    FEEDBACK_TEMPLATE,
    build_continue_requirements,
    dry_run_feedback_analysis,
    find_project_requirements_path,
    next_output_version,
    read_feedback,
    resolve_continue_target,
    resolve_previous_final_path,
    version_label_from_output_dir,
    versioned_output_dir,
)
from ..document_io import read_source_text
from ..dry_run import dry_run_reviewer, dry_run_writer
from ..ocr import read_pdf_text_with_ocr
from ..project_manager import write_latest_metadata, write_session_status
from ..project_paths import VersionLayout
from ..revision_outputs import build_summary_generation, prepare_output_dir, write_outputs
from ..workflow import RevisionRequest, run_revision_loop
from .contracts import (
    ArtifactLinks,
    ContinueRevisionRequest,
    ProgressEvent,
    RevisionApplicationError,
    RevisionRunResult,
)
from .model_profiles import load_active_role_settings


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(frozen=True)
class _SupplementalDocument:
    path: Path
    text: str
    used_ocr: bool


class ContinuedRevisionService:
    def __init__(
        self,
        projects_root: str | Path = "projects",
        config_path: str | Path = "config/settings.env",
        *,
        model_profiles_path: str | Path = "config/model_profiles.json",
        real_runner=None,
        feedback_analyzer=None,
        ocr_reader=None,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.config_path = Path(config_path)
        self.model_profiles_path = Path(model_profiles_path)
        self.real_runner = real_runner or run_autogen_revision_loop
        self.feedback_analyzer = feedback_analyzer or generate_llm_feedback_analysis
        self.ocr_reader = ocr_reader or read_pdf_text_with_ocr

    def continue_existing_revision(
        self,
        request: ContinueRevisionRequest,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> RevisionRunResult:
        self._validate_request(request)
        emit = lambda stage, message, cycle=None, total=None, elapsed_seconds=None: self._emit(
            on_progress, stage, message, cycle, total, elapsed_seconds
        )

        emit("loading_project", "读取已有项目")
        target = self._resolve_target(request)
        project_dir = target.project_dir
        output_root = target.output_root
        use_dry_run = request.dry_run or output_root.name == "dry_run_outputs"

        emit("reading_previous_draft", "读取上一版最终稿")
        previous_output_dir = target.previous_output_dir
        previous_final_path = resolve_previous_final_path(previous_output_dir)
        previous_text = self._read_previous_text(previous_final_path)
        if not previous_text:
            raise RevisionApplicationError(
                f"previous final draft is empty: {previous_output_dir}",
                stage="reading_previous_draft",
            )

        emit("reading_feedback", "读取用户反馈")
        feedback_path = project_dir / "inputs" / "feedback.md"
        feedback = self._read_feedback(request, feedback_path)
        self._write_feedback_snapshot(feedback_path, feedback)

        inputs_dir = project_dir / "inputs"
        original_requirements = self._read_original_requirements(
            inputs_dir,
            retain=request.retain_original_requirements,
        )
        original_source = self._read_optional_project_input(
            inputs_dir / "source.md",
            retain=request.retain_original_source,
        )
        original_meeting_notes = self._read_optional_project_input(
            inputs_dir / "meeting_notes.md",
            retain=request.retain_original_meeting_notes,
        )
        supplemental_documents = self._read_supplemental_documents(request)

        writer_settings, reviewer_settings = self._settings(request)

        emit("analyzing_feedback", "分析用户反馈")
        feedback_analysis = self._build_feedback_analysis(
            use_dry_run=use_dry_run,
            previous_text=previous_text,
            original_requirements=original_requirements,
            feedback=feedback,
            reviewer_settings=reviewer_settings,
        )
        requirements = build_continue_requirements(
            original_requirements=original_requirements,
            feedback=feedback,
            feedback_analysis=feedback_analysis,
        )
        source_context = self._build_source_context(
            previous_text,
            original_source=original_source,
            supplemental_documents=supplemental_documents,
        )
        workflow_request = RevisionRequest(
            source_text=source_context,
            requirements=requirements,
            meeting_notes=original_meeting_notes,
            cycles=request.cycles,
            title=project_dir.name,
            source_path=str(previous_final_path),
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
            if use_dry_run:
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
            raise RevisionApplicationError(str(exc), stage="running_revision") from exc

        emit("generating_summary", "生成修改说明汇总")
        summary_generation = build_summary_generation(
            result,
            mode=request.summary_mode,
            reviewer_settings=reviewer_settings,
        )

        current_version_number = next_output_version(output_root)
        current_version_dir = versioned_output_dir(
            output_root,
            datetime.now().strftime("%H%M%S"),
            "continue",
            current_version_number,
        )
        previous_version = version_label_from_output_dir(previous_output_dir)
        current_version = f"v{current_version_number}"
        source_reference = previous_final_path if previous_final_path.suffix.lower() == ".docx" else None
        extra_log = {
            "is_continue": True,
            "feedback_path": str(feedback_path),
            "feedback_analysis": feedback_analysis,
            "previous_output_dir": str(previous_output_dir),
            "previous_version": previous_version,
            "current_version": current_version,
            "context_selection": {
                "retain_original_requirements": request.retain_original_requirements,
                "retain_original_source": request.retain_original_source,
                "retain_original_meeting_notes": request.retain_original_meeting_notes,
                "original_requirements_chars": len(original_requirements),
                "original_source_chars": len(original_source),
                "original_meeting_notes_chars": len(original_meeting_notes),
                "supplemental_files": [
                    document.path.name for document in supplemental_documents
                ],
                "supplemental_chars": sum(
                    len(document.text) for document in supplemental_documents
                ),
            },
        }

        emit("generating_final_review", "生成最终人工复核报告")
        emit("saving_outputs", f"保存 {current_version} 和 latest")
        mode = "dry-run" if use_dry_run else "real"
        write_outputs(
            result,
            current_version_dir,
            source_path=source_reference,
            summary_generation=summary_generation,
            extra_log=extra_log,
            mode=mode,
            status="continue",
            parent_version=previous_version,
        )
        self._write_supplemental_snapshots(
            current_version_dir,
            supplemental_documents,
        )
        write_session_status(current_version_dir, status="continue", current_version=current_version)

        warnings: list[str] = []
        latest_dir = output_root / "latest"
        latest_path: Path | None = None
        if prepare_output_dir(latest_dir):
            write_outputs(
                result,
                latest_dir,
                source_path=source_reference,
                summary_generation=summary_generation,
                extra_log=extra_log,
                mode=mode,
                status="continue",
                parent_version=previous_version,
            )
            self._write_supplemental_snapshots(
                latest_dir,
                supplemental_documents,
            )
            write_session_status(latest_dir, status="continue", current_version=current_version)
            latest_path = latest_dir
        else:
            warnings.append("latest directory is locked and was not refreshed")
        write_latest_metadata(output_root, current_version_dir)

        layout = VersionLayout(current_version_dir)
        emit("completed", "运行完成")
        return RevisionRunResult(
            project_id=project_dir.name,
            project_path=project_dir,
            version=current_version_number,
            version_path=current_version_dir,
            latest_path=latest_path,
            status="continue",
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

    def _resolve_target(self, request: ContinueRevisionRequest):
        target_path = Path(request.base_version_path or request.project_id)
        if not target_path.exists():
            target_path = self.projects_root / target_path
        try:
            target = resolve_continue_target(target_path, dry_run=request.dry_run)
        except SystemExit as exc:
            raise RevisionApplicationError(str(exc), stage="loading_project") from exc
        requested_project = Path(request.project_id)
        if not requested_project.exists():
            requested_project = self.projects_root / requested_project
        if requested_project.resolve() != target.project_dir.resolve():
            raise RevisionApplicationError(
                "base version does not belong to the requested project",
                stage="loading_project",
            )
        return target

    @staticmethod
    def _read_previous_text(path: Path) -> str:
        if path.suffix.lower() == ".docx":
            return read_source_text(path).strip()
        return path.read_text(encoding="utf-8").strip()

    @staticmethod
    def _read_original_requirements(inputs_dir: Path, *, retain: bool) -> str:
        if not retain:
            return ""
        try:
            requirements_path = find_project_requirements_path(inputs_dir)
        except SystemExit as exc:
            raise RevisionApplicationError(str(exc), stage="reading_inputs") from exc
        value = requirements_path.read_text(encoding="utf-8").strip()
        if not value:
            raise RevisionApplicationError(
                f"requirements file is empty: {requirements_path}",
                stage="reading_inputs",
            )
        return value

    @staticmethod
    def _read_optional_project_input(path: Path, *, retain: bool) -> str:
        if not retain or not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def _read_supplemental_documents(
        self,
        request: ContinueRevisionRequest,
    ) -> tuple[_SupplementalDocument, ...]:
        documents = []
        for value in request.supplemental_paths:
            path = Path(value)
            if not path.exists():
                raise RevisionApplicationError(
                    f"supplemental file not found: {path}",
                    stage="reading_inputs",
                )
            used_ocr = False
            try:
                text = read_source_text(path).strip()
            except ValueError as exc:
                if request.enable_ocr and path.suffix.lower() == ".pdf":
                    try:
                        text = self.ocr_reader(path, request.ocr_language).strip()
                    except Exception as ocr_exc:
                        raise RevisionApplicationError(
                            f"supplemental file cannot be read with OCR: {ocr_exc}",
                            stage="reading_inputs",
                        ) from ocr_exc
                    used_ocr = True
                else:
                    raise RevisionApplicationError(
                        f"supplemental file cannot be read: {exc}",
                        stage="reading_inputs",
                    ) from exc
            documents.append(
                _SupplementalDocument(
                    path=path,
                    text=text,
                    used_ocr=used_ocr,
                )
            )
        return tuple(documents)

    @staticmethod
    def _build_source_context(
        previous_text: str,
        *,
        original_source: str,
        supplemental_documents: tuple[_SupplementalDocument, ...],
    ) -> str:
        if not original_source and not supplemental_documents:
            return previous_text
        sections = [("# 所选基准版本", previous_text)]
        if original_source:
            sections.append(("# 新建项目时的初稿", original_source))
        sections.extend(
            (f"# 本轮补充文件：{document.path.name}", document.text)
            for document in supplemental_documents
        )
        return "\n\n".join(f"{title}\n\n{text}" for title, text in sections)

    @staticmethod
    def _write_supplemental_snapshots(
        version_dir: Path,
        documents: tuple[_SupplementalDocument, ...],
    ) -> None:
        if not documents:
            return
        inputs_dir = version_dir / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        combined = []
        for index, document in enumerate(documents, start=1):
            target = inputs_dir / (
                f"supplemental_{index:02d}_{document.path.name}"
            )
            shutil.copy2(document.path, target)
            combined.append(f"## {document.path.name}\n\n{document.text}")
            if document.path.suffix.lower() == ".pdf":
                suffix = "_ocr.md" if document.used_ocr else "_extracted.md"
                (inputs_dir / f"{target.stem}{suffix}").write_text(
                    document.text,
                    encoding="utf-8",
                )
        (inputs_dir / "supplemental.md").write_text(
            "\n\n".join(combined),
            encoding="utf-8",
        )

    @staticmethod
    def _read_feedback(request: ContinueRevisionRequest, default_feedback_path: Path) -> str:
        if request.feedback_text is not None:
            text = request.feedback_text.strip()
            if not text:
                raise RevisionApplicationError(
                    "feedback is required and cannot be empty",
                    stage="reading_feedback",
                )
            if text == FEEDBACK_TEMPLATE.strip():
                raise RevisionApplicationError(
                    "feedback still contains the default feedback template",
                    stage="reading_feedback",
                )
            return text
        feedback_path = Path(request.feedback_path) if request.feedback_path else default_feedback_path
        try:
            return read_feedback(feedback_path)
        except SystemExit as exc:
            raise RevisionApplicationError(str(exc), stage="reading_feedback") from exc

    @staticmethod
    def _write_feedback_snapshot(feedback_path: Path, feedback: str) -> None:
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        feedback_path.write_text(feedback, encoding="utf-8")

    def _build_feedback_analysis(
        self,
        *,
        use_dry_run: bool,
        previous_text: str,
        original_requirements: str,
        feedback: str,
        reviewer_settings,
    ) -> str:
        if use_dry_run:
            return dry_run_feedback_analysis(feedback)
        try:
            return self.feedback_analyzer(
                previous_text=previous_text,
                original_requirements=original_requirements,
                feedback=feedback,
                reviewer_settings=reviewer_settings,
            )
        except Exception as exc:
            return "\n".join(
                [
                    "反馈分析模型调用失败，已回退为直接使用用户反馈。",
                    f"失败原因：{exc}",
                    "",
                    "给 writer 的整体重写指令：",
                    feedback.strip(),
                ]
            )

    @staticmethod
    def _emit(callback, stage, message, cycle=None, total=None, elapsed_seconds=None) -> None:
        if callback:
            callback(ProgressEvent(stage, message, cycle, total, elapsed_seconds))

    @staticmethod
    def _validate_request(request: ContinueRevisionRequest) -> None:
        if request.feedback_path is not None and request.feedback_text is not None and request.feedback_text.strip():
            raise RevisionApplicationError("feedback path and text cannot both be provided")
        if request.cycles <= 0:
            raise RevisionApplicationError("cycles must be greater than 0")
        if request.summary_mode not in {"rule", "llm"}:
            raise RevisionApplicationError("summary_mode must be rule or llm")
        for path in request.supplemental_paths:
            if Path(path).suffix.lower() not in {".docx", ".md", ".pdf", ".txt"}:
                raise RevisionApplicationError(
                    "supplemental file must be a .docx, .md, .pdf, or .txt file"
                )

    def _settings(self, request: ContinueRevisionRequest):
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
