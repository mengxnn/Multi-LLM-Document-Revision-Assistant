from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from office_revision.application.contracts import ProgressEvent, RevisionRunResult


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    kind: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    events: tuple[ProgressEvent, ...] = ()
    result: RevisionRunResult | None = None
    error: dict[str, str] | None = None
    project_id: str | None = None


class InMemoryRunStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, RunRecord] = {}

    def create_run(self, *, kind: str, project_id: str | None) -> RunRecord:
        record = RunRecord(
            run_id=uuid4().hex,
            kind=kind,
            status="queued",
            created_at=utc_now_iso(),
            project_id=project_id,
        )
        with self._lock:
            self._runs[record.run_id] = record
        return record

    def get_run(self, run_id: str) -> RunRecord:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            return self._runs[run_id]

    def mark_running(self, run_id: str) -> RunRecord:
        return self._update(run_id, status="running", started_at=utc_now_iso())

    def append_event(self, run_id: str, event: ProgressEvent) -> RunRecord:
        with self._lock:
            record = self._runs[run_id]
            updated = replace(record, events=record.events + (event,))
            self._runs[run_id] = updated
            return updated

    def mark_completed(self, run_id: str, result: RevisionRunResult) -> RunRecord:
        return self._update(
            run_id,
            status="completed",
            finished_at=utc_now_iso(),
            result=result,
        )

    def mark_failed(self, run_id: str, *, stage: str, message: str) -> RunRecord:
        return self._update(
            run_id,
            status="failed",
            finished_at=utc_now_iso(),
            error={"stage": stage, "message": message},
        )

    def _update(self, run_id: str, **changes: Any) -> RunRecord:
        with self._lock:
            record = self._runs[run_id]
            updated = replace(record, **changes)
            self._runs[run_id] = updated
            return updated
