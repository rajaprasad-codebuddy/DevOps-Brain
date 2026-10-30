# Project knowledge

Create one directory per project using a neutral slug, e.g. `sample-service/`.

Each project should contain:
- `README.md`: purpose, scope, owner and document index.
- `architecture.md`: verified architecture and boundaries.
- `environments.md`: sanitized environment inventory and status.
- `runbooks/`: project-specific operational procedures.
- `decisions/`: project-specific architecture decisions.

Keep project-specific information isolated. Do not use a real employer/customer project name or production identifiers until repository policy and AI-tool usage have been approved.

See `projects/sample-project/` for a populated (placeholder) example of this structure.

Search within a project's own documents with `python3 scripts/search_brain.py "<keyword>" --category project`
— note this searches across *all* projects, so re-check which project a result belongs to before
reusing anything from it (cross-project reuse requires explicit confirmation — see `AGENTS.md`).
