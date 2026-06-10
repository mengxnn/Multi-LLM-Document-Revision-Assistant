from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .config import load_env_file, load_role_settings, merged_env_values
from .document_io import read_source_text, write_final_docx
from .dry_run import dry_run_reviewer, dry_run_writer
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
    return parser


def result_to_dict(result: RevisionResult) -> dict:
    return {
        "title": result.request.title,
        "cycles": result.request.cycles,
        "actual_cycles": len(result.passes),
        "stopped_early": result.stopped_early,
        "stop_reason": result.stop_reason,
        "source_path": result.request.source_path,
        "meeting_notes_path": result.request.meeting_notes_path,
        "has_source": bool(result.request.source_text.strip()),
        "has_meeting_notes": bool(result.request.meeting_notes.strip()),
        "passes": [asdict(item) for item in result.passes],
    }


def write_outputs(result: RevisionResult, output_dir: Path, source_path: Path | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "final.md").write_text(result.final_text, encoding="utf-8")
    (output_dir / "review.md").write_text(result.final_review, encoding="utf-8")
    (output_dir / "run_log.json").write_text(
        json.dumps(result_to_dict(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if source_path is None:
        write_final_docx(result.final_text, output_dir / "final.docx")
    elif source_path.suffix.lower() == ".docx":
        write_final_docx(result.final_text, output_dir / "final.docx", reference_path=source_path)
    write_round_outputs(result, output_dir, source_path=source_path)


def write_round_outputs(result: RevisionResult, output_dir: Path, source_path: Path | None = None) -> None:
    drafts_dir = output_dir / "drafts"
    reviews_dir = output_dir / "reviews"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    write_docx = bool(source_path and source_path.suffix.lower() == ".docx")

    for revision_pass in result.passes:
        round_id = f"round_{revision_pass.cycle_index:02d}"
        draft_md = drafts_dir / f"{round_id}_draft.md"
        review_md = reviews_dir / f"{round_id}_review.md"
        draft_md.write_text(revision_pass.draft, encoding="utf-8")
        review_md.write_text(revision_pass.review, encoding="utf-8")
        if write_docx:
            write_final_docx(
                revision_pass.draft,
                drafts_dir / f"{round_id}_draft.docx",
                reference_path=source_path,
            )
            write_final_docx(revision_pass.review, reviews_dir / f"{round_id}_review.docx")


def default_output_dir(args) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    if args.dry_run:
        return Path("outputs/demo/latest")
    return Path("outputs/autogen/latest")


def default_run_output_dirs(args, timestamp: str | None = None) -> list[Path]:
    if args.output_dir:
        return [Path(args.output_dir)]
    run_timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path("outputs/demo" if args.dry_run else "outputs/autogen")
    return [base_dir / run_timestamp, base_dir / "latest"]


def prepare_output_dir(output_dir: Path) -> bool:
    if output_dir.name == "latest" and output_dir.exists():
        try:
            shutil.rmtree(output_dir)
        except PermissionError:
            return False
    return True


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
            print(f"[{status}] {result.role} model={result.model}: {result.message}")
        return 0 if all(result.ok for result in results) else 1

    source_path = resolve_source_path(args.source)
    requirements_path = resolve_requirements_path(args.requirements)
    meeting_notes_path = resolve_meeting_notes_path(args.meeting_notes)
    source_text = read_optional_document_text(source_path)
    requirements = read_required_text(requirements_path, "requirements")
    meeting_notes = read_optional_document_text(meeting_notes_path)

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

    output_dirs = default_run_output_dirs(args)
    written_dirs: list[Path] = []
    skipped_dirs: list[Path] = []
    for output_dir in output_dirs:
        if not prepare_output_dir(output_dir):
            skipped_dirs.append(output_dir)
            continue
        write_outputs(result, output_dir, source_path=source_path)
        written_dirs.append(output_dir)
    print("Wrote revision outputs to " + ", ".join(str(path) for path in written_dirs))
    if skipped_dirs:
        print(
            "Skipped locked output directories: "
            + ", ".join(str(path) for path in skipped_dirs)
            + ". Close any open files there before refreshing latest."
        )
    return 0
