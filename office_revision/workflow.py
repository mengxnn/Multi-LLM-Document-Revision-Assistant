from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .review_analysis import parse_review_decision


@dataclass(frozen=True)
class RevisionRequest:
    source_text: str
    requirements: str
    cycles: int = 2
    title: str = "office-revision"


@dataclass(frozen=True)
class WriterContext:
    source_text: str
    requirements: str
    cycle_index: int
    previous_draft: str | None = None
    previous_review: str | None = None
    previous_writer_instructions: str | None = None


@dataclass(frozen=True)
class ReviewContext:
    source_text: str
    requirements: str
    cycle_index: int
    draft: str


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


def run_revision_loop(
    request: RevisionRequest,
    *,
    writer: Writer,
    reviewer: Reviewer,
) -> RevisionResult:
    if request.cycles <= 0:
        raise ValueError("cycles must be greater than 0")

    passes: list[RevisionPass] = []
    previous_draft: str | None = None
    previous_review: str | None = None
    previous_writer_instructions: str | None = None

    for cycle_index in range(1, request.cycles + 1):
        draft = writer(
            WriterContext(
                source_text=request.source_text,
                requirements=request.requirements,
                cycle_index=cycle_index,
                previous_draft=previous_draft,
                previous_review=previous_review,
                previous_writer_instructions=previous_writer_instructions,
            )
        )
        review = reviewer(
            ReviewContext(
                source_text=request.source_text,
                requirements=request.requirements,
                cycle_index=cycle_index,
                draft=draft,
            )
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
