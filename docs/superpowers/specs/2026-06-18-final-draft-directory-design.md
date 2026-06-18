# Final Draft Directory Rename Design

## Goal

Rename the version-level `final/` directory to `final_draft/` so users can distinguish the final draft of a revision run from the intermediate drafts in `drafts/`.

This change is a prerequisite for the future `start_new_project()` application interface. That interface is explicitly outside the scope of this change and will not be implemented until the renamed directory has passed automated and real-model testing.

## Target Layout

Every timestamped version directory and its `latest/` copy will use this structure:

```text
drafts/
  round_01_draft.md
  ...
final_draft/
  final.docx
  final.md
reviews/
  round_01_review.md
  ...
  revision_summary.docx
  revision_summary.md
final_review_report/
  final_review_report.docx
  final_review_report.md
metadata/
  manifest.json
  run_log.json
  session_status.json
```

No newly generated version may contain `final/`.

## Code Changes

- Update `VersionLayout.final_dir` and all final artifact paths to use `final_draft/`.
- Update artifact fallbacks, manifest output, continue-version source resolution, and any direct path construction.
- Keep artifact keys such as `final_docx` and `final_md` unchanged. They describe artifact meaning, not directory spelling.
- Update CLI messages, README examples, and tests that assert the version layout.
- Do not add permanent compatibility logic for `final/`; the project has not entered production use.

## Existing Test Project

The existing `projects/多智能体强化学习融合调研报告修订_20260617` directory contains disposable test output. It does not justify production migration code. The implementation may either update its generated directories and manifests mechanically or remove the disposable project if a clean migration is not worthwhile. No real user project data is in scope.

## Error and Lock Handling

Existing behavior for a locked `latest/` directory remains unchanged: the timestamped version is preserved and refreshing `latest/` may be skipped with a clear message. The directory rename must not weaken this behavior.

## Verification

Tests must demonstrate that:

- new and continued runs write final artifacts under `final_draft/`;
- manifests reference `final_draft/final.md` and `final_draft/final.docx`;
- artifact queries resolve the renamed paths;
- continue reads the preceding version from `final_draft/`;
- `latest/` uses the same layout;
- no test expects or generates a version-level `final/` directory;
- the complete test suite passes using the project virtual environment.

After automated verification, implementation stops. Real-model testing and approval happen before work begins on `start_new_project()`.
