from pathlib import Path
from unittest import TestCase

from office_revision.application.contracts import (
    ArtifactLinks,
    ProjectSummary,
    RevisionRunResult,
)
from office_revision.web.schemas import (
    path_to_string,
    project_summary_to_dict,
    revision_result_to_dict,
)


class WebSchemaTests(TestCase):
    def test_path_to_string_returns_none_for_missing_path(self):
        self.assertIsNone(path_to_string(None))

    def test_path_to_string_normalizes_path_for_json(self):
        self.assertEqual(path_to_string(Path("projects/example")), "projects/example")

    def test_project_summary_to_dict_serializes_path(self):
        summary = ProjectSummary(
            project_id="demo_20260627",
            title="Demo",
            created_date="20260627",
            path=Path("projects/demo_20260627"),
            latest_status="pending",
            latest_version=1,
            latest_mode="dry-run",
        )

        payload = project_summary_to_dict(summary)

        self.assertEqual(payload["project_id"], "demo_20260627")
        self.assertEqual(payload["path"], "projects/demo_20260627")
        self.assertEqual(payload["latest_version"], 1)

    def test_revision_result_to_dict_serializes_artifacts_and_warnings(self):
        result = RevisionRunResult(
            project_id="demo_20260627",
            project_path=Path("projects/demo_20260627"),
            version=1,
            version_path=Path("projects/demo_20260627/outputs/100000-pending-v1"),
            latest_path=Path("projects/demo_20260627/latest"),
            status="pending",
            mode="dry-run",
            requested_cycles=2,
            actual_cycles=1,
            stopped_early=True,
            stop_reason="reviewer approved",
            artifacts=ArtifactLinks(
                final_md=Path("projects/demo_20260627/latest/final_draft/final.md")
            ),
            warnings=("latest locked",),
        )

        payload = revision_result_to_dict(result)

        self.assertEqual(payload["project_id"], "demo_20260627")
        self.assertEqual(
            payload["artifacts"]["final_md"],
            "projects/demo_20260627/latest/final_draft/final.md",
        )
        self.assertEqual(payload["warnings"], ["latest locked"])
