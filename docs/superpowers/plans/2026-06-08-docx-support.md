# Docx Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the revision workflow to read `.docx` source documents and write `final.docx` outputs while preserving basic heading, paragraph, and table structure.

**Architecture:** Add `office_revision.document_io` as the only file-format adapter. The workflow continues to operate on text; CLI reads source files through document IO and writes final outputs through document IO.

**Tech Stack:** Python 3.12, `python-docx`, standard-library `unittest`.

---

### Task 1: Document IO Tests

**Files:**
- Create: `tests/test_document_io.py`
- Create: `office_revision/document_io.py`

- [ ] Write tests that create a small `.docx` with a heading, paragraph, and table.
- [ ] Verify `.docx` is extracted into markdown-like text with headings and table rows.
- [ ] Verify markdown-like text can be written back to `final.docx`.

### Task 2: CLI Integration

**Files:**
- Modify: `office_revision/cli.py`
- Modify: `tests/test_cli.py`

- [ ] Write a CLI test using `.docx` as `--source`.
- [ ] Verify output includes `final.md`, `final.docx`, `review.md`, and `run_log.json`.
- [ ] Replace direct `Path.read_text` and local output writing with `document_io` helpers.

### Task 3: Docs and Dependency

**Files:**
- Modify: `requirements.txt`
- Modify: `README.md`

- [ ] Add `python-docx` dependency.
- [ ] Document `.docx` input/output behavior and current `.doc` limitation.
- [ ] Run all tests and a dry-run `.docx` example.
