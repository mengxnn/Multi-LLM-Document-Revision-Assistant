from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..autogen_runner import generate_llm_project_title, run_autogen_revision_loop
from ..continue_flow import ensure_feedback_template
from ..document_io import read_source_text
from ..dry_run import dry_run_reviewer, dry_run_writer
from ..input_inspection import write_input_summaries
from ..ocr import read_pdf_text_with_ocr
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


@dataclass(frozen=True)
class _InputDocument:
    path: Path
    text: str
    used_ocr: bool


@dataclass(frozen=True)
class _InputCollection:
    text: str
    manual_text: str
    documents: tuple[_InputDocument, ...]

    @property
    def reference_path(self) -> Path | None:
        if self.manual_text or len(self.documents) != 1:
            return None
        return self.documents[0].path


class NewProjectService:
    def __init__(
        self,
        projects_root: str | Path = "projects",
        config_path: str | Path = "config/settings.env",
        *,
        model_profiles_path: str | Path = "config/model_profiles.json",
        real_runner=None,
        title_generator=None,
        ocr_reader=None,
    ) -> None:
        self.projects_root = Path(projects_root)
        self.config_path = Path(config_path)
        self.model_profiles_path = Path(model_profiles_path)
        self.real_runner = real_runner or run_autogen_revision_loop
        self.title_generator = title_generator or generate_llm_project_title
        self.ocr_reader = ocr_reader or read_pdf_text_with_ocr

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
        requirements_input = self._read_collection(
            request.requirements_path,
            request.requirements_paths,
            request.requirements_text,
            "requirements",
            required=True,
            enable_ocr=request.enable_ocr,
            ocr_language=request.ocr_language,
        )
        source_input = self._read_collection(
            request.source_path,
            request.source_paths,
            request.source_text,
            "source",
            required=False,
            enable_ocr=request.enable_ocr,
            ocr_language=request.ocr_language,
        )
        meeting_notes_input = self._read_collection(
            request.meeting_notes_path,
            request.meeting_notes_paths,
            request.meeting_notes_text,
            "meeting notes",
            required=False,
            enable_ocr=request.enable_ocr,
            ocr_language=request.ocr_language,
        )
        requirements = requirements_input.text
        source_text = source_input.text
        source_path = source_input.reference_path
        meeting_notes = meeting_notes_input.text

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
            requirements=requirements_input,
            source=source_input,
            meeting_notes=meeting_notes_input,
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
            meeting_notes_path=(
                str(meeting_notes_input.reference_path)
                if meeting_notes_input.reference_path
                else None
            ),
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

    def _validate_request(self, request: StartProjectRequest) -> None:
        if request.cycles <= 0:
            raise RevisionApplicationError("cycles must be greater than 0")
        if request.summary_mode not in {"rule", "llm"}:
            raise RevisionApplicationError("summary_mode must be rule or llm")
        if request.project_title_language not in {"auto", "zh", "en"}:
            raise RevisionApplicationError("project_title_language must be auto, zh, or en")
        for label, paths in (
            (
                "requirements",
                self._request_paths(
                    request.requirements_path,
                    request.requirements_paths,
                ),
            ),
            ("source", self._request_paths(request.source_path, request.source_paths)),
            (
                "meeting notes",
                self._request_paths(request.meeting_notes_path, request.meeting_notes_paths),
            ),
        ):
            for path in paths:
                if path.suffix.lower() not in {".docx", ".md", ".pdf", ".txt"}:
                    raise RevisionApplicationError(
                        f"{label} must be a .docx, .md, .pdf, or .txt file"
                    )

    def _read_collection(
        self,
        path,
        paths,
        text,
        label,
        *,
        required,
        enable_ocr=False,
        ocr_language="chi_sim+eng",
    ) -> _InputCollection:
        manual_text = (text or "").strip()
        documents = tuple(
            self._read_document(
                item,
                label=label,
                enable_ocr=enable_ocr,
                ocr_language=ocr_language,
            )
            for item in self._request_paths(path, paths)
        )
        sections: list[tuple[str, str]] = []
        if manual_text:
            sections.append(("手动输入", manual_text))
        sections.extend((document.path.name, document.text) for document in documents)
        if not sections:
            combined = ""
        elif len(sections) == 1:
            combined = sections[0][1]
        else:
            combined = "\n\n".join(
                f"## {name}\n\n{content}"
                for name, content in sections
            )
        if required and not combined:
            raise RevisionApplicationError(f"{label} is required and cannot be empty")
        return _InputCollection(
            text=combined,
            manual_text=manual_text,
            documents=documents,
        )

    def _read_document(
        self,
        path,
        *,
        label,
        enable_ocr,
        ocr_language,
    ) -> _InputDocument:
        path = Path(path)
        if not path.exists():
            raise RevisionApplicationError(f"{label} file not found: {path}")
        used_ocr = False
        try:
            value = read_source_text(path).strip()
        except ValueError as exc:
            if enable_ocr and path.suffix.lower() == ".pdf":
                try:
                    value = self.ocr_reader(path, ocr_language).strip()
                except Exception as ocr_exc:
                    raise RevisionApplicationError(
                        f"{label} file cannot be read with OCR: {ocr_exc}"
                    ) from ocr_exc
                used_ocr = True
            else:
                raise RevisionApplicationError(
                    f"{label} file cannot be read: {exc}"
                ) from exc
        return _InputDocument(path=path, text=value, used_ocr=used_ocr)

    @staticmethod
    def _request_paths(path, paths) -> tuple[Path, ...]:
        values = ([path] if path is not None else []) + list(paths or ())
        unique: list[Path] = []
        seen: set[str] = set()
        for value in values:
            candidate = Path(value)
            key = str(candidate.resolve()).lower()
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return tuple(unique)

    @staticmethod
    def _write_snapshots(
        inputs_dir,
        *,
        requirements,
        source,
        meeting_notes,
    ):
        inputs_dir.mkdir(parents=True, exist_ok=True)
        NewProjectService._write_input_collection(inputs_dir, "requirements", requirements)
        NewProjectService._write_input_collection(inputs_dir, "source", source)
        NewProjectService._write_input_collection(inputs_dir, "meeting_notes", meeting_notes)

    @staticmethod
    def _write_input_collection(
        inputs_dir: Path,
        role: str,
        collection: _InputCollection,
    ) -> None:
        if not collection.text:
            return
        canonical = inputs_dir / f"{role}.md"
        canonical.write_text(collection.text, encoding="utf-8")
        legacy_layout = not collection.manual_text and len(collection.documents) == 1
        for index, document in enumerate(collection.documents, start=1):
            if legacy_layout:
                original = inputs_dir / f"{role}{document.path.suffix.lower()}"
            else:
                original = inputs_dir / (
                    f"{role}_{index:02d}_{Path(document.path.name).name}"
                )
            if original != canonical:
                shutil.copy2(document.path, original)
            if document.path.suffix.lower() != ".pdf":
                continue
            if legacy_layout:
                if role == "requirements" and not document.used_ocr:
                    continue
                extracted_name = (
                    f"{role}_ocr.md" if document.used_ocr else f"{role}_extracted.md"
                )
            else:
                suffix = "_ocr.md" if document.used_ocr else "_extracted.md"
                extracted_name = f"{original.stem}{suffix}"
            (inputs_dir / extracted_name).write_text(document.text, encoding="utf-8")

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
