from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .continue_flow import find_latest_output_dir, version_label_from_output_dir
from .project_manager import write_latest_session, write_session_status


VALID_DECISIONS = ("accept", "continue", "abandon", "skip")
RENAMABLE_STATUSES = ("pending", "accept", "continue", "abandon")


@dataclass(frozen=True)
class DecisionResult:
    status: str
    session_dir: Path
    renamed: bool
    message: str


def decision_dir_name(current_name: str, decision: str) -> str:
    if decision not in {"pending", "accept", "continue", "abandon"}:
        return current_name
    status_pattern = "|".join(RENAMABLE_STATUSES)
    return re.sub(rf"-({status_pattern})-v(\d+)$", rf"-{decision}-v\2", current_name, count=1)


def apply_session_decision(output_root: str | Path, decision: str) -> DecisionResult:
    if decision not in VALID_DECISIONS:
        raise SystemExit(f"decision must be one of: {', '.join(VALID_DECISIONS)}")

    root = Path(output_root)
    session_dir = find_latest_output_dir(root)
    return apply_decision_to_session(root, session_dir, decision)


def apply_decision_to_session(
    output_root: str | Path,
    session_dir: str | Path,
    decision: str,
    *,
    prefer_session_command: bool = False,
    update_latest: bool = True,
) -> DecisionResult:
    if decision not in VALID_DECISIONS:
        raise SystemExit(f"decision must be one of: {', '.join(VALID_DECISIONS)}")

    root = Path(output_root)
    session_dir = Path(session_dir)
    project_dir = root.parent

    if decision == "skip":
        target_dir = session_dir.with_name(decision_dir_name(session_dir.name, "pending"))
        renamed = False
        final_dir = session_dir
        if target_dir != session_dir:
            try:
                session_dir.rename(target_dir)
                final_dir = target_dir
                renamed = True
            except PermissionError:
                final_dir = session_dir
        current_version = version_label_from_output_dir(final_dir)
        write_session_status(final_dir, status="pending", current_version=current_version)
        if update_latest:
            _write_latest_status(root, status="pending", current_version=current_version)
            write_latest_session(root, final_dir)
        command_target = final_dir if prefer_session_command else project_dir
        return DecisionResult(
            status="pending",
            session_dir=final_dir,
            renamed=renamed,
            message=(
                "Skipped for now. Run this command later to choose again: "
                f'.\\.venv\\Scripts\\python.exe .\\run_revision.py --review-project "{command_target}"'
            ),
        )

    target_dir = session_dir.with_name(decision_dir_name(session_dir.name, decision))
    renamed = False
    final_dir = session_dir
    if target_dir != session_dir:
        try:
            session_dir.rename(target_dir)
            final_dir = target_dir
            renamed = True
        except PermissionError:
            final_dir = session_dir

    current_version = version_label_from_output_dir(final_dir)
    write_session_status(final_dir, status=decision, current_version=current_version)
    if update_latest:
        _write_latest_status(root, status=decision, current_version=current_version)
        write_latest_session(root, final_dir)

    message = f"Marked latest result as {decision}: {final_dir}"
    if target_dir != session_dir and not renamed:
        message += " The directory could not be renamed. Close any open files there and rename it manually if needed."
    if decision == "continue":
        command_target = final_dir if prefer_session_command else project_dir
        message += (
            "\nFill feedback.md, then run: "
            f'.\\.venv\\Scripts\\python.exe .\\run_revision.py --continue-project "{command_target}"'
        )
    return DecisionResult(status=decision, session_dir=final_dir, renamed=renamed, message=message)


def _write_latest_status(output_root: Path, *, status: str, current_version: str) -> None:
    latest = output_root / "latest"
    if latest.exists():
        write_session_status(latest, status=status, current_version=current_version)


def print_decision_prompt(project_dir: str | Path) -> None:
    project = Path(project_dir)
    print("Choose how to handle the current latest result:")
    print("1. accept    accept this result and finish")
    print("2. continue  mark it for continued revision")
    print("3. abandon   abandon this result")
    print("4. skip      keep it pending for now")
    print("")
    print(f"Project directory: {project}")


def read_interactive_decision(project_dir: str | Path) -> str:
    print_decision_prompt(project_dir)
    answer = input("Enter accept / continue / abandon / skip: ").strip().lower()
    aliases = {"1": "accept", "2": "continue", "3": "abandon", "4": "skip"}
    decision = aliases.get(answer, answer)
    if decision not in VALID_DECISIONS:
        raise SystemExit(f"unknown decision: {answer}")
    return decision
