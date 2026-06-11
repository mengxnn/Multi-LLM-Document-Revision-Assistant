from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


FEEDBACK_TEMPLATE = """# 本轮反馈

请在这里写你希望下一版如何整体调整，例如：
- 哪些内容需要保留
- 哪些内容需要重写
- 风格、语气或结构要求
- 需要补充、删除或核实的内容
"""


def ensure_feedback_template(inputs_dir: str | Path) -> Path:
    feedback_path = Path(inputs_dir) / "feedback.md"
    if not feedback_path.exists():
        feedback_path.write_text(FEEDBACK_TEMPLATE, encoding="utf-8")
    return feedback_path


def read_feedback(feedback_path: str | Path) -> str:
    path = Path(feedback_path)
    if not path.exists():
        raise SystemExit(f"feedback file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"feedback file is empty: {path}")
    return text


def find_latest_output_dir(output_root: str | Path) -> Path:
    root = Path(output_root)
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


def next_version_dir(session_dir: str | Path) -> Path:
    session = Path(session_dir)
    existing_numbers: list[int] = []
    if session.exists():
        for child in session.iterdir():
            if child.is_dir():
                match = re.fullmatch(r"v(\d+)", child.name)
                if match:
                    existing_numbers.append(int(match.group(1)))
    return session / f"v{(max(existing_numbers) if existing_numbers else 0) + 1}"


def copy_previous_version(previous_output_dir: str | Path, target_version_dir: str | Path) -> None:
    source = Path(previous_output_dir)
    target = Path(target_version_dir)
    if not source.exists():
        raise SystemExit(f"previous output not found: {source}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


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
