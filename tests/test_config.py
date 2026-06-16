import os
import tempfile
import unittest
from pathlib import Path

from office_revision.config import (
    ModelSettings,
    load_env_file,
    load_role_settings,
    read_optional_text,
)


class ConfigTests(unittest.TestCase):
    def test_loads_key_value_pairs_without_overriding_existing_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "settings.env"
            config_path.write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=file-key",
                        "OPENAI_BASE_URL=https://example.test/v1",
                        "EMPTY_VALUE=",
                        "# comment",
                    ]
                ),
                encoding="utf-8",
            )
            old_key = os.environ.get("OPENAI_API_KEY")
            old_base_url = os.environ.get("OPENAI_BASE_URL")
            try:
                os.environ["OPENAI_API_KEY"] = "env-key"
                os.environ.pop("OPENAI_BASE_URL", None)

                loaded = load_env_file(config_path)

                self.assertEqual(os.environ["OPENAI_API_KEY"], "env-key")
                self.assertEqual(os.environ["OPENAI_BASE_URL"], "https://example.test/v1")
                self.assertEqual(loaded["OPENAI_API_KEY"], "file-key")
                self.assertNotIn("EMPTY_VALUE", os.environ)
            finally:
                if old_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = old_key
                if old_base_url is None:
                    os.environ.pop("OPENAI_BASE_URL", None)
                else:
                    os.environ["OPENAI_BASE_URL"] = old_base_url

    def test_reads_optional_text_or_returns_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prompt.md"
            path.write_text("custom prompt", encoding="utf-8")

            self.assertEqual(read_optional_text(path, "default"), "custom prompt")
            self.assertEqual(read_optional_text(Path(temp_dir) / "missing.md", "default"), "default")

    def test_loads_separate_writer_and_reviewer_settings(self):
        values = {
            "WRITER_API_KEY": "writer-key",
            "WRITER_BASE_URL": "https://writer.example/v1",
            "WRITER_MODEL": "writer-model",
            "REVIEWER_API_KEY": "reviewer-key",
            "REVIEWER_BASE_URL": "https://reviewer.example/v1",
            "REVIEWER_MODEL": "reviewer-model",
        }

        writer = load_role_settings(values, "WRITER", default_model="default-writer")
        reviewer = load_role_settings(values, "REVIEWER", default_model="default-reviewer")

        self.assertEqual(
            writer,
            ModelSettings(
                role="WRITER",
                api_key="writer-key",
                base_url="https://writer.example/v1",
                model="writer-model",
                model_family="unknown",
                vision=False,
                function_calling=False,
                json_output=False,
                structured_output=False,
            ),
        )
        self.assertEqual(reviewer.api_key, "reviewer-key")
        self.assertEqual(reviewer.base_url, "https://reviewer.example/v1")
        self.assertEqual(reviewer.model, "reviewer-model")

    def test_role_settings_fall_back_to_shared_openai_values(self):
        values = {
            "OPENAI_API_KEY": "shared-key",
            "OPENAI_BASE_URL": "https://shared.example/v1",
        }

        settings = load_role_settings(values, "WRITER", default_model="gpt-test")

        self.assertEqual(settings.api_key, "shared-key")
        self.assertEqual(settings.base_url, "https://shared.example/v1")
        self.assertEqual(settings.model, "gpt-test")

    def test_loads_model_info_capability_flags(self):
        values = {
            "WRITER_API_KEY": "writer-key",
            "WRITER_MODEL": "qwen-plus",
            "WRITER_ENABLE_SEARCH": "true",
            "WRITER_MODEL_FAMILY": "r1",
            "WRITER_VISION": "true",
            "WRITER_FUNCTION_CALLING": "false",
            "WRITER_JSON_OUTPUT": "true",
            "WRITER_STRUCTURED_OUTPUT": "false",
        }

        settings = load_role_settings(values, "WRITER", default_model="default-writer")

        self.assertEqual(settings.model_family, "r1")
        self.assertTrue(settings.enable_search)
        self.assertTrue(settings.vision)
        self.assertFalse(settings.function_calling)
        self.assertTrue(settings.json_output)
        self.assertFalse(settings.structured_output)

    def test_loads_role_specific_timeout_and_retry_settings(self):
        values = {
            "WRITER_API_KEY": "writer-key",
            "WRITER_MODEL": "writer-model",
            "WRITER_TIMEOUT_SECONDS": "120",
            "WRITER_MAX_RETRIES": "3",
        }

        settings = load_role_settings(values, "WRITER", default_model="default-writer")

        self.assertEqual(settings.timeout_seconds, 120)
        self.assertEqual(settings.max_retries, 3)

    def test_timeout_and_retry_settings_fall_back_to_shared_openai_values(self):
        values = {
            "OPENAI_API_KEY": "shared-key",
            "OPENAI_TIMEOUT_SECONDS": "75",
            "OPENAI_MAX_RETRIES": "2",
        }

        settings = load_role_settings(values, "REVIEWER", default_model="reviewer-model")

        self.assertEqual(settings.timeout_seconds, 75)
        self.assertEqual(settings.max_retries, 2)

    def test_timeout_and_retry_settings_default_when_missing(self):
        settings = load_role_settings({}, "WRITER", default_model="writer-model")

        self.assertEqual(settings.timeout_seconds, 60)
        self.assertEqual(settings.max_retries, 1)


if __name__ == "__main__":
    unittest.main()
