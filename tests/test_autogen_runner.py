import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from office_revision.autogen_runner import (
    _llm_summary_markdown_from_response,
    _model_client_kwargs,
    _run_role_task,
    _run_async_revision_loop,
)
from office_revision.config import ModelSettings
from office_revision.workflow import RevisionPass, RevisionRequest, RevisionResult


class AutogenRunnerTests(unittest.TestCase):
    def test_model_client_kwargs_use_role_specific_settings(self):
        settings = ModelSettings(
            role="WRITER",
            api_key="writer-key",
            base_url="https://writer.example/v1",
            model="writer-model",
            enable_search=True,
            model_family="unknown",
            vision=False,
            function_calling=False,
            json_output=False,
            structured_output=False,
        )

        kwargs = _model_client_kwargs(settings)

        self.assertEqual(
            kwargs,
            {
                "model": "writer-model",
                "api_key": "writer-key",
                "base_url": "https://writer.example/v1",
                "extra_body": {"enable_search": True},
                "timeout": 60,
                "max_retries": 1,
                "model_info": {
                    "vision": False,
                    "function_calling": False,
                    "json_output": False,
                    "family": "unknown",
                    "structured_output": False,
                },
            },
        )

    def test_model_client_kwargs_omit_empty_base_url(self):
        settings = ModelSettings(
            role="REVIEWER",
            api_key="reviewer-key",
            base_url="",
            model="reviewer-model",
            enable_search=False,
            timeout_seconds=90,
            max_retries=4,
            model_family="unknown",
            vision=False,
            function_calling=False,
            json_output=False,
            structured_output=False,
        )

        kwargs = _model_client_kwargs(settings)

        self.assertEqual(
            kwargs,
            {
                "model": "reviewer-model",
                "api_key": "reviewer-key",
                "timeout": 90,
                "max_retries": 4,
                "model_info": {
                    "vision": False,
                    "function_calling": False,
                    "json_output": False,
                    "family": "unknown",
                    "structured_output": False,
                },
            },
        )

    def test_async_revision_loop_stops_when_review_says_no_more_revision(self):
        async def writer(context):
            return f"draft-{context.cycle_index}"

        async def reviewer(context):
            return """一、总体结论
是否继续修改：否
总体评分：5

五、给 writer 的修改指令
无需继续修改。
"""

        import asyncio

        result = asyncio.run(
            _run_async_revision_loop(
                RevisionRequest(source_text="source", requirements="requirements", cycles=3),
                writer=writer,
                reviewer=reviewer,
            )
        )

        self.assertEqual(len(result.passes), 1)
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.stop_reason, "reviewer_requested_stop")

    def test_run_role_task_prints_progress_and_elapsed_time(self):
        async def successful_call():
            return "done"

        output = StringIO()
        with patch("office_revision.autogen_runner.time.perf_counter", side_effect=[10.0, 22.3]):
            import asyncio

            with redirect_stdout(output):
                result = asyncio.run(_run_role_task("writer", 1, "writer-model", successful_call))

        self.assertEqual(result, "done")
        self.assertIn("-------", output.getvalue())
        self.assertIn("[writer] 第 1 轮开始，请求模型 writer-model...", output.getvalue())
        self.assertIn("[writer] 第 1 轮完成，用时 12.3 秒。", output.getvalue())

    def test_run_role_task_prints_stage_messages(self):
        async def successful_call():
            return "done"

        output = StringIO()
        with patch("office_revision.autogen_runner.time.perf_counter", side_effect=[10.0, 12.0]):
            import asyncio

            with redirect_stdout(output):
                asyncio.run(
                    _run_role_task(
                        "writer",
                        3,
                        "writer-model",
                        successful_call,
                        stages=["正在阅读上一轮审查意见和修改指令", "正在生成新一版完整文档"],
                    )
                )

        printed = output.getvalue()
        self.assertIn("[writer]", printed)
        self.assertIn("writer-model", printed)
        self.assertIn("上一轮", printed)
        self.assertIn("生成新一版", printed)

    def test_run_role_task_prints_failure_elapsed_before_reraising(self):
        async def failing_call():
            raise RuntimeError("boom")

        output = StringIO()
        with patch("office_revision.autogen_runner.time.perf_counter", side_effect=[3.0, 8.5]):
            import asyncio

            with redirect_stdout(output):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    asyncio.run(_run_role_task("reviewer", 2, "reviewer-model", failing_call))

        self.assertIn("[reviewer] 第 2 轮失败，用时 5.5 秒。", output.getvalue())

    def test_run_role_task_prints_timeout_suggestion_on_timeout_like_failure(self):
        async def failing_call():
            raise TimeoutError("request timed out")

        output = StringIO()
        with patch("office_revision.autogen_runner.time.perf_counter", side_effect=[1.0, 121.5]):
            import asyncio

            with redirect_stdout(output):
                with self.assertRaises(TimeoutError):
                    asyncio.run(_run_role_task("writer", 3, "writer-model", failing_call))

        printed = output.getvalue()
        self.assertIn("WRITER_TIMEOUT_SECONDS", printed)
        self.assertIn("--cycles", printed)

    def test_llm_summary_markdown_from_response_preserves_rule_facts(self):
        result = RevisionResult(
            request=RevisionRequest(
                source_text="source",
                requirements="requirements",
                cycles=5,
                source_path="inputs/source.docx",
            ),
            passes=[
                RevisionPass(
                    cycle_index=1,
                    draft="Long draft",
                    review="Long review",
                    review_continue=False,
                    review_score=5,
                    writer_instructions="Long instructions",
                )
            ],
            stopped_early=True,
            stop_reason="reviewer_requested_stop",
        )
        response = """```json
{
  "rounds": [
    {
      "cycle_index": 1,
      "writer_draft_summary": "压缩后的草稿摘要",
      "reviewer_review_summary": "压缩后的审查摘要",
      "writer_instructions_summary": "压缩后的修改指令"
    }
  ],
  "final_review_summary": "压缩后的最终审查",
  "manual_attention_summary": "未发现显式标记"
}
```"""

        summary = _llm_summary_markdown_from_response(result, response)

        self.assertIn("- 计划最大轮数：5", summary)
        self.assertIn("- 停止原因：reviewer_requested_stop", summary)
        self.assertIn("- writer 草稿摘要：压缩后的草稿摘要", summary)
        self.assertIn("- reviewer 评分：5", summary)
        self.assertIn("- 最终审查摘要：压缩后的最终审查", summary)


if __name__ == "__main__":
    unittest.main()
