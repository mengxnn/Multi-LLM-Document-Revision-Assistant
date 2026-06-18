# Application Service Layer Implementation Plan

**Goal:** Provide stable Python interfaces that can be shared by the CLI and a future local web GUI.

**Architecture:** Add an `office_revision.application` package above the existing workflow, project, decision, and connection modules. The first phase exposes query, decision, and connection services without coupling the GUI to CLI parsing or terminal output.

**Reference patterns:**

- Dify separates application inputs, workflow execution, credentials, and streaming responses.
- LangGraph/LangSmith separates long-lived threads from individual runs and attaches metadata and feedback to runs.
- AutoGen Studio separates team configuration, interactive execution, and deployment endpoints.

## Tasks

1. Add immutable DTOs for projects, versions, artifacts, decisions, and model checks.
2. Add project listing and detail queries backed by `metadata/project.json`, manifests, and latest metadata.
3. Add a decision service backed by the existing decision flow.
4. Add a model connection service backed by the existing config and connection modules.
5. Expose the services through a `RevisionApplication` facade.
6. Add focused service tests and run the full suite.

## Public Interface

```python
app = RevisionApplication(projects_root="projects")
projects = app.list_projects()
detail = app.get_project_details(projects[0].project_id)
outcome = app.apply_revision_decision(detail.summary.project_id, "accept")
checks = app.check_model_connections()
```

The next phase will extract `start_revision` and `continue_revision` orchestration from `cli.py` so both CLI and GUI call the same service implementation.
