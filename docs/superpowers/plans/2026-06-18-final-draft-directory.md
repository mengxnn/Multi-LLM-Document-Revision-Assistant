# Final Draft Directory Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename every generated version's `final/` directory to `final_draft/` without adding legacy compatibility behavior.

**Architecture:** Keep `VersionLayout` as the single source of truth for version artifact paths. Change its final artifact directory, then update tests, fixtures, documentation, and disposable sample output so new runs, continued runs, manifests, queries, and `latest/` all agree on the same layout.

**Tech Stack:** Python 3.12, `pathlib`, standard-library `unittest`, python-docx, Markdown documentation.

---

### Task 1: Lock the renamed path contract with tests

**Files:**
- Modify: `tests/test_project_paths.py`
- Modify: `tests/test_application_services.py`
- Modify: `tests/test_continue_cli.py`
- Modify: `tests/test_decision_cli.py`
- Modify: `tests/test_cli.py`

- [x] **Step 1: Change path assertions and fixtures to require `final_draft/`**

Update explicit paths such as:

```python
self.assertEqual(layout.final_md, Path("193728-pending-v1/final_draft/final.md"))
self.assertEqual(manifest["files"]["final_md"], "final_draft/final.md")
```

Change test fixture helpers from `session / "final"` to `session / "final_draft"`, and change manifest fixture values from `final/final.md` to `final_draft/final.md`.

- [x] **Step 2: Add an assertion that new output does not create `final/`**

In a CLI output test, add:

```python
self.assertTrue((output / "final_draft" / "final.md").exists())
self.assertFalse((output / "final").exists())
```

- [x] **Step 3: Run focused tests and verify the new expectations fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_project_paths tests.test_application_services tests.test_cli tests.test_continue_cli tests.test_decision_cli -v
```

Expected: failures reference paths under `final/` because production code has not changed yet.

### Task 2: Change the centralized production path

**Files:**
- Modify: `office_revision/project_paths.py`

- [x] **Step 1: Rename the layout directory and artifact fallbacks**

Use:

```python
ARTIFACT_FALLBACKS = {
    "final_docx": ("final_draft/final.docx",),
    "final_md": ("final_draft/final.md",),
    # existing non-final entries remain unchanged
}

@property
def final_dir(self) -> Path:
    return self.root / "final_draft"
```

Keep `final_docx`, `final_md`, and manifest artifact keys unchanged.

- [x] **Step 2: Run focused path and application tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_project_paths tests.test_application_services -v
```

Expected: all tests pass.

- [x] **Step 3: Run CLI and continue tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cli tests.test_continue_cli tests.test_decision_cli -v
```

Expected: all tests pass, including continue resolution through manifest and artifact fallbacks.

### Task 3: Update user documentation

**Files:**
- Modify: `README.md`

- [x] **Step 1: Replace current-layout references**

Change user-facing paths from `final/final.md` and `final/final.docx` to `final_draft/final.md` and `final_draft/final.docx`. Rename directory-tree entries and the directory explanation from `final/` to `final_draft/`. Do not rewrite historical planning documents.

- [x] **Step 2: Verify no active code, tests, scripts, or README references the old path**

Run:

```powershell
rg -n 'final/final|/ "final"|/ ''final''|final/' office_revision tests scripts README.md
```

Expected: no version-artifact reference to the old `final/` directory. Local variable names such as `final_dir` in decision logic are allowed because they mean the final resolved session directory, not the artifact directory.

### Task 4: Handle disposable sample output and run the full quality gate

**Files:**
- Optional disposable data: `projects/多智能体强化学习融合调研报告修订_20260617/`

- [x] **Step 1: Remove the disposable generated project instead of adding migration code**

Delete only the explicitly approved test project directory after resolving and verifying its absolute path is inside the workspace `projects/` directory. Do not delete any other project.

- [x] **Step 2: Run the complete test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

- [x] **Step 3: Inspect the final worktree without committing**

Run:

```powershell
git diff --check
git status --short
```

Expected: only the approved design, plan, code, tests, and README changes remain uncommitted. Stop before implementing `start_new_project()`.
