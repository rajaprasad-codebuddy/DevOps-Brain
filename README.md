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
2. Search before you browse: `python3 scripts/search_brain.py "<keyword>"` — see
   [Search](#search) below.
3. For AWS/ECS knowledge specifically, start at `core/patterns/aws/ecs/README.md` (concepts) and
   `core/runbooks/aws/ecs/README.md` (troubleshooting).
4. Add one sanitized project under `projects/`.
5. Add one runbook using `templates/runbook.md`.
6. Test the workflow with a documentation-only change.

## Repository map

| Folder | Contents | Status |
|---|---|---|
| `core/` | Shared standards, reusable AWS/ECS patterns, troubleshooting runbooks. See `core/README.md`. | Populated (ECS on EC2; see `core/patterns/aws/README.md` for coverage) |
| `projects/` | Isolated project knowledge. Do not copy facts between projects unless confirmed. | One sanitized sample project |
| `runbooks/` | Reusable, project-neutral operational procedures not tied to a specific technology stack. (Technology-specific shared runbooks, like ECS's, live under `core/runbooks/` instead — see `runbooks/README.md` for the distinction.) | Index only |
| `decisions/` | Architecture decision records. | Index only |
| `incidents/` | Sanitized incident reports and lessons learned. | Index only |
| `learning/` | Personal learning roadmaps and research notes. | **Planned, not yet created** — reserved for a later phase; no empty directory exists yet |
| `tasks/` | Recurring task checklists. | Index only |
| `templates/` | Document templates (runbook, ADR, knowledge-update proposal). | Populated |
| `proposals/` | Optional scratch space for AI-generated updates awaiting review. Prefer a branch/PR for normal changes. | Index only |
| `scripts/` | `check_brain.py` (validation) and `search_brain.py` (local search). | Populated |

## Search

Find existing knowledge before writing new knowledge or answering from memory — see
`AGENTS.md` §Knowledge retrieval.

```bash
python3 scripts/search_brain.py "capacity provider"               # keyword, anywhere in the document
python3 scripts/search_brain.py "CannotPullContainerError" --error  # exact, case-sensitive error text
python3 scripts/search_brain.py --technology ecs --category runbook # browse by filter, no keyword
python3 scripts/search_brain.py "fundamentals" --title              # match titles only
```

No database and no external service — it walks the Markdown files directly, so it has zero setup cost
and stays accurate as long as the files do.

## Fact status

Use one of these labels in project documents:
- `CONFIRMED`: verified against an authoritative source.
- `ASSUMPTION`: plausible but not verified.
- `PENDING`: waiting for confirmation or implementation.
- `DEPRECATED`: no longer valid; keep only if useful for history.

These can be recorded as a `**Status:**` bold line (the original convention) or as YAML frontmatter —
see `core/standards/document-metadata.md` for the frontmatter format and when to use it, and
`core/standards/knowledge-maintenance-workflow.md` for the day-to-day process of adding, updating, and
deprecating documents.

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

Checks: empty files, broken relative links (Markdown-style and backtick file-path mentions), missing
required sections in runbooks, duplicate document titles, missing/invalid knowledge status, missing
`last_verified` on `CONFIRMED` documents, and basic secret patterns. It is a hygiene/structure check,
not a security scanner or proof that facts are correct — see `SECURITY.md` and
`core/standards/knowledge-maintenance-workflow.md` §6 for what validation does and doesn't prove.
