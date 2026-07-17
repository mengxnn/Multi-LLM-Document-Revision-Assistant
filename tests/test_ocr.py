import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import fitz

from office_revision.ocr import (
    _candidate_tesseract_commands,
    _configure_tesseract_command,
    _ocr_data_to_lines,
    check_ocr_environment,
    read_pdf_text_with_ocr,
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


class FakeLayoutOcrPackage(FakePytesseractPackage):
    class Output:
        DICT = "dict"

    class TesseractNotFoundError(Exception):
        pass

    class TesseractError(Exception):
        pass

    ocr_data = {}

    @classmethod
    def image_to_data(cls, image_path, *, lang, output_type):
        return cls.ocr_data


def make_ocr_data(rows):
    data = {
        "text": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
        "word_num": [],
    }
    for row in rows:
        text, left, top, width, height, block_num, line_num = row
        data["text"].append(text)
        data["left"].append(left)
        data["top"].append(top)
        data["width"].append(width)
        data["height"].append(height)
        data["block_num"].append(block_num)
        data["par_num"].append(1)
        data["line_num"].append(line_num)
        data["word_num"].append(1)
    return data


class OcrConfigurationTests(TestCase):
    def test_ocr_data_is_split_and_sorted_by_two_column_layout(self):
        data = make_ocr_data(
            [
                ("FULL WIDTH TITLE", 390, 50, 420, 30, 1, 1),
                ("RIGHT COLUMN CONTENT IS RETURNED FIRST BY OCR", 700, 220, 380, 30, 2, 1),
                ("LEFT COLUMN CONTENT MUST BE READ BEFORE THE RIGHT", 80, 220, 380, 30, 2, 1),
                ("FULL WIDTH FOOTER", 400, 1400, 400, 25, 3, 1),
            ]
        )

        lines = _ocr_data_to_lines(data, page_width=1200)

        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[1].text, "LEFT COLUMN CONTENT MUST BE READ BEFORE THE RIGHT")
        self.assertEqual(lines[2].text, "RIGHT COLUMN CONTENT IS RETURNED FIRST BY OCR")

    def test_scanned_two_column_pdf_uses_visual_reading_order(self):
        data = make_ocr_data(
            [
                ("FULL WIDTH TITLE", 390, 50, 420, 30, 1, 1),
                ("RIGHT COLUMN CONTENT IS RETURNED FIRST BY OCR", 700, 220, 380, 30, 2, 1),
                ("LEFT COLUMN CONTENT MUST BE READ BEFORE THE RIGHT", 80, 220, 380, 30, 2, 1),
                ("FULL WIDTH FOOTER", 400, 1400, 400, 25, 3, 1),
            ]
        )
        FakeLayoutOcrPackage.ocr_data = data
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scanned.pdf"
            document = fitz.open()
            document.new_page(width=600, height=800)
            document.save(path)
            document.close()

            text = read_pdf_text_with_ocr(
                path,
                pytesseract_module=FakeLayoutOcrPackage,
            )

        self.assertLess(text.index("FULL WIDTH TITLE"), text.index("LEFT COLUMN"))
        self.assertLess(text.index("LEFT COLUMN"), text.index("RIGHT COLUMN"))
        self.assertLess(text.index("RIGHT COLUMN"), text.index("FULL WIDTH FOOTER"))
        self.assertIn("layout: two-column", text)

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
                fake_module.pytesseract.tesseract_cmd = ""

                _configure_tesseract_command(fake_module)

                self.assertEqual(fake_module.pytesseract.tesseract_cmd, str(command))
        finally:
            if original is None:
                os.environ.pop("TESSERACT_CMD", None)
            else:
                os.environ["TESSERACT_CMD"] = original
