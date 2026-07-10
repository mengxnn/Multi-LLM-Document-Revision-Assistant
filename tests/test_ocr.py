import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from office_revision.ocr import _configure_tesseract_command


class FakePytesseractPackage:
    class pytesseract:
        tesseract_cmd = ""


class OcrConfigurationTests(TestCase):
    def test_tesseract_cmd_environment_variable_is_used(self):
        original = os.environ.get("TESSERACT_CMD")
        try:
            with TemporaryDirectory() as temp_dir:
                command = Path(temp_dir) / "tesseract.exe"
                command.write_text("", encoding="utf-8")
                os.environ["TESSERACT_CMD"] = str(command)
                fake_module = FakePytesseractPackage()

                _configure_tesseract_command(fake_module)

                self.assertEqual(fake_module.pytesseract.tesseract_cmd, str(command))
        finally:
            if original is None:
                os.environ.pop("TESSERACT_CMD", None)
            else:
                os.environ["TESSERACT_CMD"] = original

