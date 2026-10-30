# Knowledge quality standard

## Required metadata for project-specific facts
- `status`: CONFIRMED, ASSUMPTION, PENDING, or DEPRECATED
- `owner`: team/person/role if known; otherwise `Unknown`
- `last_verified`: `YYYY-MM-DD` or `Unknown`
- `source`: authoritative file, ticket, approved change, or observation; use a sanitized reference

## Writing rules
- Prefer concise steps and concrete expected outcomes.
- Distinguish observed facts from recommendations.
- Include exact commands only when safe and verified.
- Mark environment and region explicitly when relevant.
- Add a verification step and rollback/stop condition to operational procedures.
- Link to a single source of truth rather than duplicating long content.
- Never infer that a resource exists merely because it appears in an old note.
