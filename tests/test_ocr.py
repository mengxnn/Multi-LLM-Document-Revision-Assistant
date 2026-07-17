import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from office_revision.ocr import (
    _candidate_tesseract_commands,
    _configure_tesseract_command,
    check_ocr_environment,
)


class FakePytesseractPackage:
    class pytesseract:
        tesseract_cmd = ""

    @staticmethod
    def get_tesseract_version():
        return "5.5.0"

    @staticmethod
    def get_languages(config=""):
        return ["eng", "chi_sim", "osd"]


class OcrConfigurationTests(TestCase):
    def test_ocr_environment_reports_path_version_and_languages(self):
        with TemporaryDirectory() as temp_dir:
            command = Path(temp_dir) / "tesseract.exe"
            command.write_text("", encoding="utf-8")
            fake_module = FakePytesseractPackage()
            fake_module.pytesseract.tesseract_cmd = str(command)

            status = check_ocr_environment(fake_module)

            self.assertTrue(status["ok"])
            self.assertEqual(status["path"], str(command.resolve()))
            self.assertEqual(status["version"], "5.5.0")
            self.assertIn("chi_sim", status["languages"])
            self.assertEqual(status["missing_languages"], [])

    def test_ocr_environment_reports_missing_language_package(self):
        with TemporaryDirectory() as temp_dir:
            command = Path(temp_dir) / "tesseract.exe"
            command.write_text("", encoding="utf-8")
            fake_module = FakePytesseractPackage()
            fake_module.pytesseract.tesseract_cmd = str(command)
            fake_module.get_languages = lambda config="": ["eng"]

            status = check_ocr_environment(fake_module)

            self.assertFalse(status["ok"])
            self.assertEqual(status["missing_languages"], ["chi_sim"])
            self.assertIn("chi_sim", status["message"])

    def test_ocr_environment_reports_missing_tesseract_program(self):
        fake_module = FakePytesseractPackage()
        with mock.patch("office_revision.ocr._candidate_tesseract_commands", return_value=[]):
            with mock.patch("office_revision.ocr.shutil.which", return_value=None):
                status = check_ocr_environment(fake_module)

        self.assertFalse(status["ok"])
        self.assertIsNone(status["path"])
        self.assertIn("未找到", status["message"])

    def test_portable_tools_tesseract_path_is_checked_before_system_paths(self):
        original = os.environ.get("TESSERACT_CMD")
        try:
            os.environ.pop("TESSERACT_CMD", None)

            candidates = _candidate_tesseract_commands()

            self.assertEqual(candidates[0], Path("tools") / "tesseract" / "tesseract.exe")
            self.assertIn(Path(r"E:\Tesseract-OCR\tesseract.exe"), candidates)
        finally:
            if original is not None:
                os.environ["TESSERACT_CMD"] = original

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
