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


class InputInspectionTests(unittest.TestCase):
    def test_scanned_pdf_summary_warns_that_ocr_is_needed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scanned.pdf"
            write_blank_pdf(path)

            summary = inspect_input_file(path)

            self.assertEqual(summary.kind, "pdf")
            self.assertEqual(summary.extracted_chars, 0)
            self.assertIn("pdf_needs_ocr", summary.warnings)


if __name__ == "__main__":
    unittest.main()
