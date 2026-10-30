# Shared runbooks

Shared runbooks must be project-neutral and use placeholders. Put project-specific procedures under `projects/<project-slug>/runbooks/`.

## Relationship to `core/runbooks/`

There are two shared-runbook locations, and the distinction matters when deciding where a new one goes:

- **This folder (`runbooks/`)** is for operational procedures that aren't tied to a specific technology
  stack — e.g. a general incident-response checklist, a generic on-call handoff procedure.
- **`core/runbooks/`** is for runbooks specific to a technology documented under `core/patterns/` — e.g.
  `core/runbooks/aws/ecs/` sits alongside `core/patterns/aws/ecs/` and cross-references it heavily.
  When a runbook is this tightly coupled to one technology's concepts, it belongs there, not here.

If you're unsure which applies, ask: "does this runbook reference a specific `core/patterns/` document
throughout, or is it genuinely stack-agnostic?" The former belongs in `core/runbooks/`; the latter here.

## Finding a runbook

`python3 scripts/search_brain.py "<keyword>" --runbooks` searches both locations at once.
