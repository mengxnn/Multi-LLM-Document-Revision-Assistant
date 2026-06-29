# Local HTML GUI MVP Design

## Goal

Build a local browser-based GUI for the office revision assistant. The GUI should let a non-command-line user create projects, run writer/reviewer revisions, continue existing projects, inspect outputs, manage model profiles, and apply project decisions through a local web page.

The first version is a local tool, not an online service. It runs on the user's machine, opens in a browser, and calls the existing `RevisionApplication` facade instead of duplicating revision logic.

## Recommended Route

Use a lightweight FastAPI backend plus plain local HTML/CSS/JavaScript frontend.

This route is preferred because:

- it reuses the existing Python application layer directly;
- it avoids the complexity of a native desktop framework in the first version;
- it can later be wrapped as an exe if needed;
- it keeps the GUI testable through normal HTTP endpoints;
- it is easier to evolve into a richer interface after the workflow stabilizes.

Pure static HTML is not enough because the app must read and write local project files, run model calls, track progress, and manage configuration. A pure desktop app can be considered later, but it is not necessary for the first usable GUI.

## Scope

This MVP includes:

- local web server startup;
- project list page;
- project detail and version artifact page;
- new project form;
- continue project form;
- run progress display;
- project decision actions: accept, continue, abandon, skip;
- delete project action with trash/permanent option;
- model profile list, edit, save, and activate for writer/reviewer;
- model connection check;
- file inputs and pasted text inputs for requirements, source draft, meeting notes, and feedback;
- basic error display.

This MVP excludes:

- PDF input support;
- restore-from-trash;
- multi-project parallel scheduling beyond safe in-memory run tracking;
- advanced Word formatting preservation;
- Word comments and track changes;
- login, remote deployment, or multi-user permissions;
- polished desktop packaging.

## Architecture

```text
Browser
  |
  | HTTP / polling
  v
Local FastAPI server
  |
  | calls
  v
RevisionApplication
  |
  | existing services
  v
projects/, config/, inputs/, outputs/
```

The GUI backend is an adapter layer. It should not implement writer/reviewer workflow rules itself. It translates HTTP requests into application-layer contracts such as `StartProjectRequest`, `ContinueRevisionRequest`, and `ModelProfileRequest`.

## Proposed File Layout

```text
office_revision/
  web/
    __init__.py
    app.py
    schemas.py
    runs.py
    static/
      index.html
      styles.css
      app.js
```

`app.py` creates the FastAPI app and routes.

`schemas.py` defines HTTP request/response models. These are separate from application contracts so the web layer can handle browser-specific details such as file uploads.

`runs.py` stores active and completed run states in memory for the local server process.

`static/` contains the first plain HTML frontend.

## Backend API

Initial endpoints:

```text
GET  /api/projects
GET  /api/projects/{project_id}
POST /api/projects/start
POST /api/projects/{project_id}/continue
POST /api/projects/{project_id}/decision
DELETE /api/projects/{project_id}

GET  /api/model-profiles
POST /api/model-profiles
POST /api/model-profiles/{profile_id}/activate
GET  /api/model-profiles/active/{role}
POST /api/model-connections/check

GET  /api/runs/{run_id}
GET  /api/artifacts?path=...
```

`POST /api/projects/start` and `POST /api/projects/{project_id}/continue` return a `run_id` quickly. The actual model workflow runs in a background thread so the browser does not freeze or wait on a long request.

`GET /api/runs/{run_id}` returns:

- current status: `queued`, `running`, `completed`, or `failed`;
- progress events;
- final `RevisionRunResult` when completed;
- error message and stage when failed.

The first version uses polling instead of WebSocket or SSE. Polling every 1 second is simpler and sufficient for a local single-user tool.

## Run State

Each run state contains:

- `run_id`;
- `kind`: `start_project` or `continue_revision`;
- `status`;
- `created_at`;
- `started_at`;
- `finished_at`;
- `events`;
- `result`;
- `error`;
- optional `project_id`.

Progress events use the existing `ProgressEvent.display_message()` result for user-facing text, while preserving structured fields for future UI formatting.

The run store is in memory. If the local server restarts, historical run state is lost, but versioned project outputs remain on disk under `projects/`. This is acceptable for MVP because the project output is the source of truth.

## Frontend Pages

The first frontend can be a single HTML page with simple navigation tabs:

1. Projects
2. New Project
3. Model Profiles

The project detail view can open from the project list without requiring a separate routed frontend framework.

### Projects Tab

Shows:

- project title and project ID;
- latest version;
- latest status;
- latest mode;
- buttons for details, continue, accept, abandon, skip, delete.

The detail panel shows versions and artifact links:

- final draft DOCX/MD;
- revision summary;
- final review report;
- run log when available.

### New Project Tab

Inputs:

- requirements text area or requirements file;
- optional source draft text area or file;
- optional meeting notes text area or file;
- optional project title;
- cycles;
- dry-run switch;
- summary mode.

The start button is disabled until requirements text or a requirements file is present. Empty source draft means no-source drafting, matching current writer behavior.

### Continue Project Flow

The continue form appears from a selected project.

Inputs:

- feedback text area or feedback file;
- cycles;
- dry-run switch;
- summary mode.

Feedback may come from pasted text or file upload. If neither is provided, the backend may use the project's existing `inputs/feedback.md`, matching the application-layer behavior.

### Model Profiles Tab

Shows all saved profiles and which profile is active for writer and reviewer.

The edit form keeps the current flat data model but visually groups fields:

- basic: name, model;
- connection: provider, base URL, API key, timeout, retries;
- capabilities: search, model family, vision, function calling, JSON output, structured output.

Writer and reviewer can each activate exactly one profile. Other profiles remain available for quick switching.

## File and Text Input Handling

The browser supports both file upload and pasted text for user-provided content.

The backend maps uploads and text to the existing application request fields:

- `requirements_file` or `requirements_text`;
- `source_file` or `source_text`;
- `meeting_notes_file` or `meeting_notes_text`;
- `feedback_file` or `feedback_text`.

For uploaded files, the backend saves temporary files inside a local temporary GUI upload directory and passes those paths into the application service. The application service remains responsible for copying normalized snapshots into project `inputs/`.

For pasted text, the backend passes text directly into the application request. The application service remains responsible for writing the final snapshot files.

## Error Handling

Expected application errors are returned as structured JSON:

```json
{
  "ok": false,
  "stage": "validation",
  "message": "requirements is required"
}
```

Unexpected failures return a concise message in the GUI and keep technical details in the server log. The first GUI should never silently fail; every failed run should show its failed stage and message.

## Security and Local Access

The server binds to `127.0.0.1` by default.

The GUI should not expose arbitrary filesystem browsing in the first version. It only accepts files selected by the browser upload control and project/artifact paths returned by the application layer.

API keys are stored in `config/model_profiles.json`, which is ignored by Git. The example template remains `config/model_profiles.example.json`.

## Testing Strategy

Implementation should follow red-green-refactor.

Backend tests should cover:

- project list endpoint;
- project detail endpoint;
- starting a dry-run project returns a run ID;
- run polling records progress and final result;
- continue endpoint accepts feedback text;
- decision endpoint delegates accept/abandon/skip;
- delete endpoint supports trash and permanent mode;
- model profile list/save/activate;
- model connection endpoint with injected fake service;
- validation errors for missing requirements.

Frontend can start with light smoke checks:

- static files are served;
- main page loads;
- JavaScript can render a mocked project list;
- disabled start button when requirements are empty.

Manual real-model validation remains necessary after automated tests pass.

## Implementation Order

1. Add FastAPI and Uvicorn dependencies.
2. Add web package and HTTP schemas.
3. Add in-memory run store.
4. Add project/model-profile read endpoints.
5. Add dry-run start-project endpoint and run polling.
6. Add continue, decision, delete, and connection endpoints.
7. Add static HTML/CSS/JS frontend.
8. Add a launch command or script for local GUI startup.
9. Run full automated tests.
10. Perform one dry-run GUI test.
11. Perform one real-model GUI test.

## Success Criteria

The MVP is complete when a user can:

- start the local GUI;
- configure or switch writer/reviewer profiles;
- create a new project from pasted requirements and optional files;
- see progress events during a run;
- open the generated final draft and reports;
- continue an existing project with pasted feedback or a feedback file;
- apply decisions to a version;
- delete a test project by trash or permanent mode;
- complete the above without using command-line arguments.

No Git commit is created by the assistant.
