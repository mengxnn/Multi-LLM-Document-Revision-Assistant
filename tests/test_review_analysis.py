import unittest

from office_revision.review_analysis import parse_review_decision


class ReviewAnalysisTests(unittest.TestCase):
    def test_parses_continue_flag_score_and_writer_instructions(self):
        review = """一、总体结论
是否继续修改：否
总体评分：5
结论说明：已经达到提交标准。

二、修改要求落实情况
整体已落实。

五、给 writer 的修改指令
1. 保留当前结构。
2. 只检查错别字。
"""

        decision = parse_review_decision(review)

        self.assertIs(decision.continue_revision, False)
        self.assertEqual(decision.score, 5)
        self.assertIn("保留当前结构", decision.writer_instructions)
        self.assertIn("只检查错别字", decision.writer_instructions)

    def test_parses_next_round_list_as_fallback_instructions(self):
        review = """一、总体结论
是否继续修改：是
总体评分：3

四、下一轮修改清单
1. 补充实施周期。
2. 增加验收标准。
"""

        decision = parse_review_decision(review)

        self.assertIs(decision.continue_revision, True)
        self.assertEqual(decision.score, 3)
        self.assertIn("补充实施周期", decision.writer_instructions)

    def test_unknown_continue_flag_is_safe_fallback(self):
        decision = parse_review_decision("总体看起来可以，但还需人工判断。")

        self.assertIsNone(decision.continue_revision)
        self.assertIsNone(decision.score)
        self.assertEqual(decision.writer_instructions, "")


if __name__ == "__main__":
    unittest.main()
