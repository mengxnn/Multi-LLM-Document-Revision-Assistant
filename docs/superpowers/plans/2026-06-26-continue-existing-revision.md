# Continue Existing Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an application-layer `continue_existing_revision()` API for GUI use, plus a local manual smoke-test script that is ignored by Git.

**Architecture:** Reuse the existing CLI continue building blocks instead of rewriting business rules: `continue_flow` resolves the project/version and feedback, `workflow` or `autogen_runner` performs writer/reviewer rounds, and `revision_outputs` writes the new version plus `latest`. The application layer owns GUI-friendly contracts, progress events, validation errors, and `RevisionRunResult`.

**Tech Stack:** Python dataclasses, unittest, existing office_revision modules, PowerShell-friendly local scripts.

---

### Task 1: Contracts and facade

**Files:**
- Modify: `office_revision/application/contracts.py`
- Modify: `office_revision/application/revision_application.py`
- Modify: `office_revision/application/__init__.py`
- Test: `tests/test_application_services.py`

- [ ] Add `ContinueRevisionRequest` with project/version target, feedback path/text, cycles, dry-run, summary mode, model overrides, and prompt paths.
- [ ] Export `ContinueRevisionRequest`.
- [ ] Add `RevisionApplication.continue_existing_revision(request, on_progress=None)`.
- [ ] Test that the new contract and facade method are importable and callable through injected service.

### Task 2: Continue service

**Files:**
- Create: `office_revision/application/continued_revisions.py`
- Test: `tests/test_continued_revisions.py`

- [ ] Write failing dry-run test for continuing from an existing project with `feedback_text`.
- [ ] Implement `ContinuedRevisionService` using existing `continue_flow` helpers.
- [ ] Emit `ProgressEvent` stages for loading project, reading previous draft, reading feedback, analyzing feedback, writer/reviewer rounds, summary/report generation, saving outputs, and completion.
- [ ] Return `RevisionRunResult` with v2/v3 paths and artifact links.
- [ ] Preserve `latest` as a copy and warn if it cannot be refreshed.
- [ ] Validate feedback conflicts and empty feedback before writing outputs.

### Task 3: Manual test script and ignore rule

**Files:**
- Create: `test_continue_revision.py`
- Modify: `.gitignore`

- [ ] Add a local script that calls `RevisionApplication.continue_existing_revision()` and prints `event.display_message()`.
- [ ] Add `test_continue_revision.py` to `.gitignore`.
- [ ] Verify the script compiles and is ignored.

### Task 4: Verification

**Files:**
- Existing tests under `tests/`

- [ ] Run targeted tests for application services and continued revisions.
- [ ] Run full unittest discovery.
- [ ] Run `compileall`.
- [ ] Run `git diff --check`.
