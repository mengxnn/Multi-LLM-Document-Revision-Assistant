from unittest import TestCase

from office_revision.application.contracts import ProgressEvent
from office_revision.web.runs import InMemoryRunStore


class InMemoryRunStoreTests(TestCase):
    def test_create_run_starts_as_queued(self):
        store = InMemoryRunStore()

        record = store.create_run(kind="start_project", project_id=None)

        self.assertEqual(record.status, "queued")
        self.assertEqual(record.kind, "start_project")
        self.assertIsNone(record.project_id)
        self.assertEqual(record.events, ())

    def test_append_event_preserves_order(self):
        store = InMemoryRunStore()
        record = store.create_run(kind="continue_revision", project_id="demo")

        store.mark_running(record.run_id)
        store.append_event(
            record.run_id,
            ProgressEvent(stage="reading_inputs", message="读取输入文件"),
        )
        store.append_event(
            record.run_id,
            ProgressEvent(stage="completed", message="运行完成"),
        )

        updated = store.get_run(record.run_id)

        self.assertEqual(updated.status, "running")
        self.assertEqual(
            [event.stage for event in updated.events],
            ["reading_inputs", "completed"],
        )

    def test_mark_failed_records_error_and_stage(self):
        store = InMemoryRunStore()
        record = store.create_run(kind="start_project", project_id=None)

        store.mark_failed(
            record.run_id,
            stage="validation",
            message="requirements is required",
        )

        updated = store.get_run(record.run_id)

        self.assertEqual(updated.status, "failed")
        self.assertEqual(
            updated.error,
            {"stage": "validation", "message": "requirements is required"},
        )
        self.assertIsNotNone(updated.finished_at)
