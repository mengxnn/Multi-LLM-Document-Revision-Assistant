import asyncio
import contextlib
import io
import unittest

from office_revision.autogen_runner import _run_role_task
from office_revision.config import ModelSettings


class AutogenLoggingTests(unittest.TestCase):
    def test_failed_role_task_prints_effective_timeout_and_exception_type(self):
        settings = ModelSettings(
            role="WRITER",
            api_key="secret",
            base_url="https://example.com/v1",
            model="writer-model",
            timeout_seconds=180,
            max_retries=2,
        )

        async def fail():
            raise TimeoutError("upstream closed")

        stream = io.StringIO()
        with self.assertRaises(TimeoutError):
            with contextlib.redirect_stdout(stream):
                asyncio.run(_run_role_task("writer", 1, settings, fail))

        output = stream.getvalue()

        self.assertIn("timeout=180s", output)
        self.assertIn("max_retries=2", output)
        self.assertIn("TimeoutError", output)
        self.assertIn("config/model_profiles.json", output)


if __name__ == "__main__":
    unittest.main()
