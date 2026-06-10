import unittest

from office_revision.dry_run import dry_run_reviewer, dry_run_writer
from office_revision.workflow import ReviewContext, WriterContext


class DryRunTests(unittest.TestCase):
    def test_writer_includes_requirements_source_and_prior_review(self):
        draft = dry_run_writer(
            WriterContext(
                source_text="原文第一段很短。",
                requirements="扩写并保持正式。",
                cycle_index=2,
                previous_draft="上一稿",
                previous_review="上一轮建议：增加时间表。",
            )
        )

        self.assertIn("第 2 轮修改稿", draft)
        self.assertIn("扩写并保持正式", draft)
        self.assertIn("增加时间表", draft)
        self.assertIn("原文第一段很短", draft)

    def test_reviewer_returns_structured_report(self):
        review = dry_run_reviewer(
            ReviewContext(
                source_text="原文",
                requirements="补充预算依据。",
                cycle_index=1,
                draft="修改稿包含实施步骤。",
            )
        )

        self.assertIn("一、总体结论", review)
        self.assertIn("是否继续修改：是", review)
        self.assertIn("总体评分：3", review)
        self.assertIn("五、给 writer 的修改指令", review)
        self.assertIn("补充预算依据", review)


if __name__ == "__main__":
    unittest.main()
