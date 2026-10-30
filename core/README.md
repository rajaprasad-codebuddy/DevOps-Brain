# Shared core

Only put reusable, cross-project knowledge here.

Examples:
- organization-wide approved engineering standards
- generic Terraform, CI/CD, Docker, observability patterns
- reusable runbooks with placeholders

Do not put account IDs, hostnames, project-specific resource names, customer facts, or environment-specific status here unless explicitly approved as a shared fact.

## What's here

| Folder | Contents |
|---|---|
| [standards/](standards/) | Organization-wide rules: change safety, knowledge quality, document metadata, the knowledge maintenance workflow, AWS security, deployment standards, naming conventions. |
| [patterns/aws/](patterns/aws/README.md) | AWS architecture patterns by service — currently ECS on EC2 in depth; see that index for coverage status. |
| [patterns/terraform.md](patterns/terraform.md), [patterns/github-actions.md](patterns/github-actions.md) | Generic Terraform and GitHub Actions checklists. |
| [runbooks/aws/ecs/](runbooks/aws/ecs/README.md) | Troubleshooting runbooks for ECS on EC2 — read-only investigation, documented resolutions, human-approved execution. |

## Finding something

- `python3 scripts/search_brain.py "<keyword>"` searches every document in `core/` (and the rest of the
  Brain) by keyword, title, technology, or category — faster than browsing folders by hand once this
  grows.
- `python3 scripts/check_brain.py` validates structure (links, required sections, status metadata) —
  run it after any edit here, before requesting approval.

## Related documents

- `README.md` (root) — the Brain's overall map and fact-status definitions.
- `core/standards/knowledge-maintenance-workflow.md` — how to add, update, or deprecate anything in
  this folder.
