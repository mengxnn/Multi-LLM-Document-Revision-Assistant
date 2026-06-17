from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .document_io import write_final_docx
from .workflow import RevisionPass, RevisionResult


ATTENTION_PATTERNS = ("需补充", "需核实", "待确认", "待补充", "TODO", "【需补充")
SUMMARY_HEADINGS = (
    "# 修改说明汇总",
    "## 一、运行概况",
    "## 二、输入材料",
    "## 三、每轮修改与审查摘要",
    "## 四、最终结论",
    "## 五、需人工补充或核实事项",
)


@dataclass(frozen=True)
class SummaryGeneration:
    text: str
    requested_mode: str = "rule"
    used_mode: str = "rule"
    fallback_reason: str | None = None


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


def write_changes_summary(
    result: RevisionResult,
    output_dir: str | Path,
    summary_text: str | None = None,
) -> None:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    summary = summary_text if summary_text is not None else build_changes_summary(result)
    (target_dir / "changes_summary.md").write_text(summary, encoding="utf-8")
    write_final_docx(summary, target_dir / "changes_summary.docx")


def write_revision_summary(summary_text: str, output_dir: str | Path) -> None:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "revision_summary.md").write_text(summary_text, encoding="utf-8")
    write_final_docx(summary_text, target_dir / "revision_summary.docx")


def build_final_review_report(result: RevisionResult) -> str:
    sections = [
        "# 最终人工复核报告",
        "",
        "## 一、最终结论",
        *_final_review_overview_lines(result),
        "",
        "## 二、修改要求完成情况",
        *_requirement_completion_lines(result),
        "",
        "## 三、仍需人工确认的问题",
        *_manual_attention_lines(result),
        "",
        "## 四、事实与数据风险",
        *_risk_lines(result, "事实风险", "数据", "政策", "依据", "引用", "来源"),
        "",
        "## 五、格式与表达风险",
        *_risk_lines(result, "格式", "表达", "语言", "结构", "排版"),
        "",
        "## 六、下一步建议",
        *_next_step_lines(result),
    ]
    return "\n".join(sections).rstrip() + "\n"


def write_final_review_report(result: RevisionResult, output_dir: str | Path) -> None:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    report = build_final_review_report(result)
    (target_dir / "final_review_report.md").write_text(report, encoding="utf-8")
    write_final_docx(report, target_dir / "final_review_report.docx")


def has_required_summary_headings(text: str) -> bool:
    positions: list[int] = []
    for heading in SUMMARY_HEADINGS:
        match = re.search(rf"(?m)^{re.escape(heading)}\s*$", text)
        if match is None:
            return False
        positions.append(match.start())
    return positions == sorted(positions)


def build_llm_summary_prompt(result: RevisionResult, rule_summary: str) -> str:
    round_logs = "\n\n".join(
        [
            "\n".join(
                [
                    f"### 第 {item.cycle_index} 轮",
                    f"writer 草稿：\n{item.draft}",
                    f"reviewer 审查：\n{item.review}",
                    f"reviewer 是否建议继续：{_continue_text(item.review_continue)}",
                    f"reviewer 评分：{item.review_score if item.review_score is not None else '未识别'}",
                    f"给 writer 的修改指令：{item.writer_instructions or '未识别'}",
                ]
            )
            for item in result.passes
        ]
    )
    return f"""请根据以下修订流程信息，只压缩长文本字段，并返回 JSON。

重要规则：
1. 不要改写运行事实，例如轮数、停止原因、输入来源、评分、是否继续修改。
2. 不要生成完整 Markdown，总结文件的固定格式会由程序生成。
3. 只压缩长文本字段：writer 草稿摘要、reviewer 审查摘要、给 writer 的修改指令、最终审查摘要、人工核实事项。
4. 不要编造未出现的事实、数据、轮次、来源或结论。
5. 每个摘要尽量控制在 1-2 句话，保留核心问题、核心修改和关键风险。

请严格返回以下 JSON，不要添加 Markdown 代码块以外的解释文字：
{{
  "rounds": [
    {{
      "cycle_index": 1,
      "writer_draft_summary": "对本轮 writer 草稿的简洁摘要",
      "reviewer_review_summary": "对本轮 reviewer 审查意见的简洁摘要",
      "writer_instructions_summary": "对给 writer 的修改指令的简洁摘要"
    }}
  ],
  "final_review_summary": "对最终审查意见的简洁摘要",
  "manual_attention_summary": "是否发现显式标记，以及建议人工核实的重点"
}}

最终 Markdown 必须保留这些标题，但你无需输出 Markdown：
{chr(10).join(SUMMARY_HEADINGS)}

【规则生成的参考汇总】
{rule_summary}

【输入材料】
初稿来源：{result.request.source_path or '未提供'}
初稿内容：
{result.request.source_text or '未提供'}

修改要求：
{result.request.requirements}

会议纪要来源：{result.request.meeting_notes_path or '未提供'}
会议纪要内容：
{result.request.meeting_notes or '未提供'}

【每轮 writer-reviewer 记录】
{round_logs or '未产生任何修改轮次。'}

【最终稿】
{result.final_text or '未生成最终稿。'}

【最终审查】
{result.final_review or '未生成最终审查。'}
"""


def parse_llm_summary_polish(text: str) -> dict:
    content = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    return json.loads(content)


def build_llm_polished_changes_summary(result: RevisionResult, polish: dict) -> str:
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
        *_llm_round_summary_lines(result.passes, polish),
        "",
        "## 四、最终结论",
        *_llm_final_conclusion_lines(result, polish),
        "",
        "## 五、需人工补充或核实事项",
        *_llm_manual_attention_lines(result, polish),
    ]
    return "\n".join(sections).rstrip() + "\n"


def _llm_round_summary_lines(passes: list[RevisionPass], polish: dict) -> list[str]:
    if not passes:
        return ["- 未产生任何修改轮次。"]

    polished_rounds = {
        int(item.get("cycle_index")): item
        for item in polish.get("rounds", [])
        if isinstance(item, dict) and item.get("cycle_index") is not None
    }
    lines: list[str] = []
    for item in passes:
        polished = polished_rounds.get(item.cycle_index, {})
        writer_summary = polished.get("writer_draft_summary") or _excerpt(item.draft)
        reviewer_summary = polished.get("reviewer_review_summary") or _excerpt(item.review)
        instructions_summary = polished.get("writer_instructions_summary") or (
            _excerpt(item.writer_instructions) if item.writer_instructions else "未识别"
        )
        lines.extend(
            [
                f"### 第 {item.cycle_index} 轮",
                f"- writer 草稿摘要：{writer_summary}",
                f"- reviewer 审查摘要：{reviewer_summary}",
                f"- 是否继续修改：{_continue_text(item.review_continue)}",
                f"- reviewer 评分：{item.review_score if item.review_score is not None else '未识别'}",
                f"- 给 writer 的修改指令：{instructions_summary}",
                "",
            ]
        )
    return lines[:-1] if lines and lines[-1] == "" else lines


def _llm_final_conclusion_lines(result: RevisionResult, polish: dict) -> list[str]:
    if not result.passes:
        return ["- 未生成最终稿。"]

    final_pass = result.passes[-1]
    final_review_summary = polish.get("final_review_summary") or _excerpt(final_pass.review, limit=360)
    return [
        f"- 最终稿是否基本满足要求：{_final_satisfaction_text(final_pass.review_continue)}",
        f"- 最终评分：{final_pass.review_score if final_pass.review_score is not None else '未识别'}",
        f"- 最终审查摘要：{final_review_summary}",
        "- 是否建议人工复核：是。自动生成内容仍需人工核对事实、数据、政策依据和格式。",
    ]


def _llm_manual_attention_lines(result: RevisionResult, polish: dict) -> list[str]:
    summary = polish.get("manual_attention_summary")
    if summary:
        return [f"- 显式标记检查：{summary}"]
    return [f"- 显式标记检查：{line.removeprefix('- ')}" for line in _manual_attention_lines(result)]


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


def _final_review_overview_lines(result: RevisionResult) -> list[str]:
    if not result.passes:
        return ["- 未生成最终稿，无法形成复核结论。"]
    final_pass = result.passes[-1]
    return [
        f"- 实际完成轮数：{len(result.passes)}",
        f"- 最终 reviewer 评分：{final_pass.review_score if final_pass.review_score is not None else '未识别'}",
        f"- 是否建议继续修改：{_continue_text(final_pass.review_continue)}",
        f"- 总体判断：{_final_satisfaction_text(final_pass.review_continue)}",
    ]


def _requirement_completion_lines(result: RevisionResult) -> list[str]:
    if not result.final_review.strip():
        return ["- 未生成审查意见，需人工对照修改要求逐项确认。"]
    return [
        "- 请以最终稿为准，对照原始修改要求逐项复核。",
        f"- 最终审查摘要：{_excerpt(result.final_review, limit=420)}",
    ]


def _risk_lines(result: RevisionResult, *keywords: str) -> list[str]:
    lines = []
    for line in result.final_review.splitlines():
        clean = line.strip(" -\t")
        if clean and any(keyword.lower() in clean.lower() for keyword in keywords):
            lines.append(f"- {clean}")
    if lines:
        return lines[:8]
    return ["- 未在最终审查意见中自动识别到明显风险项，仍建议人工核对关键事实、数据、格式和引用。"]


def _next_step_lines(result: RevisionResult) -> list[str]:
    if not result.passes:
        return ["- 重新运行修订流程并生成最终稿。"]
    final_pass = result.passes[-1]
    if final_pass.review_continue is True:
        return [
            "- reviewer 仍建议继续修改，可在项目的 inputs/feedback.md 中补充人工反馈后运行 continue。",
            f"- 可优先处理：{_excerpt(final_pass.writer_instructions or final_pass.review, limit=300)}",
        ]
    return [
        "- 先人工核对事实、数据、政策依据和专有名词。",
        "- 再检查 Word 格式、表格、标题层级和最终交付要求。",
        "- 如发现新问题，在 inputs/feedback.md 中写明后运行 continue。",
    ]


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
