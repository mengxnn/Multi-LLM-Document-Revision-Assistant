# Start New Project Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `RevisionApplication.start_new_project()` as the single managed-project entry point for new dry-run and real-model revisions, then make the CLI delegate to it.

**Architecture:** Add immutable application contracts and a dedicated `NewProjectService`. Move reusable run-output helpers out of the CLI, expose generic cycle progress hooks from both workflow implementations, and keep CLI responsibilities limited to parsing and presentation. Remove the unmanaged `--output-dir` branch.

**Tech Stack:** Python 3.12, dataclasses, pathlib, unittest, AutoGen, python-docx.

---

### Task 1: Define public contracts and validation errors

**Files:**
- Modify: `office_revision/application/contracts.py`
- Modify: `office_revision/application/__init__.py`
- Modify: `tests/test_application_services.py`

- [ ] Add failing tests that import `StartProjectRequest`, `ProgressEvent`, `RevisionRunResult`, and `RevisionApplicationError`, then assert immutable request defaults and artifact-bearing results.
- [ ] Run `python -m unittest tests.test_application_services -v` and verify import failures.
- [ ] Add the dataclasses and error type. Request fields use `Path | None` and `str | None`; result fields include project/version paths, cycle data, artifacts, and warnings.
- [ ] Export the contracts from `office_revision.application` and rerun the focused test to green.

### Task 2: Add generic workflow progress hooks

**Files:**
- Modify: `office_revision/workflow.py`
- Modify: `office_revision/autogen_runner.py`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_autogen_runner.py`

- [ ] Add failing tests that pass an `on_progress(stage, cycle, total)` callback and expect `writer_running` then `reviewer_running` for each executed cycle, including early stop.
- [ ] Run the two focused test modules and verify callback-argument failures.
- [ ] Add an optional generic callback to synchronous and asynchronous loops and emit immediately before each writer/reviewer call.
- [ ] Thread the callback through `run_autogen_revision_loop()` without importing application contracts, then rerun focused tests.

### Task 3: Extract reusable output helpers from the CLI

**Files:**
- Create: `office_revision/revision_outputs.py`
- Modify: `office_revision/cli.py`
- Modify: `tests/test_cli.py`

- [ ] Add a focused test importing output serialization and writing helpers from `office_revision.revision_outputs`.
- [ ] Verify the import fails.
- [ ] Move `result_to_dict`, `write_outputs`, `write_round_outputs`, `prepare_output_dir`, and summary-generation logic into `revision_outputs.py`; keep behavior and `final_draft/` layout unchanged.
- [ ] Import those helpers in the CLI and rerun CLI tests to ensure no behavior change.

### Task 4: Implement NewProjectService with file and text inputs

**Files:**
- Create: `office_revision/application/new_projects.py`
- Modify: `office_revision/application/revision_application.py`
- Modify: `office_revision/application/__init__.py`
- Create: `tests/test_new_projects.py`

- [ ] Add failing validation tests for empty requirements, conflicting path/text fields, missing paths, unsupported source types, invalid cycles, invalid summary mode, and invalid title language.
- [ ] Implement validation that raises `RevisionApplicationError` before project creation.
- [ ] Add failing dry-run tests for pasted inputs, uploaded inputs, no-source drafting, normalized snapshots, progress order, v1/latest output, and structured result paths.
- [ ] Implement input normalization, project creation, snapshots, dry-run workflow, summaries, version output, latest metadata, warnings, and result construction.
- [ ] Add dependency-injected real-run tests for settings, workflow execution, title generation, and rename behavior without external model calls.
- [ ] Implement the real-run path using current config, optional model overrides, existing title behavior, and generic progress mapping.
- [ ] Inject `NewProjectService` into `RevisionApplication` and expose `start_new_project(request, on_progress=None)`.
- [ ] Run `tests.test_new_projects` and `tests.test_application_services` to green.

### Task 5: Make CLI delegate and remove --output-dir

**Files:**
- Modify: `office_revision/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `README.md`

- [ ] Add failing parser and delegation tests: `--output-dir` is rejected, normal new runs construct `StartProjectRequest`, and progress messages are printed.
- [ ] Replace the new-run orchestration branch with `RevisionApplication.start_new_project()` while leaving connection, review, and continue branches intact.
- [ ] Remove `--output-dir`, `default_output_dir`, `default_run_output_dirs`, and the obsolete CLI-only new-run helpers.
- [ ] Update README examples and behavior notes, then run CLI, continue, and decision tests.

### Task 6: Full verification without Git commit

**Files:**
- Modify tests only if verification reveals a real uncovered regression; reproduce it with a failing test first.

- [ ] Run `python -m unittest discover -s tests -v` and require zero failures.
- [ ] Run `git diff --check`.
- [ ] Scan active code and README for `--output-dir`, application imports from CLI, and obsolete final paths.
- [ ] Inspect `git status --short` and stop with all approved changes uncommitted for user review and real-model testing.
