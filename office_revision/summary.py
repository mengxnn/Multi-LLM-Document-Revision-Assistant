from __future__ import annotations

import re
from pathlib import Path

from .document_io import write_final_docx
from .workflow import RevisionPass, RevisionResult


ATTENTION_PATTERNS = ("需补充", "需核实", "待确认", "待补充", "TODO", "【需补充")


def build_changes_summary(result: RevisionResult) -> str:
    sections = [
        "# 修改说明汇总",
        "",
        "## 一、运行概况",
        *_run_overview_lines(result),
        "",
        "## 二、输入材料",
        *_input_material_lines(result),
        "",
        "## 三、每轮修改与审查摘要",
        *_round_summary_lines(result.passes),
        "",
        "## 四、最终结论",
        *_final_conclusion_lines(result),
        "",
        "## 五、需人工补充或核实事项",
        *_manual_attention_lines(result),
    ]
    return "\n".join(sections).rstrip() + "\n"


def write_changes_summary(result: RevisionResult, output_dir: str | Path) -> None:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    summary = build_changes_summary(result)
    (target_dir / "changes_summary.md").write_text(summary, encoding="utf-8")
    write_final_docx(summary, target_dir / "changes_summary.docx")


def extract_manual_attention_items(final_text: str, final_review: str) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for line in (final_text + "\n" + final_review).splitlines():
        for clean in _attention_candidates(line):
            if any(pattern.lower() in clean.lower() for pattern in ATTENTION_PATTERNS):
                if clean not in seen:
                    seen.add(clean)
                    items.append(clean)
    return items


def _attention_candidates(line: str) -> list[str]:
    clean = line.strip(" -\t")
    if not clean:
        return []
    parts = [part.strip(" -\t") for part in re.split(r"(?<=[。！？.!?])\s*", clean) if part.strip(" -\t")]
    return parts or [clean]


def _run_overview_lines(result: RevisionResult) -> list[str]:
    final_score = result.passes[-1].review_score if result.passes else None
    return [
        f"- 计划最大轮数：{result.request.cycles}",
        f"- 实际完成轮数：{len(result.passes)}",
        f"- 是否提前停止：{'是' if result.stopped_early else '否'}",
        f"- 停止原因：{result.stop_reason or '达到设定轮数或未触发提前停止'}",
        f"- 最终评分：{final_score if final_score is not None else '未识别'}",
    ]


def _input_material_lines(result: RevisionResult) -> list[str]:
    request = result.request
    return [
        f"- 初稿来源：{request.source_path or '未提供'}",
        f"- 是否有初稿内容：{'是' if request.source_text.strip() else '否'}",
        "- 修改要求来源：requirements.md 或命令行指定文件",
        f"- 会议纪要来源：{request.meeting_notes_path or '未提供'}",
        f"- 是否有会议纪要内容：{'是' if request.meeting_notes.strip() else '否'}",
    ]


def _round_summary_lines(passes: list[RevisionPass]) -> list[str]:
    if not passes:
        return ["- 未产生任何修改轮次。"]

    lines: list[str] = []
    for item in passes:
        lines.extend(
            [
                f"### 第 {item.cycle_index} 轮",
                f"- writer 草稿摘要：{_excerpt(item.draft)}",
                f"- reviewer 审查摘要：{_excerpt(item.review)}",
                f"- 是否继续修改：{_continue_text(item.review_continue)}",
                f"- reviewer 评分：{item.review_score if item.review_score is not None else '未识别'}",
                f"- 给 writer 的修改指令：{_excerpt(item.writer_instructions) if item.writer_instructions else '未识别'}",
                "",
            ]
        )
    return lines[:-1] if lines and lines[-1] == "" else lines


def _final_conclusion_lines(result: RevisionResult) -> list[str]:
    if not result.passes:
        return ["- 未生成最终稿。"]

    final_pass = result.passes[-1]
    return [
        f"- 最终稿是否基本满足要求：{_final_satisfaction_text(final_pass.review_continue)}",
        f"- 最终评分：{final_pass.review_score if final_pass.review_score is not None else '未识别'}",
        f"- 最终审查摘要：{_excerpt(final_pass.review, limit=360)}",
        "- 是否建议人工复核：是。自动生成内容仍需人工核对事实、数据、政策依据和格式。",
    ]


def _manual_attention_lines(result: RevisionResult) -> list[str]:
    items = extract_manual_attention_items(result.final_text, result.final_review)
    if not items:
        return ["- 未自动发现“需补充 / 需核实 / 待确认 / TODO”等显式标记。"]
    return [f"- {item}" for item in items]


def _continue_text(value: bool | None) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "未识别"


def _final_satisfaction_text(continue_revision: bool | None) -> str:
    if continue_revision is False:
        return "基本满足，reviewer 建议停止继续修改"
    if continue_revision is True:
        return "仍需继续修改"
    return "未识别，需要人工判断"


def _excerpt(text: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return "无"
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
