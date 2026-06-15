# Version Directory Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a structured version directory layout while preserving compatibility with existing top-level version files.

**Architecture:** Introduce `office_revision.project_paths` as the central path resolver and manifest writer. Existing flows continue writing top-level compatibility files, while also writing `final/`, `reviews/`, `summaries/`, and `metadata/` subdirectories.

**Tech Stack:** Python 3.12, standard-library `unittest`, existing document IO helpers.

---

### Task 1: Path Resolver and Manifest

**Files:**
- Create: `office_revision/project_paths.py`
- Create/modify: `tests/test_project_paths.py`

- [ ] Add tests for structured file paths, manifest content, and legacy fallback.
- [ ] Implement path constants, `VersionLayout`, manifest read/write, and artifact resolution.

### Task 2: Structured Output Writing

**Files:**
- Modify: `office_revision/cli.py`
- Modify: `tests/test_cli.py`

- [ ] Update `write_outputs` to write both structured paths and top-level compatibility files.
- [ ] Include `reviews/round_N_review.md` in manifest.
- [ ] Update latest output copying to include structured layout.

### Task 3: Continue and Review Compatibility

**Files:**
- Modify: `office_revision/continue_flow.py`
- Modify: `office_revision/decision_flow.py`
- Modify: existing tests.

- [ ] Use path resolver for latest, previous final, status files, and latest metadata.
- [ ] Ensure old projects without manifest still work.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`

- [ ] Document structured version layout and compatibility files.
- [ ] Run the full test suite.
