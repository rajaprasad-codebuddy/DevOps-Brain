---
title: "Runbook: ECS task repeatedly stopping"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: ECS task repeatedly stopping

## 1. Title and purpose

A task reaches `RUNNING` (unlike the `ecs-service-stuck-pending.md` scenario) but then stops — once, or
repeatedly in a restart loop. This runbook diagnoses why, using the task's `stoppedReason` and AWS's
documented stopped-task error categories as the starting point rather than guessing from symptoms alone.

## 2. Symptoms

- A service's `runningCount` fluctuates or never stabilizes even though tasks do briefly start.
- `aws ecs describe-tasks` shows `lastStatus: "STOPPED"` with a `stoppedReason`.
- The same task definition keeps producing new tasks that stop shortly after starting (a restart loop).

## 3. Possible root causes

AWS categorizes stopped-task errors; do not assume the category before checking `stoppedReason` (§7):

| Category | Typical meaning |
|---|---|
| `CannotPullContainer` | Image can't be retrieved — permissions, network, tag/digest, or registry issue. |
| `ResourceInitializationError` | A dependency the container needs before it can start (secrets, env files from S3, log group) couldn't be initialized — usually network or IAM. |
| `OutOfMemoryError` | Container exceeded its hard memory limit. |
| `TaskFailedToStart` | The task failed during the startup phase for a reason other than the above. |
| `ContainerRuntimeError` / `ContainerRuntimeTimeoutError` | Docker/containerd-level failure starting or managing the container. |
| `CannotStartContainerError` / `CannotStopContainerError` / `CannotInspectContainerError` | Docker daemon-level failure performing a specific lifecycle operation. |
| `CannotCreateVolumeError` | A declared volume (e.g. EFS) couldn't be created/mounted. |
| `SpotInterruptionError` | The underlying Spot Instance was reclaimed — not a configuration problem. |
| Essential container exited (non-category-specific) | A container marked `essential` in the task definition exited, stopping the whole task — see `core/patterns/aws/ecs/task-definitions.md` §9. |
| Failed container health check | The container's own `healthCheck` failed enough times to be considered unhealthy. |

## 4. Architecture context

Full background: `core/patterns/aws/ecs/task-definitions.md` (essential containers §9, health checks
§11, CPU/memory §14) and `core/patterns/aws/ecs/iam-roles-and-permissions.md` §4 (task execution role —
relevant to `CannotPullContainer` and `ResourceInitializationError`). A task stopping is fundamentally
different from a task never starting (`ecs-service-stuck-pending.md`) — here, placement succeeded and
the failure is in container startup, runtime, or health, not scheduling.

## 5. Prerequisites and required permissions

Read-only IAM permissions: `ecs:DescribeTasks`, `ecs:ListTasks`, `ecs:DescribeTaskDefinition`,
`logs:GetLogEvents`, `logs:DescribeLogStreams`.

## 6. Step-by-step investigation

1. Get the task's `stoppedReason` and category — this is the single most important first step and
   usually points directly at one of the categories in §3.
2. If `CannotPullContainer` — check image existence/tag, then execution role permissions
   (`core/patterns/aws/ecs/iam-roles-and-permissions.md` §4), then network path to ECR
   (`ecs-ecr-image-pull-failed.md`).
3. If `ResourceInitializationError` — identify which dependency failed (secrets, S3 env file, log group)
   from the specific message text, then check that dependency's connectivity or permissions.
4. If `OutOfMemoryError` — compare the container's actual memory usage (CloudWatch metrics, if
   available) against its hard `memory` limit in the task definition.
5. If an essential container exited with a non-zero code, or failed its health check — read the
   container's own application logs for the actual application-level error, since ECS only reports that
   it exited/failed health checks, not why the application itself failed.
6. If the pattern is a repeating restart loop rather than a single stop, check whether every restart
   shows the *same* `stoppedReason` (a consistent root cause) or *different* reasons each time (possible
   environmental flakiness, e.g. intermittent network issues or a resource-starved instance).

## 7. Read-only AWS CLI commands

```bash
# Primary signal: why did this task stop?
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn> \
  --query 'tasks[0].{lastStatus:lastStatus,stoppedReason:stoppedReason,containers:containers[*].{name:name,exitCode:exitCode,reason:reason}}'
```

```bash
# List recently stopped tasks for this service, to see if it's a pattern or a one-off
aws ecs list-tasks --cluster <cluster-name> --service-name <service-name> --desired-status STOPPED
```

```bash
# Confirm the task definition's own expectations (memory limits, health check, logging)
aws ecs describe-task-definition --task-definition <task-definition-family>:<revision> \
  --query 'taskDefinition.containerDefinitions[*].{name:name,memory:memory,memoryReservation:memoryReservation,healthCheck:healthCheck,essential:essential}'
```

```bash
# Read the container's own application log, once you know the log group/stream
aws logs get-log-events \
  --log-group-name <log-group-name> \
  --log-stream-name <log-stream-name> \
  --limit 100
```

All commands above are read-only.

## 8. Expected output or relevant output fields

- `stoppedReason` on a healthy, intentionally-stopped task (e.g. a one-off `RunTask` finishing normally)
  is empty or benign; any non-empty `stoppedReason` on a service task is worth investigating.
- `containers[*].exitCode` — a non-zero exit code on an essential container confirms root cause
  "Essential container exited" from the application's own perspective, independent of any ECS-level
  category.
- `containers[*].reason` often repeats the same category text as `stoppedReason` at the container level,
  sometimes with more specific detail (e.g. the exact Secrets Manager ARN that couldn't be retrieved).

## 9. How to interpret the results

| `stoppedReason` text (abbreviated) | Interpretation |
|---|---|
| "task can't pull the image. Check that the role has the permissions..." | Execution role (EC2: container instance role) missing ECR permissions — see `core/patterns/aws/ecs/iam-roles-and-permissions.md` §4/§6. |
| "...connection issue between the task and Amazon ECR..." | Network path problem, not permissions — see `ecs-ecr-image-pull-failed.md`. |
| "...can't retrieve the secret with ARN '...' from Secrets Manager..." | Either the ARN is wrong/doesn't exist, or the execution role lacks `secretsmanager:GetSecretValue` on it. |
| "...cannot find the Amazon CloudWatch log group..." | The `awslogs-group` in the task definition doesn't exist, or there's a connectivity problem to the CloudWatch Logs endpoint. |
| `OutOfMemoryError` | Container's actual usage exceeded its hard `memory` limit — this is an application/sizing problem, not a connectivity one. |
| Essential container exited, exit code non-zero, no ECS-level category | The application itself crashed or exited — the real cause is in the application logs, not the ECS metadata. |

## 10. Root-cause identification

State the exact `stoppedReason` text plus the specific resource it names (the secret ARN, the log group
name, the image tag) — this level of specificity is what separates "the task keeps failing" from an
actionable finding.

## 11. Resolution options

**Documented recommendations only — see §12.**

- Missing execution-role permission → add the specific, narrowly-scoped permission per
  `core/patterns/aws/ecs/iam-roles-and-permissions.md` §4.
- Wrong/missing secret ARN or log group → correct the task definition and register a new revision
  (`core/patterns/aws/ecs/task-definitions.md` §16) — never edit a revision in place.
- `OutOfMemoryError` → raise the container's `memory`/`memoryReservation` in a new revision, after
  confirming the actual usage pattern, or fix an application-level memory leak if usage is abnormal.
- Application-level crash → fix the application; ECS can't resolve an application bug.
- Network path problem → see `ecs-ecr-image-pull-failed.md` or `ecs-networking-connectivity.md`.

## 12. Risks and approval requirements

- Registering a new task definition revision and updating the service is a production deployment —
  follow `core/standards/deployment-standards.md` (pre-deployment checks, approval) even for what looks
  like a small fix.
- Do not raise memory/CPU limits reflexively without understanding why usage increased — this can mask
  a real application problem (e.g. a memory leak) instead of fixing it.
- Do not disable a failing health check to "make the task stay running" — this hides a real application
  problem from the ALB/service and risks serving broken traffic to users.

## 13. Post-resolution verification

```bash
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn> --query 'tasks[0].lastStatus'
```

Confirm the new task reaches and *stays* `RUNNING` — check again a few minutes later, since a restart
loop can briefly show `RUNNING` before stopping again.

## 14. Related Brain documentation

- `core/patterns/aws/ecs/task-definitions.md` — essential containers, health checks, CPU/memory.
- `core/patterns/aws/ecs/iam-roles-and-permissions.md` §4 — task execution role.
- `core/runbooks/aws/ecs/ecs-ecr-image-pull-failed.md` — image pull failures specifically.
- `core/runbooks/aws/ecs/ecs-iam-permission-denied.md` — permission-denied failures across all roles.

## 15. Official AWS references

- ECS stopped task error codes (category index): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/stopped-task-error-codes.html
- `ResourceInitializationError` troubleshooting: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/resource-initialization-error.html
- `CannotPullContainer` troubleshooting: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_cannot_pull_image.html
- Container health checks: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html

## 16. Verification status

CONFIRMED — stopped-task error categories and the specific error message text in §9 were fetched
directly from AWS's own troubleshooting documentation for this runbook.
