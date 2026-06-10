# Office Revision Agent Design

## Goal

Build a runnable command-line prototype that uses a writer agent and a reviewer agent to revise office documents through multiple write-review cycles.

## Scope

The first version accepts plain text or Markdown input, a revision instruction file, and a cycle count. It produces a final draft, a review report, and a machine-readable run log. Meeting transcription, Word/PDF handling, and a browser UI are intentionally deferred, but the interfaces leave room for them.

## Architecture

The workflow has three layers:

- `office_revision.workflow`: model-independent loop orchestration.
- `office_revision.dry_run`: deterministic local agents for setup checks and tests.
- `office_revision.autogen_runner`: optional AutoGen-backed agents for real model calls.
- `office_revision.cli`: command-line parsing, file IO, and output writing.

The workflow always uses the same contract: a writer receives the source text, requirements, previous draft, and latest review; a reviewer receives the source text, requirements, and current draft. That keeps AutoGen, dry-run agents, and future meeting-summary agents interchangeable.

## Data Flow

1. Read source document and revision requirements.
2. Run the writer for the first draft.
3. Run the reviewer on the draft.
4. Repeat writer-review cycles for the requested number of cycles.
5. Save `final.md`, `review.md`, and `run_log.json`.

## Configuration

The CLI supports `--dry-run`, `--cycles`, `--writer-model`, `--reviewer-model`, `--output-dir`, and optional OpenAI-compatible environment variables. If AutoGen packages or API keys are missing, the user can still run the dry-run mode.

## Testing

Use Python standard-library `unittest` so the prototype can be verified before installing dependencies. Tests cover the core loop, dry-run agent behavior, and CLI output files.
