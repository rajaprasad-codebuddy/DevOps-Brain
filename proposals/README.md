# Proposals

Optional scratch space for AI-generated knowledge updates that are awaiting human review.

## Purpose

When an AI agent drafts a non-trivial documentation change — new runbook, architecture update, incident
write-up — it can place the draft here instead of editing the target file directly. This keeps proposed
changes visible and reviewable without touching committed knowledge until a human approves them.

Use this folder when:
- The change is large enough that reviewing it as a standalone file is easier than reviewing an inline diff.
- Multiple related documents are being proposed together and should be reviewed as a set.
- You want to keep a proposal around across sessions before deciding whether to merge it.

Prefer a branch and a pull request for normal, small changes. Use `proposals/` as a lower-ceremony
alternative when a branch/PR is not practical yet (for example, early drafting before scope is confirmed).

## Workflow

1. The AI agent writes the proposed document(s) under `proposals/`, following the same structure and
   metadata rules as the final location would require (see `core/standards/knowledge-quality.md`).
2. The agent explains which target file(s) the proposal would update or create, and why.
3. A human reviews the proposal: checks for secrets, cross-project leakage, and factual accuracy
   (see `SECURITY.md` and `AGENTS.md`).
4. On approval, the content is moved to its real location (e.g. `core/`, `projects/<slug>/`,
   `runbooks/`, `incidents/`, `decisions/`) and removed from `proposals/`.
5. On rejection, the proposal is deleted or revised in place.

## Rules

- Nothing in `proposals/` is considered approved knowledge. Do not treat it as a source of truth.
- Follow the same security rules as the rest of the repository — no secrets, no unredacted customer
  data, no unapproved production details (see `SECURITY.md`).
- Do not leave stale proposals indefinitely; resolve (approve or reject) before starting unrelated work
  in the same area.

## Related documents

- `core/standards/knowledge-maintenance-workflow.md` — the full add/update/deprecate process this
  folder is one entry point into.
- `templates/knowledge-update.md` — the template a proposal here should follow.
