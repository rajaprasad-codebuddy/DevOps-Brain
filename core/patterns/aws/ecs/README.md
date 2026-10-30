# Amazon ECS on EC2 — pattern index

Shared, reusable knowledge about Amazon Elastic Container Service (ECS) using the **EC2 capacity
model**. This is generic conceptual and operational knowledge — it does not describe any specific
project's actual cluster, account, or environment. Project-specific ECS facts (real cluster names, real
task definitions, real scaling numbers) belong in `projects/<project-slug>/`.

## Scope

ECS supports two capacity models: **EC2 launch type** (you provide and manage EC2 instances as
capacity) and **Fargate launch type** (AWS manages the underlying compute, no EC2 instances visible to
you). This pattern set focuses on the **EC2 model**, since that matches the documented working area.
Fargate is mentioned only for contrast where it clarifies an EC2-specific concept.

## Documents in this set

| Document | Covers |
|---|---|
| [fundamentals.md](fundamentals.md) | What ECS is, cluster/service/task/task definition/container relationships, control plane vs. data plane, the ECS agent, container instance registration, and the desired/running/pending count model. |
| [capacity-providers.md](capacity-providers.md) | EC2 launch type vs. capacity providers, Auto Scaling Group (ASG) integration, capacity provider managed scaling, managed termination protection, and ECS cluster auto scaling. |
| [instance-capacity-and-placement.md](instance-capacity-and-placement.md) | EC2 instance type selection, CPU/memory reservation accounting, task placement strategies and constraints, container instance draining, and common EC2 capacity problems. |
| [task-definitions.md](task-definitions.md) | Task definition structure, container definitions, CPU/memory, environment variables and secrets, port mappings, health checks, `awslogs` logging, volumes, essential containers, container dependencies, and revisions. |
| [iam-roles-and-permissions.md](iam-roles-and-permissions.md) | The five distinct IAM roles involved in ECS on EC2 (task execution role, task role, EC2 container instance role, ECS service-linked role, CI/CD deployment role), with least-privilege examples and troubleshooting. |
| [networking.md](networking.md) | VPC layout, security groups, VPC endpoints, ECS network modes (`awsvpc`/`bridge`/`host`), ALB/target group integration, and common networking failures. |
| [deployment.md](deployment.md) | The end-to-end deployment lifecycle, rolling deployment configuration, the deployment circuit breaker, deployment controller types, blue/green concepts, and a GitHub Actions OIDC deployment workflow. |

Planned but not yet written (later phase):
- Individual troubleshooting runbooks (stuck `PENDING` tasks, ASG not launching capacity, ECR pull
  failures, and similar) — these will live under `core/runbooks/` once written, following
  `templates/runbook.md`.

## How to use this material

- Read `fundamentals.md` first if you are new to ECS; it establishes the vocabulary every other document
  assumes.
- Read `capacity-providers.md` and `instance-capacity-and-placement.md` together when designing or
  debugging EC2 capacity behavior — they cover two halves of the same problem (how capacity is
  *supplied*, and how tasks are *placed* onto it).
- Read `task-definitions.md`, `iam-roles-and-permissions.md`, and `networking.md` together when building
  or debugging a specific service — a working task definition, the right IAM roles, and correct
  networking all have to line up before a task actually serves traffic.
- Read `deployment.md` last; it assumes the task definition, IAM, and networking pieces are already in
  place and focuses on how a *change* to them rolls out safely.
- Every AWS CLI example uses placeholders (`<CLUSTER_NAME>`, `<ACCOUNT_ID>`, etc.). Never substitute
  real values into this shared folder — put real values in a project-specific document instead.

## Fact status

This set follows the status labels defined in `README.md`:
`CONFIRMED` (verified against AWS documentation), `ASSUMPTION` (reasonable but unverified), `PENDING`
(incomplete), `DEPRECATED` (superseded). Each document marks status per claim where it matters, not just
once at the top.

## Related standards

- `core/standards/aws-security.md` — IAM least privilege, secrets, network security, auditability.
- `core/standards/deployment-standards.md` — pre-deployment checks, rollback, approval.
- `core/standards/naming-conventions.md` — cluster/service/task-definition/IAM-role naming patterns used
  in the examples below.
