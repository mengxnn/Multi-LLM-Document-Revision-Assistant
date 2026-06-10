# Office Revision Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a command-line AutoGen-compatible office document revision prototype.

**Architecture:** A model-independent workflow coordinates writer and reviewer callables, with deterministic dry-run agents for local verification and an optional AutoGen runner for real model calls. The CLI owns file IO and writes final draft, review report, and JSON log.

**Tech Stack:** Python 3.12, standard-library `unittest`, optional `autogen-agentchat` and `autogen-ext[openai]`.

---

### Task 1: Core Workflow

**Files:**
- Create: `tests/test_workflow.py`
- Create: `src/office_revision/workflow.py`
- Create: `src/office_revision/__init__.py`

- [ ] Write failing tests for multi-cycle writer-review orchestration.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest tests.test_workflow -v` and confirm import failure.
- [ ] Implement dataclasses and `run_revision_loop`.
- [ ] Run the test again and confirm it passes.

### Task 2: Dry-Run Agents

**Files:**
- Create: `tests/test_dry_run.py`
- Create: `src/office_revision/dry_run.py`

- [ ] Write failing tests for deterministic writer and reviewer behavior.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest tests.test_dry_run -v` and confirm failure.
- [ ] Implement local dry-run writer and reviewer.
- [ ] Run the test again and confirm it passes.

### Task 3: CLI and Output Files

**Files:**
- Create: `tests/test_cli.py`
- Create: `src/office_revision/cli.py`
- Create: `run_revision.py`

- [ ] Write failing tests for dry-run CLI output files.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest tests.test_cli -v` and confirm failure.
- [ ] Implement CLI parsing and output writing.
- [ ] Run the test again and confirm it passes.

### Task 4: Optional AutoGen Runner and Documentation

**Files:**
- Create: `src/office_revision/autogen_runner.py`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `examples/source.md`
- Create: `examples/requirements.md`

- [ ] Add optional AutoGen agent adapter.
- [ ] Document setup, dry-run command, real-model command, and future extensions.
- [ ] Run all tests with `.\.venv\Scripts\python.exe -m unittest discover -v`.
