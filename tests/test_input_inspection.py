import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from office_revision.input_inspection import inspect_input_file


def write_blank_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)


def write_two_column_pdf(path: Path) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_textbox(
        fitz.Rect(40, 100, 270, 350),
        "Left column contains enough text for reliable layout detection.",
        fontsize=11,
    )
    page.insert_textbox(
        fitz.Rect(330, 100, 560, 350),
        "Right column also contains enough text for reliable layout detection.",
        fontsize=11,
    )
    document.save(path)
    document.close()


class InputInspectionTests(unittest.TestCase):
    def test_scanned_pdf_summary_warns_that_ocr_is_needed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scanned.pdf"
            write_blank_pdf(path)

            summary = inspect_input_file(path)

            self.assertEqual(summary.kind, "pdf")
            self.assertEqual(summary.extracted_chars, 0)
            self.assertIn("pdf_needs_ocr", summary.warnings)

    def test_two_column_pdf_summary_reports_layout_aware_extraction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "paper.pdf"
            write_two_column_pdf(path)

            summary = inspect_input_file(path)

            self.assertGreater(summary.extracted_chars, 0)
            self.assertIn("pdf_two_column", summary.warnings)


if __name__ == "__main__":
    unittest.main()
