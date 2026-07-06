from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .application.contracts import InputSummary
from .document_io import read_source_text


LONG_INPUT_CHAR_LIMIT = 20_000
VERY_LONG_INPUT_CHAR_LIMIT = 80_000


def inspect_input_file(path: str | Path) -> InputSummary:
    input_path = Path(path)
    extracted_chars = _extracted_char_count(input_path)
    warnings: list[str] = []
    if extracted_chars == 0:
        warnings.append("empty")
    if extracted_chars > LONG_INPUT_CHAR_LIMIT:
        warnings.append("long")
    if extracted_chars > VERY_LONG_INPUT_CHAR_LIMIT:
        warnings.append("very_long")
    return InputSummary(
        name=input_path.name,
        kind=_kind(input_path),
        size_bytes=input_path.stat().st_size,
        extracted_chars=extracted_chars,
        warnings=tuple(warnings),
    )


def inspect_inputs_dir(inputs_dir: str | Path) -> dict[str, InputSummary]:
    root = Path(inputs_dir)
    if not root.exists():
        return {}
    summaries = {}
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file():
            summaries[path.name] = inspect_input_file(path)
    return summaries


def write_input_summaries(project_dir: str | Path) -> None:
    root = Path(project_dir)
    metadata_dir = root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    summaries = inspect_inputs_dir(root / "inputs")
    payload = {
        name: input_summary_to_dict(summary)
        for name, summary in summaries.items()
    }
    (metadata_dir / "input_summaries.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_input_summaries(project_dir: str | Path) -> dict[str, InputSummary]:
    root = Path(project_dir)
    path = root / "metadata" / "input_summaries.json"
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        if isinstance(raw, dict):
            loaded = {
                str(name): input_summary_from_dict(str(name), value)
                for name, value in raw.items()
                if isinstance(value, dict)
            }
            if loaded:
                return loaded
    return inspect_inputs_dir(root / "inputs")


def input_summary_to_dict(summary: InputSummary) -> dict[str, Any]:
    return {
        "name": summary.name,
        "kind": summary.kind,
        "size_bytes": summary.size_bytes,
        "extracted_chars": summary.extracted_chars,
        "warnings": list(summary.warnings),
    }


def input_summary_from_dict(name: str, value: dict[str, Any]) -> InputSummary:
    warnings = value.get("warnings")
    return InputSummary(
        name=str(value.get("name") or name),
        kind=str(value.get("kind") or ""),
        size_bytes=_int_or_zero(value.get("size_bytes")),
        extracted_chars=_int_or_zero(value.get("extracted_chars")),
        warnings=tuple(str(item) for item in warnings) if isinstance(warnings, list) else (),
    )


def _extracted_char_count(path: Path) -> int:
    try:
        return len(read_source_text(path).strip())
    except (OSError, UnicodeDecodeError, ValueError):
        return 0


def _kind(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "file"


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
