---
title: "Knowledge maintenance workflow"
category: standard
technology: general
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "Repository policy (introduced in Phase 6)"
---

# Knowledge maintenance workflow

## Purpose

A step-by-step process for the six recurring maintenance actions in this Brain: adding knowledge,
updating it, marking it outdated, reviewing pending information, verifying sources, and validating
before approval. This complements, not replaces, `core/standards/change-safety.md` (the general
change-safety principles) and `core/standards/knowledge-quality.md` (the required metadata fields).

**Human approval is mandatory for every step that changes a committed document.** Nothing in this
workflow authorizes an AI agent to commit, push, or merge on its own — see `AGENTS.md`.

## 1. Add new knowledge

1. Search first (`python3 scripts/search_brain.py "<keyword>"`) to confirm this isn't already
   documented somewhere, under a different title or in a different category than expected.
2. Decide the category: shared/reusable → `core/`; project-specific → `projects/<slug>/`; personal
   learning → `learning/`; a specific incident → `incidents/`; an architecture decision → `decisions/`.
   See `README.md`'s repository map if the boundary is unclear.
3. Write the document using the relevant template (`templates/runbook.md`, `templates/adr.md`) or, for
   a new pattern/standard, follow the structure of an existing sibling document in the same folder.
4. Add frontmatter if the document is mature/technology-specific enough to be worth searching for later
   — see `core/standards/document-metadata.md` for the migration guidance (don't add it reflexively to
   every new file).
5. Record `status`, `source`, and `last_verified` honestly — `PENDING`/`Unknown` is correct and expected
   for a draft, not a flaw to hide.
6. Run validation (`python3 scripts/check_brain.py`) and fix anything it flags before requesting review.
7. Present the new document (or diff, if editing toward it incrementally) for human approval before it's
   committed.

## 2. Update existing documentation

1. Search for and read the current version in full before proposing a change — don't edit from a
   fragment or a memory of what the document "probably says."
2. If the update contradicts the existing content, treat it as a conflict to flag explicitly (see
   `AGENTS.md` §Knowledge retrieval point 3), not a silent overwrite.
3. Show the diff, not just the new text — a reviewer approving "the new version" without seeing what
   changed can't actually review it.
4. Update `last_verified` to the date of this update if the update reconfirms or corrects a fact; update
   `status` if the update changes confidence (e.g. `ASSUMPTION` → `CONFIRMED` once verified).
5. Run validation before requesting approval.

## 3. Mark documentation outdated

1. Do not delete a document just because it's outdated — set its status to `DEPRECATED` instead, so the
   history and reasoning stay visible (`README.md`'s fact-status definitions).
2. If a replacement document exists, link to it from the deprecated one ("superseded by ...") — don't
   make a reader hunt for the current version.
3. For an ADR specifically, follow `templates/adr.md`'s own convention: supersede with a new ADR rather
   than rewriting the old one's content, per `decisions/README.md`.
4. Deprecating a document is still a documentation change — it needs the same review/approval as any
   other edit, not a quick unreviewed commit.

## 4. Review pending information

1. Periodically search for `PENDING` and `ASSUMPTION` status documents
   (`python3 scripts/search_brain.py "PENDING"` or `"ASSUMPTION"`, or grep for `status: PENDING` /
   `status: ASSUMPTION` in frontmatter) rather than waiting for them to surface incidentally.
2. For each one, ask: is the blocking information now available? If yes, update status and
   `last_verified` per §2 above. If no, leave it — a stale `PENDING` marker is honest; a guessed
   `CONFIRMED` is not.
3. Prioritize reviewing `PENDING` items that other documents actively depend on or link to — an
   unresolved dependency blocking multiple documents is higher-value to resolve than an isolated one.

## 5. Verify official documentation sources

1. Prefer the authoritative source named in `README.md` §Source verification and accuracy (AWS docs,
   Terraform docs, Docker docs, Kubernetes docs, GitHub Actions docs) over secondary summaries or
   memory.
2. When a fetched source gives an AI-summarized answer rather than the primary document's own text (for
   example, a tool that paraphrases a page), treat that summary as unverified until cross-checked against
   the actual primary source text — a summary can misstate a detail the original didn't.
3. Record the specific URL(s) consulted in the document's References section, not just "AWS
   documentation" vaguely, so a future reader or AI agent can re-verify independently.
4. If a claim can't be verified against an authoritative source, mark it `PENDING` or `ASSUMPTION`
   explicitly rather than presenting it as checked.

## 6. Run validation before approving changes

1. Always run `python3 scripts/check_brain.py` before presenting a change for approval — not after.
2. Treat new `ERRORS` as blocking; `WARNINGS` should be read and either fixed or consciously accepted
   with a stated reason (e.g. a pre-existing legacy document not yet migrated to frontmatter).
3. Validation passing is not proof of factual correctness — it's a hygiene/structure check (broken
   links, missing sections, secret patterns, missing status). Factual accuracy still depends on §5.
4. For changes touching runbooks specifically, also confirm the required-section check passes for the
   runbook's profile (extended ECS-style or simple template-style) — see `scripts/check_brain.py`.

## Security considerations

Every step above inherits the no-secrets rule from `SECURITY.md` — validation's secret-pattern check is
a backstop, not a substitute for not writing a secret down in the first place.

## Related documents

- `AGENTS.md` — the AI agent rules this workflow operationalizes, including the knowledge-retrieval
  instructions.
- `core/standards/change-safety.md` — the general change-safety principles.
- `core/standards/knowledge-quality.md` — required metadata fields.
- `core/standards/document-metadata.md` — the frontmatter standard and migration strategy.
- `scripts/check_brain.py` — the validation script referenced throughout.
- `scripts/search_brain.py` — the search tool referenced throughout.
- `templates/knowledge-update.md` — the proposal template for a knowledge-update task.
