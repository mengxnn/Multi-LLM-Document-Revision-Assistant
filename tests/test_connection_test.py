import unittest
from unittest.mock import patch

from office_revision.config import ModelSettings
from office_revision.connection_test import check_openai_compatible_connection, validate_settings


class ConnectionTestTests(unittest.TestCase):
    def test_validate_settings_requires_api_key(self):
        result = validate_settings(
            ModelSettings(
                role="WRITER",
                api_key="",
                base_url="",
                model="writer-model",
                model_family="unknown",
                vision=False,
                function_calling=False,
                json_output=False,
                structured_output=False,
            )
        )

        self.assertIsNotNone(result)
        self.assertFalse(result.ok)
        self.assertIn("WRITER_API_KEY", result.message)
        self.assertEqual(result.elapsed_seconds, 0.0)

    def test_validate_settings_accepts_complete_settings(self):
        result = validate_settings(
            ModelSettings(
                role="REVIEWER",
                api_key="key",
                base_url="",
                model="reviewer-model",
                model_family="unknown",
                vision=False,
                function_calling=False,
                json_output=False,
                structured_output=False,
            )
        )

        self.assertIsNone(result)

    def test_check_connection_reports_success_elapsed_time(self):
        class FakeResponse:
            def __init__(self):
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})]

        class FakeCompletions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return FakeResponse()

        class FakeChat:
            def __init__(self):
                self.completions = FakeCompletions()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.chat = FakeChat()

        settings = ModelSettings(
            role="WRITER",
            api_key="key",
            base_url="https://writer.example/v1",
            model="writer-model",
            timeout_seconds=45,
            max_retries=2,
        )

        with patch.dict("sys.modules", {"openai": type("OpenAIModule", (), {"OpenAI": FakeOpenAI})}):
            with patch("office_revision.connection_test.time.perf_counter", side_effect=[1.0, 4.25]):
                result = check_openai_compatible_connection(settings)

        self.assertTrue(result.ok)
        self.assertEqual(result.elapsed_seconds, 3.25)
        self.assertIn("search=off", result.message)

    def test_check_connection_reports_failure_elapsed_time(self):
        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.chat = type(
                    "FakeChat",
                    (),
                    {
                        "completions": type(
                            "FakeCompletions",
                            (),
                            {"create": staticmethod(lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))}
                        )()
                    },
                )()

        settings = ModelSettings(
            role="REVIEWER",
            api_key="key",
            base_url="",
            model="reviewer-model",
        )

        with patch.dict("sys.modules", {"openai": type("OpenAIModule", (), {"OpenAI": FakeOpenAI})}):
            with patch("office_revision.connection_test.time.perf_counter", side_effect=[5.0, 7.5]):
                result = check_openai_compatible_connection(settings)

        self.assertFalse(result.ok)
        self.assertEqual(result.elapsed_seconds, 2.5)
        self.assertIn("RuntimeError: boom", result.message)


if __name__ == "__main__":
    unittest.main()
