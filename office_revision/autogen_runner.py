from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from .config import ModelSettings, read_optional_text
from .review_analysis import parse_review_decision
from .summary import (
    build_llm_polished_changes_summary,
    build_llm_summary_prompt,
    parse_llm_summary_polish,
)
from .workflow import (
    ReviewContext,
    RevisionPass,
    RevisionRequest,
    RevisionResult,
    WriterContext,
    _emit_progress,
)


WRITER_SYSTEM_MESSAGE = """你是严谨的中文办公文档写作助手。
你的任务是根据用户提供的修改要求、可选原文、可选会议纪要、上一版草稿和 reviewer 给出的明确修改指令，生成可直接用于项目实施方案、申请书、论文或汇报材料的修改稿。
要求：结构清晰、语气正式、避免编造事实；如缺少必要信息，用“【需补充：...】”标出。
如果用户没有提供原文，则根据修改要求和会议纪要从零起草。"""

REVIEWER_SYSTEM_MESSAGE = """你是严谨的中文文档审查专家。
你的任务是检查修改稿是否符合用户要求，并结合可选原文和可选会议纪要指出事实风险、逻辑问题、遗漏项、格式问题，给出下一轮可执行修改建议。
请使用固定 Markdown 结构输出，并明确写出“是否继续修改：是/否”和“给 writer 的修改指令”。"""


def _optional_imports() -> tuple[Any, Any]:
    try:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_ext.models.openai import OpenAIChatCompletionClient
    except ImportError as exc:
        raise RuntimeError(
            "AutoGen packages are not installed. Install them with "
            '`pip install -U "autogen-agentchat" "autogen-ext[openai]"`, '
            "or run with --dry-run."
        ) from exc
    return AssistantAgent, OpenAIChatCompletionClient


def _model_client_kwargs(settings: ModelSettings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model": settings.model}
    if settings.api_key:
        kwargs["api_key"] = settings.api_key
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    kwargs["timeout"] = settings.timeout_seconds
    kwargs["max_retries"] = settings.max_retries
    if settings.enable_search:
        kwargs["extra_body"] = {"enable_search": True}
    kwargs["model_info"] = {
        "vision": settings.vision,
        "function_calling": settings.function_calling,
        "json_output": settings.json_output,
        "family": settings.model_family,
        "structured_output": settings.structured_output,
    }
    return kwargs


def _model_client(model_class: Any, settings: ModelSettings) -> Any:
    return model_class(**_model_client_kwargs(settings))


def _message_content(task_result: Any) -> str:
    messages = getattr(task_result, "messages", None)
    if not messages:
        return ""
    content = getattr(messages[-1], "content", "")
    return content if isinstance(content, str) else str(content)


async def _run_role_task(role: str, cycle_index: int, model: str, call, *, stages: list[str] | None = None) -> str:
    start = time.perf_counter()

    for stage in stages or []:
        print(f"[{role}] 第 {cycle_index} 轮：{stage}。", flush=True)
    print(f"[{role}] 第 {cycle_index} 轮开始，请求模型 {model}...", flush=True)
    try:
        result = await call()
    except Exception:
        elapsed = time.perf_counter() - start
        print(f"[{role}] 第 {cycle_index} 轮失败，用时 {elapsed:.1f} 秒。", flush=True)
        print(
            f"[{role}] 如果是请求超时，可在 config/settings.env 调整 "
            f"{role.upper()}_TIMEOUT_SECONDS，或减少 --cycles 后重试。",
            flush=True,
        )
        print("----------------------------------------------------", flush=True)
        raise
    elapsed = time.perf_counter() - start
    print(f"[{role}] 第 {cycle_index} 轮完成，用时 {elapsed:.1f} 秒。", flush=True)
    print("----------------------------------------------------", flush=True)
    return result


def _optional_section(title: str, value: str, missing_text: str) -> str:
    content = value.strip()
    return f"【{title}】\n{content if content else missing_text}"


def _writer_prompt(context: WriterContext) -> str:
    source_section = (
        _optional_section("原文/初稿", context.source_text, "未提供原文或初稿，请从零起草。")
        if context.cycle_index == 1
        else "【原文/初稿】\n本轮不重复提供初始原文，请以上一版草稿为修改基础。"
    )
    meeting_section = (
        _optional_section("会议纪要", context.meeting_notes, "未提供会议纪要。")
        if context.cycle_index == 1
        else "【会议纪要】\n本轮不重复提供会议纪要，请以修改要求和上一轮审查意见为准。"
    )
    return f"""请执行第 {context.cycle_index} 轮文档写作或修改。

【修改要求】
{context.requirements}

{source_section}

{meeting_section}

【上一轮完整审查意见】
{context.previous_review or "无，当前为首轮。"}

【上一版草稿】
{context.previous_draft or "无，当前为首轮。"}

请输出完整修改稿。优先落实上一轮审查意见中“给 writer 的修改指令”。如果是首轮且没有原文，请根据修改要求和会议纪要生成一版完整初稿。"""


def _reviewer_prompt(context: ReviewContext) -> str:
    source_section = (
        _optional_section("原文/初稿", context.source_text, "未提供原文或初稿，本轮应按从零起草场景审查。")
        if context.cycle_index == 1
        else "【原文/初稿】\n本轮不重复提供初始原文，请以当前修改稿和修改要求为审查基础。"
    )
    meeting_section = (
        _optional_section("会议纪要", context.meeting_notes, "未提供会议纪要。")
        if context.cycle_index == 1
        else "【会议纪要】\n本轮不重复提供会议纪要，请以修改要求和上一轮审查意见为准。"
    )
    return f"""请执行第 {context.cycle_index} 轮文档审查。

【修改要求】
{context.requirements}

{source_section}

{meeting_section}

【上一轮审查意见】
{context.previous_review or "无，当前为首轮。"}

【当前修改稿】
{context.draft}

请严格按以下 Markdown 结构输出：

一、总体结论
是否继续修改：是/否
总体评分：1-5
结论说明：……

二、修改要求落实情况
1. 要求：……
   状态：已落实/部分落实/未落实
   说明：……

三、主要问题
1. 问题类型：事实风险/逻辑结构/语言风格/格式规范/遗漏内容
   严重程度：高/中/低
   问题描述：……
   修改建议：……

四、下一轮修改清单
1. ……

五、给 writer 的修改指令
请用可直接交给 writer 执行的清单表达。

判断规则：
- 如果修改稿已经基本满足要求，只需要少量人工校对，则写“是否继续修改：否”。
- 如果仍有明显遗漏、事实风险、结构问题或未满足修改要求，则写“是否继续修改：是”。
- 不要重写全文，只输出审查意见。"""


async def _run_autogen_revision_loop_async(
    request: RevisionRequest,
    *,
    writer_settings: ModelSettings,
    reviewer_settings: ModelSettings,
    writer_prompt_path: str = "config/writer_system_prompt.md",
    reviewer_prompt_path: str = "config/reviewer_system_prompt.md",
    on_progress: Callable[[str, int, int, float | None], None] | None = None,
):
    AssistantAgent, OpenAIChatCompletionClient = _optional_imports()
    writer_client = _model_client(OpenAIChatCompletionClient, writer_settings)
    reviewer_client = _model_client(OpenAIChatCompletionClient, reviewer_settings)
    writer_agent = AssistantAgent(
        name="writer",
        model_client=writer_client,
        system_message=read_optional_text(writer_prompt_path, WRITER_SYSTEM_MESSAGE),
    )
    reviewer_agent = AssistantAgent(
        name="reviewer",
        model_client=reviewer_client,
        system_message=read_optional_text(reviewer_prompt_path, REVIEWER_SYSTEM_MESSAGE),
    )

    async def write(context: WriterContext) -> str:
        async def call():
            result = await writer_agent.run(task=_writer_prompt(context))
            return _message_content(result)

        stages = (
            ["正在阅读初稿、修改要求和会议纪要"]
            if context.cycle_index == 1
            else ["正在阅读上一版草稿、上一轮审查意见和修改要求"]
        )
        stages.append("正在生成新一版完整文档")
        return await _run_role_task("writer", context.cycle_index, writer_settings.model, call, stages=stages)

    async def review(context: ReviewContext) -> str:
        async def call():
            result = await reviewer_agent.run(task=_reviewer_prompt(context))
            return _message_content(result)

        stages = ["正在阅读本轮修改稿、上一轮审查意见和修改要求", "正在生成审查意见"]
        return await _run_role_task("reviewer", context.cycle_index, reviewer_settings.model, call, stages=stages)

    try:
        return await _run_async_revision_loop(
            request,
            writer=write,
            reviewer=review,
            on_progress=on_progress,
        )
    finally:
        await writer_client.close()
        await reviewer_client.close()


async def _run_async_revision_loop(request, *, writer, reviewer, on_progress=None):
    if request.cycles <= 0:
        raise ValueError("cycles must be greater than 0")

    passes = []
    previous_draft = None
    previous_review = None
    previous_writer_instructions = None
    for cycle_index in range(1, request.cycles + 1):
        source_text = request.source_text if cycle_index == 1 else ""
        meeting_notes = request.meeting_notes if cycle_index == 1 else ""
        _emit_progress(on_progress, "writer_running", cycle_index, request.cycles)
        started_at = time.perf_counter()
        draft = await writer(
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
        review = await reviewer(
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


def run_autogen_revision_loop(
    request: RevisionRequest,
    *,
    writer_settings: ModelSettings,
    reviewer_settings: ModelSettings,
    writer_prompt_path: str = "config/writer_system_prompt.md",
    reviewer_prompt_path: str = "config/reviewer_system_prompt.md",
    on_progress: Callable[[str, int, int, float | None], None] | None = None,
):
    return asyncio.run(
        _run_autogen_revision_loop_async(
            request,
            writer_settings=writer_settings,
            reviewer_settings=reviewer_settings,
            writer_prompt_path=writer_prompt_path,
            reviewer_prompt_path=reviewer_prompt_path,
            on_progress=on_progress,
        )
    )


async def _generate_llm_changes_summary_async(
    result: RevisionResult,
    *,
    reviewer_settings: ModelSettings,
    rule_summary: str,
):
    AssistantAgent, OpenAIChatCompletionClient = _optional_imports()
    reviewer_client = _model_client(OpenAIChatCompletionClient, reviewer_settings)
    summary_agent = AssistantAgent(
        name="summary_reviewer",
        model_client=reviewer_client,
        system_message=(
            "你是严谨的中文办公文档审查与汇总助手。"
            "请只根据用户提供的修订记录生成修改说明汇总，"
            "严格遵守用户要求的 Markdown 标题结构，不要编造事实。"
        ),
    )
    try:
        task_result = await summary_agent.run(task=build_llm_summary_prompt(result, rule_summary))
        return _llm_summary_markdown_from_response(result, _message_content(task_result))
    finally:
        await reviewer_client.close()


def generate_llm_changes_summary(
    result: RevisionResult,
    *,
    reviewer_settings: ModelSettings,
    rule_summary: str,
) -> str:
    return asyncio.run(
        _generate_llm_changes_summary_async(
            result,
            reviewer_settings=reviewer_settings,
            rule_summary=rule_summary,
        )
    )


async def _generate_llm_project_title_async(
    *,
    source_text: str,
    requirements: str,
    meeting_notes: str,
    reviewer_settings: ModelSettings,
    language: str,
) -> str:
    AssistantAgent, OpenAIChatCompletionClient = _optional_imports()
    reviewer_client = _model_client(OpenAIChatCompletionClient, reviewer_settings)
    title_agent = AssistantAgent(
        name="project_title_generator",
        model_client=reviewer_client,
        system_message=(
            "你负责为办公文档修订任务生成简短文件夹名。"
            "只输出一个名称，不要解释，不要加引号。"
        ),
    )
    try:
        result = await title_agent.run(
            task=(
                "请根据以下材料生成一个简短、易识别的项目文件夹名。\n"
                "要求：\n"
                "1. 只输出一个名称。\n"
                "2. 不超过 18 个中文字符或 30 个英文字符。\n"
                "3. 不要包含日期、时间、标点符号或 Windows 文件名非法字符。\n"
                f"4. 语言偏好：{language}。auto 表示按材料主要语言。\n\n"
                f"【初稿/原文】\n{source_text[:1200] or '未提供'}\n\n"
                f"【修改要求】\n{requirements[:1200]}\n\n"
                f"【会议纪要】\n{meeting_notes[:800] or '未提供'}"
            )
        )
        return _message_content(result).strip()
    finally:
        await reviewer_client.close()


def generate_llm_project_title(
    *,
    source_text: str,
    requirements: str,
    meeting_notes: str,
    reviewer_settings: ModelSettings,
    language: str = "auto",
) -> str:
    return asyncio.run(
        _generate_llm_project_title_async(
            source_text=source_text,
            requirements=requirements,
            meeting_notes=meeting_notes,
            reviewer_settings=reviewer_settings,
            language=language,
        )
    )


async def _generate_llm_feedback_analysis_async(
    *,
    previous_text: str,
    original_requirements: str,
    feedback: str,
    reviewer_settings: ModelSettings,
) -> str:
    AssistantAgent, OpenAIChatCompletionClient = _optional_imports()
    reviewer_client = _model_client(OpenAIChatCompletionClient, reviewer_settings)
    feedback_agent = AssistantAgent(
        name="feedback_analyst",
        model_client=reviewer_client,
        system_message=(
            "你是办公文档修订流程中的反馈分析助手。"
            "你的任务是把用户对上一版修改稿的反馈整理成 writer 可以直接执行的整体重写指令。"
            "不要重写全文，只输出清晰、可执行的分析和指令。"
        ),
    )
    try:
        result = await feedback_agent.run(
            task=(
                "请根据以下材料整理反馈分析。输出结构固定为：\n"
                "一、需要保留的内容\n"
                "二、需要重写或加强的内容\n"
                "三、整体风格与结构调整\n"
                "四、不能割裂处理的关联点\n"
                "五、给 writer 的整体重写指令\n\n"
                f"【上一版修改稿】\n{previous_text[:4000]}\n\n"
                f"【原始修改要求】\n{original_requirements[:2000]}\n\n"
                f"【用户本轮反馈】\n{feedback[:2000]}"
            )
        )
        return _message_content(result).strip()
    finally:
        await reviewer_client.close()


def generate_llm_feedback_analysis(
    *,
    previous_text: str,
    original_requirements: str,
    feedback: str,
    reviewer_settings: ModelSettings,
) -> str:
    return asyncio.run(
        _generate_llm_feedback_analysis_async(
            previous_text=previous_text,
            original_requirements=original_requirements,
            feedback=feedback,
            reviewer_settings=reviewer_settings,
        )
    )


def _llm_summary_markdown_from_response(result: RevisionResult, response: str) -> str:
    polish = parse_llm_summary_polish(response)
    return build_llm_polished_changes_summary(result, polish)
