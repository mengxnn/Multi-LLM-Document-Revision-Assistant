import tempfile
import unittest
from pathlib import Path

from docx import Document

from office_revision.document_io import read_source_text, write_final_docx


class DocumentIoTests(unittest.TestCase):
    def test_reads_docx_headings_paragraphs_and_tables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "source.docx"
            document = Document()
            document.add_heading("项目实施方案", level=1)
            document.add_paragraph("本项目用于提升文档修改效率。")
            table = document.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "阶段"
            table.cell(0, 1).text = "产出"
            table.cell(1, 0).text = "第一阶段"
            table.cell(1, 1).text = "原型"
            document.save(path)

            text = read_source_text(path)

            self.assertIn("# 项目实施方案", text)
            self.assertIn("本项目用于提升文档修改效率。", text)
            self.assertIn("| 阶段 | 产出 |", text)
            self.assertIn("| 第一阶段 | 原型 |", text)

    def test_writes_docx_from_markdown_like_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "final.docx"

            write_final_docx(
                "\n".join(
                    [
                        "# 修改稿",
                        "",
                        "这是正文段落。",
                        "",
                        "| 阶段 | 产出 |",
                        "| 第一阶段 | 原型 |",
                    ]
                ),
                output,
            )

            document = Document(output)
            self.assertEqual(document.paragraphs[0].text, "修改稿")
            self.assertTrue(document.paragraphs[0].style.name.startswith("Heading"))
            self.assertIn("这是正文段落。", [item.text for item in document.paragraphs])
            self.assertEqual(document.tables[0].cell(0, 0).text, "阶段")
            self.assertEqual(document.tables[0].cell(1, 1).text, "原型")


    def test_writes_markdown_formatting_as_real_docx_formatting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "final.docx"

            write_final_docx(
                "\n".join(
                    [
                        "# Plan",
                        "",
                        "This project lasts **six months**.",
                        "",
                        "| Phase | Work |",
                        "| :--- | :--- |",
                        "| **Phase 1** | Line one<br>Line two |",
                    ]
                ),
                output,
            )

            document = Document(output)
            paragraph = next(item for item in document.paragraphs if "six months" in item.text)
            self.assertEqual(paragraph.text, "This project lasts six months.")
            self.assertTrue(any(run.text == "six months" and run.bold for run in paragraph.runs))
            table = document.tables[0]
            self.assertEqual(len(table.rows), 2)
            self.assertEqual(table.cell(1, 0).text, "Phase 1")
            self.assertNotIn("**", table.cell(1, 0).text)
            self.assertNotIn(":---", table.cell(1, 0).text)
            self.assertIn("Line one\nLine two", table.cell(1, 1).text)

    def test_skips_standalone_markdown_horizontal_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "final.docx"

            write_final_docx(
                "\n".join(
                    [
                        "# Plan",
                        "---",
                        "First paragraph.",
                        "------",
                        "Second paragraph.",
                    ]
                ),
                output,
            )

            document = Document(output)
            paragraph_text = [item.text for item in document.paragraphs]
            self.assertNotIn("---", paragraph_text)
            self.assertNotIn("------", paragraph_text)
            self.assertIn("First paragraph.", paragraph_text)
            self.assertIn("Second paragraph.", paragraph_text)


if __name__ == "__main__":
    unittest.main()
