from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from .autogen_runner import generate_llm_changes_summary
from .document_io import write_final_docx
from .project_paths import (
    VersionLayout,
    source_type_from_path,
    structured_manifest,
    version_number_from_dir,
    write_manifest,
)
from .summary import (
    SummaryGeneration,
    build_changes_summary,
    has_required_summary_headings,
    write_final_review_report,
    write_revision_summary,
)
from .workflow import RevisionResult


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


def build_summary_generation(result: RevisionResult, *, mode: str, reviewer_settings) -> SummaryGeneration:
    rule_summary = build_changes_summary(result)
    if mode == "rule":
        return SummaryGeneration(text=rule_summary, requested_mode="rule", used_mode="rule")
    try:
        text = generate_llm_changes_summary(
            result,
            reviewer_settings=reviewer_settings,
            rule_summary=rule_summary,
        )
        if not has_required_summary_headings(text):
            raise ValueError("LLM summary did not keep the required heading structure")
        return SummaryGeneration(text=text, requested_mode="llm", used_mode="llm")
    except Exception as exc:
        return SummaryGeneration(
            text=rule_summary,
            requested_mode="llm",
            used_mode="rule",
            fallback_reason=str(exc),
        )


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
) -> None:
    summary_generation = summary_generation or SummaryGeneration(text=build_changes_summary(result))
    layout = VersionLayout(output_dir)
    layout.ensure_dirs()
    layout.final_md.write_text(result.final_text, encoding="utf-8")
    layout.run_log.write_text(
        json.dumps(result_to_dict(result, summary_generation, extra=extra_log), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if source_path is not None and source_path.suffix.lower() == ".docx":
        write_final_docx(result.final_text, layout.final_docx, reference_path=source_path)
    else:
        write_final_docx(result.final_text, layout.final_docx)
    round_review_paths = write_round_outputs(result, output_dir, source_path=source_path)
    write_revision_summary(summary_generation.text, layout.reviews_dir)
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
        (drafts_dir / f"{round_id}_draft.md").write_text(revision_pass.draft, encoding="utf-8")
        review_md = reviews_dir / f"{round_id}_review.md"
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


def prepare_output_dir(output_dir: Path) -> bool:
    if output_dir.name == "latest" and output_dir.exists():
        try:
            shutil.rmtree(output_dir)
        except PermissionError:
            return False
    return True
