from __future__ import annotations

from .workflow import ReviewContext, WriterContext


def _excerpt(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def dry_run_writer(context: WriterContext) -> str:
    prior_review = context.previous_review or "首轮修改，无上一轮审查意见。"
    prior_instructions = context.previous_writer_instructions or "首轮修改，无上一轮明确修改指令。"
    prior_draft = context.previous_draft or "首轮修改，无上一版草稿。"

    return "\n".join(
        [
            f"# 第 {context.cycle_index} 轮修改稿",
            "",
            "## 修改要求",
            context.requirements.strip(),
            "",
            "## 参考原文",
            _excerpt(context.source_text),
            "",
            "## 已吸收的审查意见",
            _excerpt(prior_review),
            "",
            "## 已落实的 writer 指令",
            _excerpt(prior_instructions),
            "",
            "## 修改正文",
            "本稿根据上述要求对原文进行结构化调整，补充目标、实施步骤、责任分工和进度安排。",
            "后续接入真实大模型后，此处将由写作模型生成完整正文。",
            "",
            "## 上一稿摘要",
            _excerpt(prior_draft),
        ]
    )


def dry_run_reviewer(context: ReviewContext) -> str:
    return "\n".join(
        [
            "一、总体结论",
            "是否继续修改：是",
            "总体评分：3",
            "结论说明：dry-run 模式用于验证流程，默认继续到设定轮次。",
            "",
            "二、修改要求落实情况",
            f"1. 要求：{context.requirements.strip()}",
            "   状态：部分落实",
            "   说明：dry-run 仅模拟审查，不判断真实内容质量。",
            "",
            "三、主要问题",
            "1. 问题类型：事实风险",
            "   严重程度：中",
            "   问题描述：建议继续核对事实、数据来源和政策依据。",
            "   修改建议：补充可核验来源或标注“需补充”。",
            "",
            "四、下一轮修改清单",
            "1. 补充可量化目标、时间节点和验收标准。",
            "2. 强化逻辑衔接，减少泛化表述。",
            "",
            "五、给 writer 的修改指令",
            "1. 在下一轮中补充目标、时间节点和验收标准。",
            "2. 保持正式办公文风，减少空泛表述。",
            "",
            "六、当前稿摘录",
            _excerpt(context.draft),
        ]
    )
