# ECS on EC2 — troubleshooting runbooks

Practical, production-oriented troubleshooting runbooks for Amazon ECS on EC2. These reuse the concepts
explained in `core/patterns/aws/ecs/` rather than re-explaining them — read the relevant pattern
document first if a term here is unfamiliar.

**This is a knowledge repository, not an automatic remediation system.** Every runbook separates
read-only investigation from documented resolution options from execution — executing any fix requires
explicit human approval. No runbook here contains a command that mutates an AWS resource.

## Runbooks

| Runbook | Symptom it addresses |
|---|---|
| [ec2-instance-not-registering.md](ec2-instance-not-registering.md) | An EC2 instance exists but never becomes a usable ECS container instance. |
| [ecs-service-stuck-pending.md](ecs-service-stuck-pending.md) | A service's `runningCount` won't reach `desiredCount`; tasks stay `PENDING`. |
| [ecs-task-stopped.md](ecs-task-stopped.md) | A task reaches `RUNNING` but then stops, once or repeatedly. |
| [ecs-deployment-failed.md](ecs-deployment-failed.md) | A service update/deployment is stuck `IN_PROGRESS` or transitions to `FAILED`. |
| [ecs-capacity-provider-scaling.md](ecs-capacity-provider-scaling.md) | A capacity provider isn't scaling its backing ASG out (or in) as expected. |
| [ecs-insufficient-capacity.md](ecs-insufficient-capacity.md) | CPU/memory placement failures that persist despite apparently-sufficient cluster-wide capacity (fragmentation). |
| [ecs-alb-health-check-failed.md](ecs-alb-health-check-failed.md) | Tasks are `RUNNING` but the ALB target group never considers them healthy. |
| [ecs-ecr-image-pull-failed.md](ecs-ecr-image-pull-failed.md) | A task stops with a `CannotPullContainer`-category error. |
| [ecs-iam-permission-denied.md](ecs-iam-permission-denied.md) | An ECS-related operation fails with an IAM access-denied error — identifying which of the five roles is at fault. |
| [ecs-networking-connectivity.md](ecs-networking-connectivity.md) | General outbound/inbound network connectivity failures, with a decision tree. |

## Recommended reading order

If you're building familiarity rather than chasing a live incident:

1. `ec2-instance-not-registering.md` — the most foundational failure (no capacity at all).
2. `ecs-service-stuck-pending.md` and `ecs-insufficient-capacity.md` — placement failures once capacity
   exists.
3. `ecs-task-stopped.md`, `ecs-ecr-image-pull-failed.md` — startup/runtime failures once a task places.
4. `ecs-alb-health-check-failed.md`, `ecs-networking-connectivity.md` — connectivity once a task runs.
5. `ecs-deployment-failed.md`, `ecs-capacity-provider-scaling.md` — the automation layers (deployments,
   scaling) that tie the above together over time.
6. `ecs-iam-permission-denied.md` — a cross-cutting reference, since IAM denials can appear as the root
   cause behind several of the above symptoms.

## Symptom-based navigation

| If you're seeing... | Start here |
|---|---|
| A new EC2 instance never shows up in the cluster | `ec2-instance-not-registering.md` |
| `pendingCount > 0` and it won't resolve | `ecs-service-stuck-pending.md` |
| Placement failure despite "enough" total cluster capacity | `ecs-insufficient-capacity.md` |
| A task starts then stops, with any `stoppedReason` | `ecs-task-stopped.md` |
| Specifically an image-pull-flavored `stoppedReason` | `ecs-ecr-image-pull-failed.md` |
| Specifically an access-denied/permissions-flavored error anywhere | `ecs-iam-permission-denied.md` |
| A deployment won't finish or rolled back | `ecs-deployment-failed.md` |
| Capacity provider / ASG not growing or shrinking as expected | `ecs-capacity-provider-scaling.md` |
| Tasks run but the ALB never sends them traffic | `ecs-alb-health-check-failed.md` |
| Any other "can't reach X" symptom not covered above | `ecs-networking-connectivity.md` |

## Format

Every runbook in this set follows the same 16-section structure: title/purpose, symptoms, possible root
causes, architecture context, prerequisites, step-by-step investigation, read-only CLI commands,
expected output, interpretation, root-cause identification, resolution options, risks/approval
requirements, post-resolution verification, related Brain documentation, official AWS references, and a
verification status. All AWS CLI commands shown are read-only (`describe-*`/`list-*`/`get-*`); none
create, modify, or delete a resource.

## Related documentation

- `core/patterns/aws/ecs/` — the conceptual documentation this runbook set assumes and cross-references
  throughout.
- `core/standards/change-safety.md`, `core/standards/deployment-standards.md`,
  `core/standards/aws-security.md` — the standards every runbook's "Resolution options" and "Risks and
  approval requirements" sections point back to.
- `templates/runbook.md` — the simpler, generic runbook template used elsewhere in this Brain; the ECS
  runbooks here use an extended 16-section format specific to this topic area's complexity.
