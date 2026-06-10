import unittest

from office_revision.autogen_runner import _model_client_kwargs, _run_async_revision_loop
from office_revision.config import ModelSettings
from office_revision.workflow import RevisionRequest


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


if __name__ == "__main__":
    unittest.main()
