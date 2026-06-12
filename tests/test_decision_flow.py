import json
import tempfile
import unittest
from pathlib import Path

from office_revision.decision_flow import apply_session_decision, decision_dir_name


class DecisionFlowTests(unittest.TestCase):
    def test_decision_dir_name_replaces_pending_label(self):
        self.assertEqual(
            decision_dir_name("193728-pending-v1", "accept"),
            "193728-accept-v1",
        )
        self.assertEqual(
            decision_dir_name("193728-pending-v1", "abandon"),
            "193728-abandon-v1",
        )
        self.assertEqual(
            decision_dir_name("193728-pending-v1", "continue"),
            "193728-continue-v1",
        )

    def test_decision_dir_name_can_change_existing_decision(self):
        self.assertEqual(
            decision_dir_name("193728-accept-v1", "abandon"),
            "193728-abandon-v1",
        )
        self.assertEqual(
            decision_dir_name("193728-abandon-v1", "accept"),
            "193728-accept-v1",
        )

    def test_accept_renames_pending_directory_and_updates_latest_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            (output_root / "latest").mkdir()
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            result = apply_session_decision(output_root, "accept")

            self.assertEqual(result.status, "accept")
            self.assertEqual(result.session_dir.name, "193728-accept-v1")
            self.assertTrue(result.session_dir.exists())
            self.assertFalse(session.exists())
            latest_session = json.loads((output_root / "latest_session.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(latest_session["session_dir"]), result.session_dir)
            status = json.loads((result.session_dir / "session_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "accept")

    def test_abandon_can_rename_previously_accepted_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            session = output_root / "193728-accept-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            result = apply_session_decision(output_root, "abandon")

            self.assertEqual(result.status, "abandon")
            self.assertTrue(result.renamed)
            self.assertEqual(result.session_dir.name, "193728-abandon-v1")
            self.assertTrue(result.session_dir.exists())
            self.assertFalse(session.exists())

    def test_continue_renames_pending_directory_and_reminds_next_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            result = apply_session_decision(output_root, "continue")

            self.assertEqual(result.status, "continue")
            self.assertEqual(result.session_dir.name, "193728-continue-v1")
            self.assertIn("--continue-project", result.message)

    def test_skip_keeps_pending_directory_and_returns_reminder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            session = output_root / "193728-pending-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            result = apply_session_decision(output_root, "skip")

            self.assertEqual(result.status, "pending")
            self.assertEqual(result.session_dir, session)
            self.assertIn("--review-project", result.message)
            self.assertTrue(session.exists())
            status = json.loads((session / "session_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "pending")

    def test_skip_renames_accepted_directory_back_to_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "outputs"
            session = output_root / "193728-accept-v1"
            session.mkdir(parents=True)
            (output_root / "latest_session.json").write_text(
                json.dumps({"session_dir": str(session)}),
                encoding="utf-8",
            )

            result = apply_session_decision(output_root, "skip")

            self.assertEqual(result.status, "pending")
            self.assertEqual(result.session_dir.name, "193728-pending-v1")
            self.assertTrue(result.session_dir.exists())
            self.assertFalse(session.exists())


if __name__ == "__main__":
    unittest.main()
