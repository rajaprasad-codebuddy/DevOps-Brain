# DevOps Brain

A private, Git-based engineering knowledge base for reusable DevOps knowledge and isolated project-specific facts.

## Principles

- Markdown is the source of truth; AI agents are readers and proposed editors.
- Shared standards live in `core/`. Project-specific knowledge lives in `projects/<project-slug>/`.
- Every important fact should have a source, verification date, and status.
- AI proposes changes on a branch or as a diff. A human reviews and approves them.
- Never store credentials, secret values, customer data, or unapproved production details.

## Start here

1. Read `AGENTS.md` and `SECURITY.md`.
2. Fill in `core/standards/knowledge-quality.md` and `core/standards/change-safety.md`.
3. Add one sanitized project under `projects/`.
4. Add one runbook using `templates/runbook.md`.
5. Test the workflow with a documentation-only change.

## Repository map

- `core/`: shared standards, reusable patterns, global tooling guidance.
- `projects/`: isolated project knowledge. Do not copy facts between projects unless confirmed.
- `runbooks/`: reusable, project-neutral operational procedures.
- `decisions/`: architecture decision records.
- `incidents/`: sanitized incident reports and lessons learned.
- `tasks/`: recurring task checklists.
- `templates/`: document templates.
- `proposals/`: optional scratch space for AI-generated updates awaiting review. Prefer a branch/PR for normal changes.

## Fact status

Use one of these labels in project documents:
- `CONFIRMED`: verified against an authoritative source.
- `ASSUMPTION`: plausible but not verified.
- `PENDING`: waiting for confirmation or implementation.
- `DEPRECATED`: no longer valid; keep only if useful for history.

## Change workflow

1. Create a branch, e.g. `brain/update-ecs-runbook`.
2. Ask an AI agent to inspect relevant files and propose a minimal diff.
3. Check for secrets and cross-project leakage.
4. Verify technical claims against source files, logs, tickets, or an owner.
5. Review the diff and run validation.
6. Commit and merge only after approval.
7. Add a verification date or changelog entry for material changes.

## Local validation

Run:

```bash
python3 scripts/check_brain.py
```

This is a lightweight hygiene check, not a security scanner or proof that facts are correct.
