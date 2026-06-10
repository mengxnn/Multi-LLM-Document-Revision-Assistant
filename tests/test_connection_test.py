import unittest

from office_revision.config import ModelSettings
from office_revision.connection_test import validate_settings


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


if __name__ == "__main__":
    unittest.main()
