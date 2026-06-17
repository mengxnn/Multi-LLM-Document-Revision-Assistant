import tempfile
import unittest
from pathlib import Path

from office_revision.summary import (
    SUMMARY_HEADINGS,
    build_final_review_report,
    build_changes_summary,
    build_llm_polished_changes_summary,
    build_llm_summary_prompt,
    extract_manual_attention_items,
    has_required_summary_headings,
    parse_llm_summary_polish,
    write_final_review_report,
    write_revision_summary,
)
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

    def test_write_revision_summary_outputs_md_and_docx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            write_revision_summary("# 修改说明汇总\n\ncontent", output_dir)

            self.assertTrue((output_dir / "revision_summary.md").exists())
            self.assertTrue((output_dir / "revision_summary.docx").exists())

    def test_builds_and_writes_final_review_report(self):
        result = RevisionResult(
            request=RevisionRequest(source_text="", requirements="Write from scratch.", cycles=1),
            passes=[
                RevisionPass(
                    cycle_index=1,
                    draft="Final draft with 【需补充：联系人】.",
                    review="是否继续修改：否\n总体评分：4\n格式风险：表格需检查。\n事实风险：数据来源需核实。",
                    review_continue=False,
                    review_score=4,
                )
            ],
        )

        report = build_final_review_report(result)

        self.assertIn("# 最终人工复核报告", report)
        self.assertIn("一、最终结论", report)
        self.assertIn("事实风险", report)
        self.assertIn("格式风险", report)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            write_final_review_report(result, output_dir)

            self.assertTrue((output_dir / "final_review_report.md").exists())
            self.assertTrue((output_dir / "final_review_report.docx").exists())

    def test_validates_required_summary_headings_in_order(self):
        valid_summary = "\n\n".join(SUMMARY_HEADINGS)
        invalid_summary = "\n\n".join([SUMMARY_HEADINGS[0], SUMMARY_HEADINGS[2], SUMMARY_HEADINGS[1]])

        self.assertTrue(has_required_summary_headings(valid_summary))
        self.assertFalse(has_required_summary_headings(invalid_summary))
        self.assertFalse(has_required_summary_headings("# 修改说明汇总\n\n## 一、运行概况"))

    def test_builds_llm_summary_prompt_for_compressing_long_fields_only(self):
        result = RevisionResult(
            request=RevisionRequest(
                source_text="Original source.",
                requirements="Improve timeline.",
                meeting_notes="Meeting asked for risk controls.",
                cycles=1,
                source_path="inputs/source.docx",
                meeting_notes_path="inputs/meeting_notes.md",
            ),
            passes=[
                RevisionPass(
                    cycle_index=1,
                    draft="Final draft content.",
                    review="是否继续修改：否\n总体评分：5\n结论说明：基本满足要求。",
                    review_continue=False,
                    review_score=5,
                    writer_instructions="",
                )
            ],
            stopped_early=True,
            stop_reason="reviewer_requested_stop",
        )
        rule_summary = build_changes_summary(result)

        prompt = build_llm_summary_prompt(result, rule_summary)

        for heading in SUMMARY_HEADINGS:
            self.assertIn(heading, prompt)
        self.assertIn("只压缩长文本字段", prompt)
        self.assertIn("不要改写运行事实", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn("Original source.", prompt)
        self.assertIn("Meeting asked for risk controls.", prompt)
        self.assertIn("Final draft content.", prompt)
        self.assertIn(rule_summary, prompt)

    def test_builds_llm_polished_summary_with_rule_facts_and_compressed_long_fields(self):
        result = RevisionResult(
            request=RevisionRequest(
                source_text="source text",
                requirements="Improve it.",
                cycles=5,
                source_path="inputs/source.docx",
            ),
            passes=[
                RevisionPass(
                    cycle_index=1,
                    draft="Original long draft.",
                    review="Long review.",
                    review_continue=True,
                    review_score=3,
                    writer_instructions="Long instructions.",
                ),
                RevisionPass(
                    cycle_index=2,
                    draft="Final draft.",
                    review="Final review.",
                    review_continue=False,
                    review_score=5,
                    writer_instructions="Polish punctuation.",
                ),
            ],
            stopped_early=True,
            stop_reason="reviewer_requested_stop",
        )
        polish = {
            "rounds": [
                {
                    "cycle_index": 1,
                    "writer_draft_summary": "明确了输入输出，但仍有元评论。",
                    "reviewer_review_summary": "要求删除元评论并降低事实风险。",
                    "writer_instructions_summary": "删除元评论，调整引用表述。",
                },
                {
                    "cycle_index": 2,
                    "writer_draft_summary": "补齐标题并完成核心修改。",
                    "reviewer_review_summary": "认为基本满足要求。",
                    "writer_instructions_summary": "仅需最后校对。",
                },
            ],
            "final_review_summary": "最终审查认为核心要求已满足，仍需人工校对格式和事实。",
            "manual_attention_summary": "未发现显式标记；建议人工核对事实、术语和格式。",
        }

        summary = build_llm_polished_changes_summary(result, polish)

        self.assertIn("- 计划最大轮数：5", summary)
        self.assertIn("- 实际完成轮数：2", summary)
        self.assertIn("- 停止原因：reviewer_requested_stop", summary)
        self.assertIn("- 初稿来源：inputs/source.docx", summary)
        self.assertIn("- 修改要求来源：requirements.md 或命令行指定文件", summary)
        self.assertIn("- writer 草稿摘要：明确了输入输出，但仍有元评论。", summary)
        self.assertIn("- 是否继续修改：是", summary)
        self.assertIn("- reviewer 评分：3", summary)
        self.assertIn("- 最终评分：5", summary)
        self.assertIn("- 最终审查摘要：最终审查认为核心要求已满足，仍需人工校对格式和事实。", summary)
        self.assertIn("- 显式标记检查：未发现显式标记；建议人工核对事实、术语和格式。", summary)

    def test_parses_llm_summary_polish_json_from_plain_or_fenced_response(self):
        plain = '{"rounds": [], "final_review_summary": "ok", "manual_attention_summary": "none"}'
        fenced = "```json\n" + plain + "\n```"

        self.assertEqual(parse_llm_summary_polish(plain)["final_review_summary"], "ok")
        self.assertEqual(parse_llm_summary_polish(fenced)["manual_attention_summary"], "none")

if __name__ == "__main__":
    unittest.main()
