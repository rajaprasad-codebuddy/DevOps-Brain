---
title: "AWS patterns index"
category: pattern
technology: aws
status: PENDING
created: 2026-10-31
last_verified: Unknown
source: "Index — see linked documents for their own sources"
---

# AWS patterns index

Shared, reusable AWS architecture and operational knowledge, organized by service. This folder's own
status is `PENDING` because it's an index of in-progress coverage, not a technical claim itself.

## Coverage

| Service | Status | Where |
|---|---|---|
| ECS (EC2 capacity model) | Documented — fundamentals, EC2 capacity, task definitions, IAM, networking, deployment | [ecs/README.md](ecs/README.md) |
| VPC / networking | Not yet documented as a standalone service pattern (ECS-specific networking is covered in `ecs/networking.md`) | Planned |
| IAM (general, beyond ECS) | Not yet documented as a standalone pattern (ECS-specific IAM is covered in `ecs/iam-roles-and-permissions.md`) | Planned |
| EC2 (general, beyond ECS capacity) | Not yet documented | Planned |
| S3 | Not yet documented | Planned |
| RDS | Not yet documented | Planned |
| ALB (general, beyond ECS integration) | Not yet documented as a standalone pattern (ECS-specific ALB integration is covered in `ecs/networking.md` §8 and `ecs/deployment.md` §7) | Planned |
| CloudFront | Not yet documented | Planned |

Expanding this table with real content (not placeholder files) is part of a later phase. Per this
Brain's "progressive creation" principle, no empty placeholder files exist yet for the "Planned" rows —
they'll be created when there's real, verified content to put in them.

## How to find AWS knowledge right now

- Use `python3 scripts/search_brain.py --technology ecs` to list everything currently documented for
  ECS.
- Use `python3 scripts/search_brain.py "<keyword>"` for a keyword search across all AWS patterns and
  runbooks at once.
- `core/runbooks/aws/ecs/README.md` is the troubleshooting-runbook counterpart to this pattern set.

## Related documents

- `core/README.md` — what belongs in `core/` generally.
- `core/standards/aws-security.md`, `core/standards/naming-conventions.md`,
  `core/standards/deployment-standards.md` — AWS-relevant shared standards that apply across every
  service in this table, not just ECS.
