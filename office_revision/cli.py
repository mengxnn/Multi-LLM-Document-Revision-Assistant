from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Sequence

from .config import load_env_file, load_role_settings, merged_env_values
from .document_io import read_source_text, write_final_docx
from .dry_run import dry_run_reviewer, dry_run_writer
from .workflow import RevisionRequest, RevisionResult, run_revision_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a multi-cycle office document revision workflow."
    )
    parser.add_argument(
        "--source",
        default="inputs/source.docx",
        help="Path to the source document. Defaults to inputs/source.docx.",
    )
    parser.add_argument(
        "--requirements",
        default="inputs/requirements.md",
        help="Path to the revision requirements text/Markdown file.",
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
    if source_path and source_path.suffix.lower() == ".docx":
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

    source_path = Path(args.source)
    requirements_path = Path(args.requirements)
    source_text = read_source_text(source_path)
    requirements = requirements_path.read_text(encoding="utf-8")

    request = RevisionRequest(
        source_text=source_text,
        requirements=requirements,
        cycles=args.cycles,
        title=source_path.stem,
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

    output_dir = default_output_dir(args)
    write_outputs(result, output_dir, source_path=source_path)
    print(f"Wrote revision outputs to {output_dir}")
    return 0
