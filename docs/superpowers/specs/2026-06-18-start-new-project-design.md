# Start New Project Application Interface Design

## Goal

Add a stable `RevisionApplication.start_new_project()` interface that creates a managed project, runs the writer-reviewer workflow, saves versioned artifacts, reports structured progress, and returns structured results. The CLI will use this interface for all new projects, and the same interface will later serve FastAPI and the GUI.

## Scope

This phase includes:

- `StartProjectRequest`, `ProgressEvent`, and `RevisionRunResult` contracts;
- a new-project application service;
- `RevisionApplication.start_new_project()`;
- file-path and pasted-text inputs;
- dry-run and real-model execution;
- structured per-stage and per-cycle progress;
- CLI migration to the application interface;
- removal of the unmanaged `--output-dir` path.

This phase excludes continue revision, model-profile management, FastAPI, GUI implementation, cancellation, background queues, and concurrent project execution.

## Public Interface

```python
result = app.start_new_project(
    StartProjectRequest(
        requirements_text="Rewrite this as a formal project proposal.",
        source_path="draft.docx",
        meeting_notes_text="Keep the agreed delivery date.",
        cycles=3,
        dry_run=False,
    ),
    on_progress=handle_progress,
)
```

`on_progress` is optional. The service returns only after the run succeeds or raises an application-layer exception.

## Contracts

### StartProjectRequest

The immutable request contains:

- `requirements_path` or `requirements_text`: exactly one non-empty source is required;
- `source_path` or `source_text`: optional and mutually exclusive;
- `meeting_notes_path` or `meeting_notes_text`: optional and mutually exclusive;
- `project_title`: optional explicit initial title;
- `project_title_language`: `auto`, `zh`, or `en`;
- `cycles`: positive integer;
- `dry_run`: whether to use deterministic local agents;
- `summary_mode`: `rule` or `llm`;
- optional writer and reviewer model overrides;
- writer and reviewer prompt paths.

Whitespace-only optional text is treated as absent. Whitespace-only requirements are invalid. Uploaded `.docx`, `.md`, and `.txt` source files remain supported.

### ProgressEvent

Each event contains a stable `stage` code, a user-facing `message`, and optional `cycle` and `total_cycles` values. Initial stages are:

- `reading_inputs`
- `creating_project`
- `writer_running`
- `reviewer_running`
- `generating_summary`
- `generating_final_review`
- `renaming_project`
- `saving_outputs`
- `completed`

The workflow and real-model runner expose generic progress hooks without importing application-layer contracts. The application service maps those updates to `ProgressEvent` objects.

### RevisionRunResult

The immutable result contains:

- project ID and project directory;
- version number, version directory, and optional `latest/` path;
- status and run mode;
- requested and actual cycle counts;
- early-stop flag and reason;
- final artifact links;
- non-fatal warnings, such as a locked `latest/` directory.

## Components and Boundaries

`RevisionApplication` remains the public facade. It delegates new-project work to a dedicated service injected through its constructor for focused tests.

The new-project service owns orchestration but does not parse command-line arguments or print terminal messages. Shared output-writing and summary helpers currently embedded in `cli.py` move to a non-CLI module so neither the application layer nor future GUI code depends on CLI internals.

The core workflow remains model-independent. It receives an optional generic progress hook for writer and reviewer cycle boundaries. The real-model runner receives the same kind of hook. Neither layer imports `office_revision.application`.

The CLI owns only argument parsing, request construction, progress printing, result display, and conversion of application errors to user-facing CLI exits.

## Input Snapshot Rules

Managed project inputs use stable role-based names:

```text
inputs/
  requirements.md
  source.docx | source.md | source.txt
  meeting_notes.md
  feedback.md
```

Pasted requirements, source, and meeting notes are written as UTF-8 Markdown. File inputs are copied using their supported source extension and normalized role name. Missing or empty source content means the writer starts from the requirements. `feedback.md` is initialized from the existing template.

## Execution and Output Flow

1. Validate request shape, cycles, modes, paths, and required content before creating a project.
2. Read and normalize all inputs.
3. Choose the initial local project title and create the managed project.
4. Snapshot normalized inputs and initialize feedback.
5. Load the current writer and reviewer settings, applying optional model overrides.
6. Run dry-run agents or the real-model workflow while emitting progress events.
7. For real runs, generate and apply the final suggested project title using existing behavior.
8. Generate the revision summary and final review report.
9. Write the timestamped v1 directory and refresh `latest/` using the established layout:

```text
drafts/
final_draft/
reviews/
final_review_report/
metadata/
```

10. Update project/latest metadata and return `RevisionRunResult`.

If refreshing a locked `latest/` fails, the timestamped version remains successful and the result carries a warning.

## CLI Migration

The CLI removes `--output-dir`. Every new dry-run or real-model invocation creates a project under `--projects-root`. Existing connection checks, project decisions, and continue commands keep their current entry paths during this phase.

The CLI retains `--dry-run`, model overrides, prompt paths, summary mode, cycles, project title, and project-title language. It translates them into `StartProjectRequest` and prints `ProgressEvent.message` values.

## Error Handling

Application code does not raise `SystemExit` or rely on terminal output. Validation and run failures use application-layer exceptions with a stable message and stage context. Missing files, unsupported file types, conflicting path/text inputs, empty requirements, invalid cycles, and invalid modes fail before project creation whenever possible.

Unexpected model or filesystem failures preserve their original cause. The CLI catches application errors and converts them to the existing concise command-line failure behavior.

## Testing

Implementation follows red-green-refactor. Focused tests cover:

- request validation for path/text conflicts and empty requirements;
- pasted-text and file input snapshots;
- no-source drafting;
- dry-run project creation and v1/latest outputs;
- real-run dependency injection without external calls;
- progress ordering and writer/reviewer cycle values;
- early reviewer stop;
- project-title rename behavior;
- locked `latest/` warnings;
- structured result artifact paths;
- removed `--output-dir` parsing;
- CLI delegation to `RevisionApplication.start_new_project()`;
- preservation of connection, decision, and continue commands.

The phase completes only when focused tests and the full suite pass. No Git commit is created by the assistant. Real-model validation follows before designing `continue_existing_revision()`.
