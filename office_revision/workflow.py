from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Callable

from .review_analysis import parse_review_decision


@dataclass(frozen=True)
class RevisionRequest:
    source_text: str
    requirements: str
    meeting_notes: str = ""
    cycles: int = 2
    title: str = "office-revision"
    source_path: str | None = None
    meeting_notes_path: str | None = None


@dataclass(frozen=True)
class WriterContext:
    source_text: str
    requirements: str
    cycle_index: int
    meeting_notes: str = ""
    previous_draft: str | None = None
    previous_review: str | None = None
    previous_writer_instructions: str | None = None


@dataclass(frozen=True)
class ReviewContext:
    source_text: str
    requirements: str
    cycle_index: int
    draft: str
    meeting_notes: str = ""
    previous_review: str | None = None


@dataclass(frozen=True)
class RevisionPass:
    cycle_index: int
    draft: str
    review: str
    review_continue: bool | None = None
    review_score: int | None = None
    writer_instructions: str = ""


@dataclass(frozen=True)
class RevisionResult:
    request: RevisionRequest
    passes: list[RevisionPass] = field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str | None = None

    @property
    def final_text(self) -> str:
        return self.passes[-1].draft if self.passes else ""

    @property
    def final_review(self) -> str:
        return self.passes[-1].review if self.passes else ""


Writer = Callable[[WriterContext], str]
Reviewer = Callable[[ReviewContext], str]
ProgressHook = Callable[..., None]


def _emit_progress(
    on_progress: ProgressHook | None,
    stage: str,
    cycle: int,
    total: int,
    elapsed_seconds: float | None = None,
) -> None:
    if not on_progress:
        return
    signature = inspect.signature(on_progress)
    accepts_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
    positional_count = sum(
        parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for parameter in signature.parameters.values()
    )
    if accepts_varargs or positional_count >= 4:
        on_progress(stage, cycle, total, elapsed_seconds)
    else:
        on_progress(stage, cycle, total)


def run_revision_loop(
    request: RevisionRequest,
    *,
    writer: Writer,
    reviewer: Reviewer,
    on_progress: ProgressHook | None = None,
) -> RevisionResult:
    if request.cycles <= 0:
        raise ValueError("cycles must be greater than 0")

    passes: list[RevisionPass] = []
    previous_draft: str | None = None
    previous_review: str | None = None
    previous_writer_instructions: str | None = None

    for cycle_index in range(1, request.cycles + 1):
        source_text = request.source_text if cycle_index == 1 else ""
        meeting_notes = request.meeting_notes if cycle_index == 1 else ""
        _emit_progress(on_progress, "writer_running", cycle_index, request.cycles)
        started_at = time.perf_counter()
        draft = writer(
            WriterContext(
                source_text=source_text,
                requirements=request.requirements,
                meeting_notes=meeting_notes,
                cycle_index=cycle_index,
                previous_draft=previous_draft,
                previous_review=previous_review,
                previous_writer_instructions=previous_writer_instructions,
            )
        )
        _emit_progress(
            on_progress,
            "writer_completed",
            cycle_index,
            request.cycles,
            time.perf_counter() - started_at,
        )
        _emit_progress(on_progress, "reviewer_running", cycle_index, request.cycles)
        started_at = time.perf_counter()
        review = reviewer(
            ReviewContext(
                source_text=source_text,
                requirements=request.requirements,
                meeting_notes=meeting_notes,
                cycle_index=cycle_index,
                draft=draft,
                previous_review=previous_review,
            )
        )
        _emit_progress(
            on_progress,
            "reviewer_completed",
            cycle_index,
            request.cycles,
            time.perf_counter() - started_at,
        )
        decision = parse_review_decision(review)
        passes.append(
            RevisionPass(
                cycle_index=cycle_index,
                draft=draft,
                review=review,
                review_continue=decision.continue_revision,
                review_score=decision.score,
                writer_instructions=decision.writer_instructions,
            )
        )
        if decision.continue_revision is False:
            return RevisionResult(
                request=request,
                passes=passes,
                stopped_early=True,
                stop_reason="reviewer_requested_stop",
            )
        previous_draft = draft
        previous_review = review
        previous_writer_instructions = decision.writer_instructions

    return RevisionResult(request=request, passes=passes)
