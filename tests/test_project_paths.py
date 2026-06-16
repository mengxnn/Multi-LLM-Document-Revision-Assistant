import json
import tempfile
import unittest
from pathlib import Path

from office_revision.project_paths import (
    VersionLayout,
    resolve_artifact,
    structured_manifest,
    write_manifest,
)


class ProjectPathsTests(unittest.TestCase):
    def test_version_layout_uses_structured_paths_and_compatibility_paths(self):
        layout = VersionLayout(Path("193728-pending-v1"))

        self.assertEqual(layout.final_md, Path("193728-pending-v1/final/final.md"))
        self.assertEqual(layout.final_docx, Path("193728-pending-v1/final/final.docx"))
        self.assertEqual(layout.summary_md, Path("193728-pending-v1/changes_summary/changes_summary.md"))
        self.assertEqual(layout.run_log, Path("193728-pending-v1/metadata/run_log.json"))
        self.assertEqual(layout.compat_final_md, Path("193728-pending-v1/final.md"))
        self.assertEqual(layout.compat_review_md, Path("193728-pending-v1/review.md"))

    def test_manifest_records_structured_files_and_round_reviews(self):
        layout = VersionLayout(Path("193728-pending-v1"))

        manifest = structured_manifest(
            layout,
            project_name="Project",
            version=1,
            status="pending",
            mode="real",
            source_type="docx",
            round_review_paths=[layout.reviews_dir / "round_01_review.md"],
        )

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["files"]["final_md"], "final/final.md")
        self.assertEqual(manifest["files"]["review_md"], "reviews/round_01_review.md")
        self.assertEqual(manifest["files"]["round_reviews"], ["reviews/round_01_review.md"])
        self.assertEqual(manifest["files"]["changes_summary_md"], "changes_summary/changes_summary.md")

    def test_resolve_artifact_prefers_manifest_then_structured_then_legacy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            version_dir = Path(temp_dir)
            layout = VersionLayout(version_dir)
            layout.ensure_dirs()
            layout.final_md.write_text("structured", encoding="utf-8")
            layout.compat_final_md.write_text("legacy", encoding="utf-8")

            write_manifest(
                layout,
                structured_manifest(
                    layout,
                    project_name="Project",
                    version=1,
                    status="pending",
                    mode="dry-run",
                    source_type="docx",
                    round_review_paths=[],
                ),
            )

            self.assertEqual(resolve_artifact(version_dir, "final_md").read_text(encoding="utf-8"), "structured")

            layout.final_md.unlink()
            self.assertEqual(resolve_artifact(version_dir, "final_md").read_text(encoding="utf-8"), "legacy")

            data = json.loads(layout.manifest.read_text(encoding="utf-8"))
            data["files"]["final_md"] = "custom/final.md"
            (version_dir / "custom").mkdir()
            (version_dir / "custom" / "final.md").write_text("manifest", encoding="utf-8")
            layout.manifest.write_text(json.dumps(data), encoding="utf-8")

            self.assertEqual(resolve_artifact(version_dir, "final_md").read_text(encoding="utf-8"), "manifest")


if __name__ == "__main__":
    unittest.main()
