import unittest

from office_revision.workflow import RevisionRequest, run_revision_loop


class WorkflowTests(unittest.TestCase):
    def test_runs_requested_writer_reviewer_cycles(self):
        calls = []

        def writer(context):
            calls.append(("writer", context.cycle_index, context.previous_review))
            return f"draft-{context.cycle_index}: {context.requirements}"

        def reviewer(context):
            calls.append(("reviewer", context.cycle_index, context.draft))
            return f"review-{context.cycle_index}: check {context.draft}"

        request = RevisionRequest(
            source_text="原方案：建设一个系统。",
            requirements="补充实施步骤，语气正式。",
            cycles=2,
        )

        result = run_revision_loop(request, writer=writer, reviewer=reviewer)

        self.assertEqual(result.final_text, "draft-2: 补充实施步骤，语气正式。")
        self.assertEqual(result.final_review, "review-2: check draft-2: 补充实施步骤，语气正式。")
        self.assertEqual(len(result.passes), 2)
        self.assertEqual(
            [call[0] for call in calls],
            ["writer", "reviewer", "writer", "reviewer"],
        )
        self.assertIn("review-1", calls[2][2])

    def test_rejects_non_positive_cycles(self):
        request = RevisionRequest(
            source_text="文本",
            requirements="要求",
            cycles=0,
        )

        with self.assertRaises(ValueError):
            run_revision_loop(request, writer=lambda context: "", reviewer=lambda context: "")

    def test_stops_early_when_reviewer_says_no_more_revision(self):
        writer_contexts = []

        def writer(context):
            writer_contexts.append(context)
            return f"draft-{context.cycle_index}"

        def reviewer(context):
            return """一、总体结论
是否继续修改：否
总体评分：5

五、给 writer 的修改指令
无需继续修改。
"""

        result = run_revision_loop(
            RevisionRequest(source_text="source", requirements="requirements", cycles=3),
            writer=writer,
            reviewer=reviewer,
        )

        self.assertEqual(len(result.passes), 1)
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.stop_reason, "reviewer_requested_stop")
        self.assertIs(result.passes[0].review_continue, False)
        self.assertEqual(result.passes[0].review_score, 5)
        self.assertIn("无需继续修改", result.passes[0].writer_instructions)
        self.assertEqual(len(writer_contexts), 1)

    def test_next_writer_gets_extracted_writer_instructions(self):
        seen_contexts = []

        def writer(context):
            seen_contexts.append(context)
            return f"draft-{context.cycle_index}"

        def reviewer(context):
            if context.cycle_index == 1:
                return """一、总体结论
是否继续修改：是
总体评分：3

五、给 writer 的修改指令
1. 补充预算依据。
2. 调整语气。
"""
            return "是否继续修改：否"

        run_revision_loop(
            RevisionRequest(source_text="source", requirements="requirements", cycles=2),
            writer=writer,
            reviewer=reviewer,
        )

        self.assertIn("补充预算依据", seen_contexts[1].previous_writer_instructions)
        self.assertIn("调整语气", seen_contexts[1].previous_writer_instructions)


    def test_writer_and_reviewer_receive_optional_meeting_notes(self):
        seen_writer_contexts = []
        seen_reviewer_contexts = []

        def writer(context):
            seen_writer_contexts.append(context)
            return "draft"

        def reviewer(context):
            seen_reviewer_contexts.append(context)
            return "是否继续修改：否"

        run_revision_loop(
            RevisionRequest(
                source_text="",
                requirements="Write a project plan.",
                meeting_notes="Meeting decided to add a timeline.",
                cycles=1,
            ),
            writer=writer,
            reviewer=reviewer,
        )

        self.assertEqual(seen_writer_contexts[0].source_text, "")
        self.assertIn("timeline", seen_writer_contexts[0].meeting_notes)
        self.assertIn("timeline", seen_reviewer_contexts[0].meeting_notes)

    def test_later_cycles_use_previous_draft_review_and_omit_initial_source_materials(self):
        seen_writer_contexts = []
        seen_reviewer_contexts = []

        def writer(context):
            seen_writer_contexts.append(context)
            return f"draft-{context.cycle_index}"

        def reviewer(context):
            seen_reviewer_contexts.append(context)
            return "是否继续修改：是" if context.cycle_index == 1 else "是否继续修改：否"

        run_revision_loop(
            RevisionRequest(
                source_text="initial source should only be read in round 1",
                requirements="initial requirements stay available",
                meeting_notes="meeting notes should only be read in round 1",
                cycles=2,
            ),
            writer=writer,
            reviewer=reviewer,
        )

        self.assertIn("initial source", seen_writer_contexts[0].source_text)
        self.assertEqual(seen_writer_contexts[1].source_text, "")
        self.assertEqual(seen_writer_contexts[1].meeting_notes, "")
        self.assertEqual(seen_writer_contexts[1].previous_draft, "draft-1")
        self.assertIn("是否继续修改", seen_writer_contexts[1].previous_review)
        self.assertEqual(seen_reviewer_contexts[1].source_text, "")
        self.assertEqual(seen_reviewer_contexts[1].meeting_notes, "")
        self.assertIn("是否继续修改", seen_reviewer_contexts[1].previous_review)


if __name__ == "__main__":
    unittest.main()
