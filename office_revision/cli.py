from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .config import load_env_file, load_role_settings, merged_env_values
from .continue_flow import (
    build_continue_requirements,
    dry_run_feedback_analysis,
    ensure_feedback_template,
    find_latest_output_dir,
    find_project_requirements_path,
    read_feedback,
    next_output_version,
    resolve_previous_final_path,
    resolve_continue_target,
    version_label_from_output_dir,
    versioned_output_dir,
)
from .decision_flow import apply_decision_to_session, apply_session_decision, read_interactive_decision
from .document_io import read_source_text, write_final_docx
from .dry_run import dry_run_reviewer, dry_run_writer
from .project_manager import (
    create_project_context,
    fallback_project_title,
    finalize_project_title,
    snapshot_project_inputs,
    write_latest_metadata,
    write_session_status,
)
from .project_paths import (
    VersionLayout,
    source_type_from_path,
    structured_manifest,
    version_number_from_dir,
    write_manifest,
)
from .autogen_runner import (
    generate_llm_changes_summary,
    generate_llm_feedback_analysis,
    generate_llm_project_title,
)
from .summary import (
    SummaryGeneration,
    build_changes_summary,
    has_required_summary_headings,
    write_final_review_report,
    write_revision_summary,
)
from .workflow import RevisionRequest, RevisionResult, run_revision_loop


DEFAULT_INPUT_DIR = Path("inputs")
SOURCE_CANDIDATES = ("source.docx", "source.md", "source.txt")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a multi-cycle office document revision workflow."
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Optional source document path. If omitted, inputs/source.docx/.md/.txt are tried.",
    )
    parser.add_argument(
        "--requirements",
        default=None,
        help="Path to the revision requirements text/Markdown file.",
    )
    parser.add_argument(
        "--meeting-notes",
        default=None,
        help="Optional meeting notes text/Markdown file. Empty files are ignored.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for final.md, review.md, and run_log.json.",
    )
    parser.add_argument(
        "--projects-root",
        default="projects",
        help="Root directory for managed project folders when --output-dir is not set.",
    )
    parser.add_argument(
        "--continue-project",
        default=None,
        help="Continue revising an existing projects/<project> directory using inputs/feedback.md.",
    )
    parser.add_argument(
        "--review-project",
        default=None,
        help="Choose accept, abandon, or skip for the latest pending result in a project directory.",
    )
    parser.add_argument(
        "--decision",
        choices=("accept", "continue", "abandon", "skip"),
        default=None,
        help="Decision used with --review-project. If omitted, an interactive prompt is shown.",
    )
    parser.add_argument(
        "--project-title",
        default=None,
        help="Optional project title used for projects/<title>_<YYYYMMDD>.",
    )
    parser.add_argument(
        "--project-title-language",
        choices=("auto", "zh", "en"),
        default="auto",
        help="Preferred language for future LLM-generated project titles.",
    )
    parser.add_argument("--cycles", type=int, default=2, help="Writer-review cycles to run.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use deterministic local agents without calling external models.",
    )
    parser.add_argument("--writer-model", help="Override model name for writer agent.")
    parser.add_argument("--reviewer-model", help="Override model name for reviewer agent.")
    parser.add_argument(
        "--writer-prompt",
        default="config/writer_system_prompt.md",
        help="Path to the writer system prompt.",
    )
    parser.add_argument(
        "--reviewer-prompt",
        default="config/reviewer_system_prompt.md",
        help="Path to the reviewer system prompt.",
    )
    parser.add_argument(
        "--config",
        default="config/settings.env",
        help="Path to persistent API settings. Used only for real model runs.",
    )
    parser.add_argument(
        "--check-connections",
        action="store_true",
        help="Test writer and reviewer API settings, then exit.",
    )
    parser.add_argument(
        "--summary-mode",
        choices=("rule", "llm"),
        default="rule",
        help="How to generate reviews/revision_summary.md/docx. rule is deterministic; llm uses reviewer model with rule fallback.",
    )
    return parser


def result_to_dict(
    result: RevisionResult,
    summary_generation: SummaryGeneration | None = None,
    extra: dict | None = None,
) -> dict:
    summary_generation = summary_generation or SummaryGeneration(text=build_changes_summary(result))
    data = {
        "title": result.request.title,
        "cycles": result.request.cycles,
        "actual_cycles": len(result.passes),
        "stopped_early": result.stopped_early,
        "stop_reason": result.stop_reason,
        "source_path": result.request.source_path,
        "meeting_notes_path": result.request.meeting_notes_path,
        "has_source": bool(result.request.source_text.strip()),
        "has_meeting_notes": bool(result.request.meeting_notes.strip()),
        "summary_mode_requested": summary_generation.requested_mode,
        "summary_mode_used": summary_generation.used_mode,
        "summary_fallback_reason": summary_generation.fallback_reason,
        "passes": [asdict(item) for item in result.passes],
    }
    if extra:
        data.update(extra)
    return data


def write_outputs(
    result: RevisionResult,
    output_dir: Path,
    source_path: Path | None = None,
    summary_generation: SummaryGeneration | None = None,
    extra_log: dict | None = None,
    *,
    mode: str = "unknown",
    status: str | None = None,
    parent_version: str | None = None,
    announce_final_review_report: bool = True,
) -> None:
    summary_generation = summary_generation or SummaryGeneration(text=build_changes_summary(result))
    layout = VersionLayout(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    layout.ensure_dirs()
    run_log_text = json.dumps(result_to_dict(result, summary_generation, extra=extra_log), ensure_ascii=False, indent=2)
    layout.final_md.write_text(result.final_text, encoding="utf-8")
    layout.run_log.write_text(run_log_text, encoding="utf-8")
    if source_path is None:
        write_final_docx(result.final_text, layout.final_docx)
    elif source_path.suffix.lower() == ".docx":
        write_final_docx(result.final_text, layout.final_docx, reference_path=source_path)
    round_review_paths = write_round_outputs(result, output_dir, source_path=source_path)
    write_revision_summary(summary_generation.text, layout.reviews_dir)
    if announce_final_review_report:
        print("[收尾] 正在生成最终人工复核报告 final_review_report...", flush=True)
    write_final_review_report(result, layout.final_review_report_dir)
    write_manifest(
        layout,
        structured_manifest(
            layout,
            project_name=result.request.title or output_dir.parent.parent.name,
            version=version_number_from_dir(output_dir),
            status=status,
            mode=mode,
            source_type=source_type_from_path(source_path),
            round_review_paths=round_review_paths,
            parent_version=parent_version,
        ),
    )


def write_round_outputs(result: RevisionResult, output_dir: Path, source_path: Path | None = None) -> list[Path]:
    drafts_dir = output_dir / "drafts"
    reviews_dir = output_dir / "reviews"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    write_docx = bool(source_path and source_path.suffix.lower() == ".docx")
    review_paths: list[Path] = []

    for revision_pass in result.passes:
        round_id = f"round_{revision_pass.cycle_index:02d}"
        draft_md = drafts_dir / f"{round_id}_draft.md"
        review_md = reviews_dir / f"{round_id}_review.md"
        draft_md.write_text(revision_pass.draft, encoding="utf-8")
        review_md.write_text(revision_pass.review, encoding="utf-8")
        review_paths.append(review_md)
        if write_docx:
            write_final_docx(
                revision_pass.draft,
                drafts_dir / f"{round_id}_draft.docx",
                reference_path=source_path,
            )
            write_final_docx(revision_pass.review, reviews_dir / f"{round_id}_review.docx")
    return review_paths


def default_output_dir(args) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    if args.dry_run:
        return Path("outputs/demo/latest")
    return Path("outputs/autogen/latest")


def default_run_output_dirs(
    args,
    timestamp: str | None = None,
    *,
    project_dir: Path | None = None,
    version: int = 1,
) -> list[Path]:
    if args.output_dir:
        return [Path(args.output_dir)]
    run_timestamp = timestamp or datetime.now().strftime("%H%M%S")
    if project_dir is None:
        project_dir = Path("projects") / f"document_{datetime.now().strftime('%Y%m%d')}"
    base_dir = project_dir / ("dry_run_outputs" if args.dry_run else "outputs")
    return [base_dir / f"{run_timestamp}-pending-v{version}", base_dir / "latest"]


def resolve_project_output_root(project_dir: Path, *, dry_run: bool) -> Path:
    if dry_run:
        return project_dir / "dry_run_outputs"

    real_root = project_dir / "outputs"
    dry_root = project_dir / "dry_run_outputs"
    if _has_latest_output(real_root):
        return real_root
    if _has_latest_output(dry_root):
        return dry_root
    return real_root


def _has_latest_output(output_root: Path) -> bool:
    latest_metadata = output_root.parent / "metadata" / "latest.json"
    if latest_metadata.exists():
        try:
            data = json.loads(latest_metadata.read_text(encoding="utf-8"))
            return data.get("output_root") == output_root.name
        except (json.JSONDecodeError, OSError):
            return False
    return (output_root / "latest").exists()


def prepare_output_dir(output_dir: Path) -> bool:
    if output_dir.name == "latest" and output_dir.exists():
        try:
            shutil.rmtree(output_dir)
        except PermissionError:
            return False
    return True


def print_review_command(output_dir: Path) -> None:
    print("使用下面的命令进行状态标记：")
    print(f'.\\scripts\\review_project.ps1 -ProjectDir "{output_dir}"')


def resolve_requirements_path(path_arg: str | None) -> Path:
    return Path(path_arg) if path_arg else DEFAULT_INPUT_DIR / "requirements.md"


def resolve_source_path(path_arg: str | None) -> Path | None:
    if path_arg:
        path = Path(path_arg)
        return path if path.exists() else None
    for candidate in SOURCE_CANDIDATES:
        path = DEFAULT_INPUT_DIR / candidate
        if path.exists():
            return path
    return None


def resolve_meeting_notes_path(path_arg: str | None) -> Path | None:
    if path_arg:
        path = Path(path_arg)
        return path if path.exists() else None
    path = DEFAULT_INPUT_DIR / "meeting_notes.md"
    return path if path.exists() else None


def read_optional_document_text(path: Path | None) -> str:
    if path is None:
        return ""
    return read_source_text(path).strip()


def read_required_text(path: Path, label: str) -> str:
    if not path.exists():
        raise SystemExit(f"{label} file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"{label} file is empty: {path}")
    return text


def build_summary_generation(
    result: RevisionResult,
    *,
    mode: str,
    reviewer_settings,
) -> SummaryGeneration:
    rule_summary = build_changes_summary(result)
    if mode == "rule":
        return SummaryGeneration(text=rule_summary, requested_mode="rule", used_mode="rule")

    try:
        llm_summary = generate_llm_changes_summary(
            result,
            reviewer_settings=reviewer_settings,
            rule_summary=rule_summary,
        )
        if not has_required_summary_headings(llm_summary):
            raise ValueError("LLM summary did not keep the required heading structure")
        return SummaryGeneration(text=llm_summary, requested_mode="llm", used_mode="llm")
    except Exception as exc:
        return SummaryGeneration(
            text=rule_summary,
            requested_mode="llm",
            used_mode="rule",
            fallback_reason=str(exc),
        )


def build_feedback_analysis(
    *,
    dry_run: bool,
    previous_text: str,
    original_requirements: str,
    feedback: str,
    reviewer_settings,
) -> str:
    if dry_run:
        return dry_run_feedback_analysis(feedback)
    try:
        return generate_llm_feedback_analysis(
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


def choose_project_title(
    args,
    *,
    source_path: Path | None,
    source_text: str,
    requirements: str,
    meeting_notes: str = "",
    reviewer_settings=None,
) -> str:
    if args.project_title:
        return args.project_title
    return fallback_project_title(source_path, source_text, requirements)


def generate_final_suggested_project_title(
    *,
    final_text: str,
    requirements: str,
    meeting_notes: str,
    reviewer_settings,
    language: str,
) -> str | None:
    start = datetime.now().timestamp()
    print(f"[收尾] 正在生成最终建议项目名，请求 reviewer 模型 {reviewer_settings.model}...", flush=True)
    try:
        title = generate_llm_project_title(
            source_text=final_text,
            requirements=requirements,
            meeting_notes=meeting_notes,
            reviewer_settings=reviewer_settings,
            language=language,
        )
        title = title.strip()
        if not title:
            return None
        elapsed = datetime.now().timestamp() - start
        print(f"[收尾] 最终建议项目名生成完成，用时 {elapsed:.1f} 秒：{title}", flush=True)
        return title
    except Exception as exc:
        elapsed = datetime.now().timestamp() - start
        print(f"[收尾] 最终建议项目名生成失败，用时 {elapsed:.1f} 秒，保留当前项目目录名：{exc}", flush=True)
        return None


def finalize_project_directory(context, final_title: str):
    print(
        "***[收尾] 正在根据最终建议项目名整理项目目录。请暂时不要用 Word/WPS/记事本打开本项目文件。***",
        flush=True,
    )
    new_context, rename_result = finalize_project_title(context, final_title)
    if rename_result.status == "renamed":
        print(f"[收尾] 项目目录已重命名：{new_context.project_dir}", flush=True)
    elif rename_result.status == "unchanged":
        print(f"[收尾] 项目目录名已匹配最终建议项目名：{new_context.project_dir}", flush=True)
    else:
        print(
            "[收尾] 项目目录暂时无法重命名，可能有文件被打开。"
            "请关闭 Word/WPS/记事本后手动重命名，或稍后重试。"
            f"原因：{rename_result.reason}",
            flush=True,
        )
    return new_context


def run_continue_project(args, *, writer_settings, reviewer_settings) -> int:
    target = resolve_continue_target(args.continue_project, dry_run=args.dry_run)
    project_dir = target.project_dir

    inputs_dir = project_dir / "inputs"
    feedback_path = inputs_dir / "feedback.md"
    feedback = read_feedback(feedback_path)
    requirements_path = find_project_requirements_path(inputs_dir)
    original_requirements = read_required_text(requirements_path, "requirements")
    output_root = target.output_root
    use_dry_run = args.dry_run or output_root.name == "dry_run_outputs"
    previous_output_dir = target.previous_output_dir
    previous_final_path = resolve_previous_final_path(previous_output_dir)
    if previous_final_path.suffix.lower() == ".docx":
        previous_text = read_source_text(previous_final_path).strip()
    else:
        previous_text = previous_final_path.read_text(encoding="utf-8").strip()
    if not previous_text:
        raise SystemExit(f"previous final draft is empty: {previous_output_dir}")

    feedback_analysis = build_feedback_analysis(
        dry_run=use_dry_run,
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
    request = RevisionRequest(
        source_text=previous_text,
        requirements=requirements,
        cycles=args.cycles,
        title=project_dir.name,
        source_path=str(previous_final_path),
    )

    if use_dry_run:
        result = run_revision_loop(
            request,
            writer=dry_run_writer,
            reviewer=dry_run_reviewer,
        )
    else:
        from .autogen_runner import run_autogen_revision_loop

        result = run_autogen_revision_loop(
            request,
            writer_settings=writer_settings,
            reviewer_settings=reviewer_settings,
            writer_prompt_path=args.writer_prompt,
            reviewer_prompt_path=args.reviewer_prompt,
        )

    summary_generation = build_summary_generation(
        result,
        mode=args.summary_mode,
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
    }
    write_outputs(
        result,
        current_version_dir,
        source_path=source_reference,
        summary_generation=summary_generation,
        extra_log=extra_log,
        mode="dry-run" if use_dry_run else "real",
        status="continue",
        parent_version=previous_version,
    )
    write_session_status(current_version_dir, status="continue", current_version=current_version)

    latest_dir = output_root / "latest"
    written_dirs = [current_version_dir]
    skipped_dirs = []
    if prepare_output_dir(latest_dir):
        write_outputs(
            result,
            latest_dir,
            source_path=source_reference,
            summary_generation=summary_generation,
            extra_log=extra_log,
            mode="dry-run" if use_dry_run else "real",
            status="continue",
            parent_version=previous_version,
            announce_final_review_report=False,
        )
        write_session_status(latest_dir, status="continue", current_version=current_version)
        written_dirs.append(latest_dir)
    else:
        skipped_dirs.append(latest_dir)
    write_latest_metadata(output_root, current_version_dir)
    print("Wrote continued revision outputs to " + ", ".join(str(path) for path in written_dirs))
    print_review_command(current_version_dir)
    if skipped_dirs:
        print(
            "Skipped locked output directories: "
            + ", ".join(str(path) for path in skipped_dirs)
            + ". Close any open files there before refreshing latest."
        )
    return 0


def run_review_project(args) -> int:
    target = resolve_continue_target(args.review_project, dry_run=args.dry_run)
    project_dir = target.project_dir
    output_root = target.output_root
    decision = args.decision or read_interactive_decision(project_dir)
    input_path = Path(args.review_project)
    if input_path == target.previous_output_dir:
        result = apply_decision_to_session(
            output_root,
            target.previous_output_dir,
            decision,
            prefer_session_command=True,
            update_latest=False,
        )
    else:
        result = apply_session_decision(output_root, decision)
    print(result.message)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    loaded_config = load_env_file(args.config)
    config_values = merged_env_values(loaded_config)
    writer_settings = load_role_settings(
        config_values,
        "WRITER",
        default_model=args.writer_model or "gpt-4.1",
    )
    reviewer_settings = load_role_settings(
        config_values,
        "REVIEWER",
        default_model=args.reviewer_model or "gpt-4.1",
    )
    if args.writer_model:
        writer_settings = replace(writer_settings, model=args.writer_model)
    if args.reviewer_model:
        reviewer_settings = replace(reviewer_settings, model=args.reviewer_model)

    if args.check_connections:
        from .connection_test import check_all_connections

        results = check_all_connections([writer_settings, reviewer_settings])
        for result in results:
            status = "OK" if result.ok else "FAIL"
            print(f"[{status}] {result.role} model={result.model} elapsed={result.elapsed_seconds:.1f}s: {result.message}")
        return 0 if all(result.ok for result in results) else 1

    if args.review_project:
        return run_review_project(args)

    if args.continue_project:
        return run_continue_project(
            args,
            writer_settings=writer_settings,
            reviewer_settings=reviewer_settings,
        )

    source_path = resolve_source_path(args.source)
    requirements_path = resolve_requirements_path(args.requirements)
    meeting_notes_path = resolve_meeting_notes_path(args.meeting_notes)
    source_text = read_optional_document_text(source_path)
    requirements = read_required_text(requirements_path, "requirements")
    meeting_notes = read_optional_document_text(meeting_notes_path)

    project_context = None
    if not args.output_dir:
        now = datetime.now()
        project_title = choose_project_title(
            args,
            source_path=source_path,
            source_text=source_text,
            requirements=requirements,
            meeting_notes=meeting_notes,
            reviewer_settings=reviewer_settings,
        )
        project_context = create_project_context(
            projects_root=args.projects_root,
            title=project_title,
            created_date=now.strftime("%Y%m%d"),
        )
        snapshot_project_inputs(
            project_context,
            source_path=source_path,
            requirements_path=requirements_path,
            meeting_notes_path=meeting_notes_path,
        )
        ensure_feedback_template(project_context.inputs_dir)

    request = RevisionRequest(
        source_text=source_text,
        requirements=requirements,
        meeting_notes=meeting_notes,
        cycles=args.cycles,
        title=source_path.stem if source_path else requirements_path.stem,
        source_path=str(source_path) if source_path else None,
        meeting_notes_path=str(meeting_notes_path) if meeting_notes_path else None,
    )

    if args.dry_run:
        result = run_revision_loop(
            request,
            writer=dry_run_writer,
            reviewer=dry_run_reviewer,
        )
    else:
        from .autogen_runner import run_autogen_revision_loop

        result = run_autogen_revision_loop(
            request,
            writer_settings=writer_settings,
            reviewer_settings=reviewer_settings,
            writer_prompt_path=args.writer_prompt,
            reviewer_prompt_path=args.reviewer_prompt,
        )

    if project_context and not args.dry_run:
        final_title = generate_final_suggested_project_title(
            final_text=result.final_text,
            requirements=requirements,
            meeting_notes=meeting_notes,
            reviewer_settings=reviewer_settings,
            language=args.project_title_language,
        )
        if final_title:
            project_context = finalize_project_directory(project_context, final_title)

    summary_generation = build_summary_generation(
        result,
        mode=args.summary_mode,
        reviewer_settings=reviewer_settings,
    )

    run_time = datetime.now().strftime("%H%M%S")
    output_dirs = default_run_output_dirs(
        args,
        run_time,
        project_dir=project_context.project_dir if project_context else None,
        version=next_output_version(
            project_context.dry_run_outputs_dir if args.dry_run else project_context.outputs_dir
        )
        if project_context
        else 1,
    )
    written_dirs: list[Path] = []
    skipped_dirs: list[Path] = []
    for output_dir in output_dirs:
        if not prepare_output_dir(output_dir):
            skipped_dirs.append(output_dir)
            continue
        write_outputs(
            result,
            output_dir,
            source_path=source_path,
            summary_generation=summary_generation,
            mode="dry-run" if args.dry_run else "real",
            status="pending",
            announce_final_review_report=output_dir.name != "latest",
        )
        write_session_status(output_dir, current_version="v1")
        written_dirs.append(output_dir)
    if project_context and written_dirs:
        primary_session_dir = next((path for path in written_dirs if path.name != "latest"), written_dirs[0])
        output_root = project_context.dry_run_outputs_dir if args.dry_run else project_context.outputs_dir
        write_latest_metadata(output_root, primary_session_dir)
    print("Wrote revision outputs to " + ", ".join(str(path) for path in written_dirs))
    if project_context and written_dirs:
        print_review_command(primary_session_dir)
    if skipped_dirs:
        print(
            "Skipped locked output directories: "
            + ", ".join(str(path) for path in skipped_dirs)
            + ". Close any open files there before refreshing latest."
        )
    return 0
