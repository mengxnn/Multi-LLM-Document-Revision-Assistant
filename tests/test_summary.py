import tempfile
import unittest
from pathlib import Path

from docx import Document

from office_revision.summary import build_changes_summary, extract_manual_attention_items, write_changes_summary
from office_revision.workflow import RevisionPass, RevisionRequest, RevisionResult


class SummaryTests(unittest.TestCase):
    def test_extracts_manual_attention_items_from_final_text_and_review(self):
        items = extract_manual_attention_items(
            "\n".join(
                [
                    "项目预算为【需补充：预算依据】。",
                    "完成时间待确认。",
                    "普通句子。",
                ]
            ),
            "审查意见：需核实政策依据。TODO: 补充附件。",
        )

        self.assertEqual(len(items), 4)
        self.assertTrue(any("预算依据" in item for item in items))
        self.assertTrue(any("待确认" in item for item in items))
        self.assertTrue(any("需核实" in item for item in items))
        self.assertTrue(any("TODO" in item for item in items))

    def test_builds_changes_summary_with_run_overview_inputs_rounds_and_final_conclusion(self):
        result = RevisionResult(
            request=RevisionRequest(
                source_text="source text",
                requirements="Improve the plan.",
                meeting_notes="Meeting asked for timeline.",
                cycles=3,
                title="source",
                source_path="inputs/source.docx",
                meeting_notes_path="inputs/meeting_notes.md",
            ),
            passes=[
                RevisionPass(
                    cycle_index=1,
                    draft="Round one draft with 【需补充：联系人】.",
                    review="是否继续修改：是\n总体评分：3\n五、给 writer 的修改指令\n1. Add timeline.",
                    review_continue=True,
                    review_score=3,
                    writer_instructions="1. Add timeline.",
                ),
                RevisionPass(
                    cycle_index=2,
                    draft="Final draft.",
                    review="是否继续修改：否\n总体评分：5\n结论说明：基本满足要求。",
                    review_continue=False,
                    review_score=5,
                    writer_instructions="",
                ),
            ],
            stopped_early=True,
            stop_reason="reviewer_requested_stop",
        )

        summary = build_changes_summary(result)

        self.assertIn("# 修改说明汇总", summary)
        self.assertIn("一、运行概况", summary)
        self.assertIn("实际完成轮数：2", summary)
        self.assertIn("是否提前停止：是", summary)
        self.assertIn("二、输入材料", summary)
        self.assertIn("初稿来源：inputs/source.docx", summary)
        self.assertIn("会议纪要来源：inputs/meeting_notes.md", summary)
        self.assertIn("三、每轮修改与审查摘要", summary)
        self.assertIn("第 1 轮", summary)
        self.assertIn("Add timeline", summary)
        self.assertIn("四、最终结论", summary)
        self.assertIn("最终评分：5", summary)
        self.assertIn("五、需人工补充或核实事项", summary)
        self.assertIn("联系人", summary)

    def test_write_changes_summary_outputs_md_and_docx(self):
        result = RevisionResult(
            request=RevisionRequest(source_text="", requirements="Write from scratch.", cycles=1),
            passes=[
                RevisionPass(
                    cycle_index=1,
                    draft="Draft.",
                    review="是否继续修改：否\n总体评分：4",
                    review_continue=False,
                    review_score=4,
                )
            ],
            stopped_early=True,
            stop_reason="reviewer_requested_stop",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            write_changes_summary(result, output_dir)

            self.assertTrue((output_dir / "changes_summary.md").exists())
            self.assertTrue((output_dir / "changes_summary.docx").exists())
            document = Document(output_dir / "changes_summary.docx")
            self.assertTrue(any("修改说明汇总" in paragraph.text for paragraph in document.paragraphs))


if __name__ == "__main__":
    unittest.main()
