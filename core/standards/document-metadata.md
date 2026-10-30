---
title: "Document metadata standard"
category: standard
technology: general
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "Repository policy (introduced in Phase 6)"
---

# Document metadata standard

## Purpose

As this Brain grows toward hundreds of documents, prose alone (a sentence like "Status: CONFIRMED...")
is hard for tooling to search, filter, or validate reliably. This standard introduces a small, optional
YAML frontmatter block that machine-readable tools (`scripts/check_brain.py`,
`scripts/search_brain.py`) can parse directly, without regex-guessing at prose.

This is additive, not a replacement for the existing bold-field convention
(`core/standards/knowledge-quality.md`) — a document can have both, and older documents are not
required to migrate immediately (see §Migration strategy).

## Format

A frontmatter block, if present, is the very first thing in the file: a `---` line, YAML key/value
pairs, a closing `---` line, then the normal Markdown content (starting with the `# Title` heading).

```markdown
---
title: ECS fundamentals (EC2 capacity model)
category: pattern
technology: ecs
status: CONFIRMED
created: 2026-10-30
last_verified: 2026-10-30
source: AWS documentation (see References section)
---

# ECS fundamentals (EC2 capacity model)
...
```

## Fields

| Field | Required | Meaning |
|---|---|---|
| `title` | Yes, if frontmatter is present | Should match the `# H1` heading below it. Lets tooling list documents without re-parsing the body. |
| `category` | Yes | One of: `pattern`, `runbook`, `standard`, `project`, `decision`, `incident`, `learning`, `template`, `index`. Matches the Brain's top-level knowledge categories. |
| `technology` | Yes | A short lowercase tag: `ecs`, `iam`, `networking`, `terraform`, `docker`, `github-actions`, `aws` (general), or `general` for non-technology-specific standards. Supports `--technology` search filtering. |
| `status` | Yes | One of `CONFIRMED`, `ASSUMPTION`, `PENDING`, `DEPRECATED` — see §Status definitions. |
| `created` | Yes | `YYYY-MM-DD` the document was first written, or `Unknown` for pre-existing documents being migrated without reliable history. |
| `last_verified` | Yes for `CONFIRMED` documents | `YYYY-MM-DD` of the most recent check against an authoritative source, or `Unknown`. Required when `status: CONFIRMED` — a confirmed fact with no verification date is a contradiction in terms. |
| `source` | Yes | A short pointer, e.g. "AWS documentation (see References section)", a ticket ID, or "Observed in production — see Evidence section." Not a full citation list — that belongs in the document body. |

## Status definitions

These four statuses are used consistently across the whole Brain, in frontmatter or in prose:

- **`CONFIRMED`** — verified against an authoritative source (official documentation, a tested command,
  a reviewed production observation). Must carry a real `last_verified` date, not `Unknown`.
- **`ASSUMPTION`** — plausible and reasoned, but not independently verified. Safe to use as a starting
  point; flag before relying on it for a production decision.
- **`PENDING`** — incomplete, a placeholder, or waiting on information/confirmation. Expected for
  in-progress project documents and templates.
- **`DEPRECATED`** — no longer valid. Kept only if useful for history; link to its replacement if one
  exists.

## Migration strategy

**Do not add frontmatter to every file mechanically.** Apply it where it earns its keep:

1. **Migrate now:** documents that are mature, technology-specific, and heavily cross-referenced or
   likely to be searched — the `core/patterns/aws/ecs/` pattern documents, the
   `core/runbooks/aws/ecs/` runbooks, and the `core/standards/` documents. These are exactly the
   documents `scripts/search_brain.py`'s `--technology`/`--category` filters are most useful against.
2. **Migrate opportunistically:** the next time an existing document without frontmatter is materially
   updated, add frontmatter as part of that change rather than as a separate mechanical pass.
3. **Don't migrate:** pure navigational `README.md`/index files (frontmatter adds no search value to a
   file that's just a table of links), `templates/*.md` (they're generic skeletons, not facts to find),
   and placeholder project documents that are entirely `PENDING`/`Unknown` already (nothing to confirm
   yet, and adding frontmatter to an empty placeholder is exactly the "blind migration" this standard
   warns against).
4. **Never required retroactively:** `scripts/check_brain.py`'s status/date checks accept *either*
   frontmatter *or* the existing bold-field convention (`**Status:** ...`) — a document is never flagged
   just for predating this standard.

## Security considerations

Frontmatter is plain text in the same file — the no-secrets rule in `SECURITY.md` applies to it exactly
as it does to the rest of the document. Never put a real resource ID, account ID, or sensitive value in
`source` or any other field.

## Related documents

- `core/standards/knowledge-quality.md` — the pre-existing bold-field metadata convention this standard
  complements.
- `README.md` — root-level fact-status definitions (kept consistent with §Status definitions here).
- `scripts/check_brain.py` — validates frontmatter where present.
- `scripts/search_brain.py` — uses frontmatter for `--category`/`--technology` filtering.
