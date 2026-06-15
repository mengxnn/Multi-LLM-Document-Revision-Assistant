from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .project_paths import resolve_artifact


FEEDBACK_TEMPLATE = """# 本轮反馈

请在这里写你希望下一版如何整体调整，例如：
- 哪些内容需要保留
- 哪些内容需要重写
- 风格、语气或结构要求
- 需要补充、删除或核实的内容
"""


@dataclass(frozen=True)
class ContinueTarget:
    project_dir: Path
    output_root: Path
    previous_output_dir: Path


def ensure_feedback_template(inputs_dir: str | Path) -> Path:
    feedback_path = Path(inputs_dir) / "feedback.md"
    if not feedback_path.exists():
        feedback_path.write_text(FEEDBACK_TEMPLATE, encoding="utf-8")
    return feedback_path


def read_feedback(feedback_path: str | Path) -> str:
    path = Path(feedback_path)
    if not path.exists():
        raise SystemExit(f"feedback file not found: {path}. Please create it and write your revision feedback.")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"feedback file is empty: {path}. Please write your revision feedback before continuing.")
    if _normalize_feedback(text) == _normalize_feedback(FEEDBACK_TEMPLATE):
        raise SystemExit(
            f"feedback file still contains the default feedback template: {path}. "
            "Please replace it with your actual revision feedback before continuing."
        )
    return text


def _normalize_feedback(text: str) -> str:
    return re.sub(r"\s+", "", text)


def find_latest_output_dir(output_root: str | Path) -> Path:
    root = Path(output_root)
    latest_metadata = root.parent / "metadata" / "latest.json"
    if latest_metadata.exists():
        try:
            data = json.loads(latest_metadata.read_text(encoding="utf-8"))
            session_dir = Path(data["session_dir"])
            if session_dir.exists() and session_dir.parent == root:
                return session_dir
        except (KeyError, json.JSONDecodeError, OSError):
            pass

    latest_session = root / "latest_session.json"
    if latest_session.exists():
        try:
            data = json.loads(latest_session.read_text(encoding="utf-8"))
            session_dir = Path(data["session_dir"])
            if session_dir.exists():
                return session_dir
        except (KeyError, json.JSONDecodeError, OSError):
            pass

    latest = root / "latest"
    if latest.exists():
        return latest
    raise SystemExit(f"latest output not found under: {root}")


def resolve_previous_final_path(previous_output_dir: str | Path) -> Path:
    root = Path(previous_output_dir)
    for key in ("final_md", "final_docx"):
        try:
            return resolve_artifact(root, key)
        except FileNotFoundError:
            continue
    raise SystemExit(f"previous final.md/final.docx not found under: {root}")


def resolve_continue_target(path: str | Path, *, dry_run: bool) -> ContinueTarget:
    target = Path(path)
    if not target.exists():
        raise SystemExit(f"project or version directory not found: {target}")

    if _is_version_output_dir(target):
        output_root = target.parent
        project_dir = output_root.parent
        if output_root.name not in {"outputs", "dry_run_outputs"}:
            raise SystemExit(
                "version directory must be inside an outputs or dry_run_outputs directory: "
                f"{target}"
            )
        return ContinueTarget(
            project_dir=project_dir,
            output_root=output_root,
            previous_output_dir=target,
        )

    project_dir = target
    output_root = _resolve_project_output_root(project_dir, dry_run=dry_run)
    return ContinueTarget(
        project_dir=project_dir,
        output_root=output_root,
        previous_output_dir=find_latest_output_dir(output_root),
    )


def _is_version_output_dir(path: Path) -> bool:
    return path.is_dir() and re.search(r"-(pending|accept|continue|abandon)-v\d+$", path.name) is not None


def _resolve_project_output_root(project_dir: Path, *, dry_run: bool) -> Path:
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
    return (output_root / "latest_session.json").exists() or (output_root / "latest").exists()


def find_project_requirements_path(inputs_dir: str | Path) -> Path:
    root = Path(inputs_dir)
    preferred = root / "requirements.md"
    if preferred.exists():
        return preferred

    candidates = [
        path
        for path in root.glob("*.md")
        if path.name.lower() not in {"feedback.md", "meeting_notes.md"}
        and "meeting" not in path.stem.lower()
        and "source" not in path.stem.lower()
    ]
    requirement_named = [path for path in candidates if "requirement" in path.stem.lower()]
    if requirement_named:
        return sorted(requirement_named)[0]
    if candidates:
        return sorted(candidates)[0]
    raise SystemExit(f"requirements snapshot not found under: {root}")


def next_output_version(output_root: str | Path) -> int:
    root = Path(output_root)
    existing_numbers: list[int] = []
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                match = re.search(r"-v(\d+)$", child.name)
                if match:
                    existing_numbers.append(int(match.group(1)))
    return (max(existing_numbers) if existing_numbers else 0) + 1


def versioned_output_dir(output_root: str | Path, timestamp: str, status: str, version: int) -> Path:
    return Path(output_root) / f"{timestamp}-{status}-v{version}"


def version_label_from_output_dir(output_dir: str | Path) -> str:
    match = re.search(r"-v(\d+)$", Path(output_dir).name)
    if not match:
        return "unknown"
    return f"v{match.group(1)}"


def build_continue_requirements(
    *,
    original_requirements: str,
    feedback: str,
    feedback_analysis: str,
) -> str:
    return "\n\n".join(
        [
            "# 原始修改要求",
            original_requirements.strip(),
            "# 用户本轮反馈",
            feedback.strip(),
            "# 反馈分析与整体重写指令",
            feedback_analysis.strip(),
            "# 本轮任务",
            (
                "请以上一版结果为基础，吸收用户反馈，生成一版结构完整、前后衔接自然的整体重写稿。"
                "不要只做局部补丁；如果反馈中既有保留项又有重写项，请在整体结构中统一处理。"
            ),
        ]
    )


def dry_run_feedback_analysis(feedback: str) -> str:
    return "\n".join(
        [
            "dry-run feedback analysis:",
            "1. 保留用户明确认可的内容。",
            "2. 按用户反馈整体重写不满意的部分。",
            "3. 保持全文结构和语气一致，避免局部拼接感。",
            f"4. 用户反馈摘要：{feedback.strip()}",
        ]
    )
