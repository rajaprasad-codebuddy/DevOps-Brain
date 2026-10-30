---
title: "ECS task definitions"
category: pattern
technology: ecs
status: CONFIRMED
created: 2026-10-30
last_verified: 2026-10-30
source: "AWS documentation (see References section)"
---

# ECS task definitions

**Status:** CONFIRMED against AWS documentation (see References). Some parameters below are documented
by AWS primarily for Fargate; where EC2 behavior differs or a requirement is relaxed on EC2, this is
called out explicitly.

## 1. Purpose

Explain what a task definition is, how its parts fit together, and how to configure the parts you'll
touch most often: containers, CPU/memory, environment variables, secrets, logging, health checks, and
volumes. This document assumes the vocabulary from `fundamentals.md` (cluster, service, task, container)
and the resource-reservation concepts from `instance-capacity-and-placement.md`.

## 2. Prerequisites

- Read `fundamentals.md` first — this document builds directly on its task/task-definition/service
  definitions.
- Familiarity with basic Docker concepts (image, container, environment variable, volume) is assumed.

## 3. What is a task definition?

A task definition is a **versioned JSON blueprint** for one or more containers that run together as a
single task. It specifies: the container image(s) to run, how much CPU/memory the task (and optionally
each container) gets, networking mode, IAM roles, logging, health checks, and volumes. Registering a
task definition does not run anything by itself — a task definition only becomes running containers when
you `RunTask` directly or create/update a **service** that references it (see `fundamentals.md` §3).

## 4. Task definition vs. task vs. service (recap)

| Concept | Relationship |
|---|---|
| **Task definition** | The blueprint — a specific **family + revision**, e.g. `<project>-api-prod:7`. |
| **Task** | One running instantiation of a task definition — launched by a service or by a direct `RunTask` call. |
| **Service** | Keeps a desired number of tasks of one task definition revision running, handling restarts and rolling updates. |

Full detail on this relationship is in `fundamentals.md` §3 — this table is a recap, not a replacement.

## 5. Task definition revisions

A task definition has a stable **family** name and an incrementing **revision** number. The first
registration of a family is revision `1`; every subsequent `register-task-definition` call for the same
family creates a new, immutable revision (`2`, `3`, ...). Revisions are never edited in place — "updating
a task definition" always means registering a new revision and then pointing a service at it. This
immutability is what makes rollback possible: rolling back a bad deployment usually means updating the
service back to the previous revision number (see `deployment.md`).

## 6. Container definitions

Each task definition contains one or more **container definitions**. Key fields:

| Field | Purpose |
|---|---|
| `name` | The container's name within the task — used for port mapping names, `dependsOn`, and log stream naming. |
| `image` | The image URI to run, e.g. `<ECR_REPO_URI>/<project>-api:<GIT_SHA>`. Always use an immutable tag (Git SHA or version), never `:latest`, for anything deployed (see `core/standards/naming-conventions.md`). |
| `essential` | See §9 below. |
| `portMappings` | See §7. |
| `environment` / `secrets` | See §8. |
| `logConfiguration` | See §10. |
| `healthCheck` | See §11. |
| `mountPoints` | See §12. |
| `dependsOn` | See §13. |

## 7. Port mappings

`portMappings` exposes a container's port. Behavior depends on network mode (full detail in
`networking.md`):

- **`awsvpc` mode** (recommended): specify only `containerPort`. `hostPort` is ignored — AWS maps the
  container port straight to the task's own elastic network interface (ENI).
- **`bridge` mode**: you may specify `hostPort`, or leave it blank for Docker to assign a random
  high-numbered host port — this is **dynamic host port mapping**, which is what allows multiple tasks
  from the same service to run on one EC2 instance without a port conflict.
- **`host` mode**: `hostPort` must either be left unspecified or match `containerPort` exactly — and
  because the task uses the instance's own network namespace directly, no two tasks using the same
  host port can run on one instance at the same time.

```json
"portMappings": [
  { "containerPort": 8080, "protocol": "tcp" }
]
```

## 8. Environment variables and secrets

- `environment` — plain key/value pairs baked into the task definition. **Never put a secret value
  here** — it is visible in the task definition JSON to anyone who can call `DescribeTaskDefinition`
  (see `SECURITY.md`).
- `secrets` — injects a value from AWS Secrets Manager or SSM Parameter Store as an environment variable
  at container start, without the value ever appearing in the task definition itself:

```json
"secrets": [
  { "name": "DATABASE_PASSWORD", "valueFrom": "<SECRET_ARN>" }
]
```

`valueFrom` takes the full ARN of the Secrets Manager secret or SSM parameter. Retrieving it at
container start requires the **task execution role** to have `secretsmanager:GetSecretValue` (or
`ssm:GetParameters`) on that specific ARN — covered in `iam-roles-and-permissions.md`.

## 9. Essential vs. non-essential containers

`essential` (boolean, default `true` if omitted): if an essential container stops for any reason, **ECS
stops every other container in the task** — the whole task is considered failed. If a non-essential
container stops, the rest of the task keeps running unaffected. Every task must have at least one
essential container.

Use non-essential containers for auxiliary work (e.g. a one-shot init step, a log-shipping sidecar whose
failure shouldn't take down the main application) — not for anything the task actually depends on to
function.

## 10. Logging configuration — `awslogs`

```json
"logConfiguration": {
  "logDriver": "awslogs",
  "options": {
    "awslogs-group": "<LOG_GROUP_NAME>",
    "awslogs-region": "<AWS_REGION>",
    "awslogs-stream-prefix": "<project>"
  }
}
```

- `awslogs-group` (required) — the destination CloudWatch Logs log group. It must already exist unless
  you also set `awslogs-create-group: "true"` (requires `logs:CreateLogGroup` on the execution role).
- `awslogs-region` (required) — the region the log group lives in.
- `awslogs-stream-prefix` (required) — combined with the container name and task ID to form the log
  stream name; required to use the modern multi-container log stream format.
- Writing logs requires the **task execution role** to have `logs:CreateLogStream` and
  `logs:PutLogEvents` on that log group — see `iam-roles-and-permissions.md`.

## 11. Health checks

A container-level `healthCheck` runs a command inside the container on an interval to determine
liveness, independent of any ALB target group health check (see `networking.md` §Health checks for how
the two relate during a deployment):

```json
"healthCheck": {
  "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
  "interval": 30,
  "timeout": 5,
  "retries": 3,
  "startPeriod": 60
}
```

- `interval` — seconds between checks (5–300, default 30).
- `timeout` — seconds to wait for the check to finish before it counts as a failure (2–60, default 5).
- `retries` — consecutive failures before the container is marked unhealthy (1–10, default 3).
- `startPeriod` — grace period after container start during which failures don't count toward
  `retries`, so a slow-starting application doesn't get killed prematurely (0–300, disabled by default).

## 12. Volumes and mount points

A task definition can declare `volumes` (e.g. a Docker volume, a bind mount to the host, or an EFS
volume) at the task level, then reference them per-container via `mountPoints`:

```json
"mountPoints": [
  { "sourceVolume": "<VOLUME_NAME>", "containerPath": "/data", "readOnly": false }
]
```

Prefer `readOnly: true` unless the container genuinely needs to write — this limits the blast radius of
a compromised or misbehaving container (see `core/standards/aws-security.md`).

## 13. Container dependencies (`dependsOn`)

`dependsOn` orders startup (and, in reverse, shutdown) between containers in the same task:

| Condition | Meaning |
|---|---|
| `START` | The dependency container must have started before this one starts. |
| `COMPLETE` | The dependency container must have exited before this one starts (non-essential containers only). |
| `SUCCESS` | Same as `COMPLETE`, but the dependency must have exited with status `0` (non-essential containers only). |
| `HEALTHY` | The dependency container must have passed its own `healthCheck` before this one starts. |

```json
"dependsOn": [
  { "containerName": "<SIDECAR_NAME>", "condition": "HEALTHY" }
]
```

## 14. CPU and memory configuration (recap)

Full accounting detail (how this affects scheduling/placement) is in
`instance-capacity-and-placement.md` §2. Summary:

- **Task-level `cpu`/`memory`** — the total budget for the whole task; on EC2 this is used by the
  scheduler for placement accounting.
- **Container-level `memory` (hard limit)** — the container is killed if it exceeds this.
- **Container-level `memoryReservation` (soft limit)** — used for placement; the container may burst
  above it up to the hard limit if the instance has spare capacity.

## 15. Task execution role and task role (recap)

A task definition references two separate IAM roles via `executionRoleArn` and `taskRoleArn`. They are
easy to confuse — the full breakdown, including trust policies and least-privilege examples, is in
`iam-roles-and-permissions.md`. In short: the **execution role** is used by the ECS agent/infrastructure
(image pull, log writing, secret retrieval before the container starts); the **task role** is used by
your application code inside the container.

## 16. Registering a task definition

```bash
aws ecs register-task-definition --cli-input-json file://<TASK_DEFINITION_FILE>.json
```

This returns the full registered task definition including its new revision number. Check it:

```bash
aws ecs describe-task-definition --task-definition <TASK_DEF_FAMILY> \
  --query 'taskDefinition.{family:family,revision:revision,status:status}'
```

Point a service at the new revision with `aws ecs update-service --task-definition <family>:<revision>`
— this is covered end-to-end, including rollout behavior, in `deployment.md`.

## 17. Practical example

A minimal but realistic EC2-launch-type task definition, using placeholders throughout:

```json
{
  "family": "<project>-api-<env>",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["EC2"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "<EXECUTION_ROLE_ARN>",
  "taskRoleArn": "<TASK_ROLE_ARN>",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<ECR_REPO_URI>/<project>-api:<GIT_SHA>",
      "essential": true,
      "portMappings": [
        { "containerPort": 8080, "protocol": "tcp" }
      ],
      "environment": [
        { "name": "APP_ENV", "value": "<env>" }
      ],
      "secrets": [
        { "name": "DATABASE_PASSWORD", "valueFrom": "<SECRET_ARN>" }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "<LOG_GROUP_NAME>",
          "awslogs-region": "<AWS_REGION>",
          "awslogs-stream-prefix": "<project>"
        }
      }
    }
  ]
}
```

## 18. How this connects to services and EC2 capacity

Registering this task definition does nothing by itself. A **service** (`fundamentals.md` §3, §6)
references a family:revision and a desired count; the ECS **scheduler** then tries to place that many
task instances onto currently registered, `ACTIVE` container instances with enough free CPU/memory to
satisfy this task definition's requirements (`instance-capacity-and-placement.md` §1–§3). If no
container instance has room, the task stays `PENDING` regardless of how correct the task definition
itself is — a task definition problem and a capacity problem produce a similar-looking symptom
(`pendingCount > 0`) but need different fixes.

## 19. Common configuration mistakes

- Using `:latest` as the image tag — makes it impossible to know exactly what's running or to roll back
  precisely.
- Putting a secret value directly in `environment` instead of referencing it via `secrets`.
- Setting `memoryReservation` far below real usage to fit more tasks per instance — risks real OOM kills
  under load (see `instance-capacity-and-placement.md` §7).
- Forgetting `awslogs-stream-prefix` — some AWS console flows and CLI examples omit it by habit, but it
  is required when using the `awslogs` driver.
- Setting an aggressive `healthCheck` `startPeriod` too short for a slow-starting application, causing
  healthy containers to be killed before they finish booting.
- Marking a container `essential: false` that the application actually depends on, which can mask a real
  failure instead of surfacing it.

## 20. Troubleshooting (pointer only)

Full runbooks (e.g. "task stuck in PENDING," "task repeatedly stopping") are planned for Phase 5. As a
starting point: a task that stops immediately after starting is usually an application/health-check
problem — check `aws ecs describe-tasks ... --query 'tasks[0].stoppedReason'` and the container's
CloudWatch log stream. A task that never leaves `PENDING` is usually a capacity or placement problem —
see `instance-capacity-and-placement.md` §6.

## 21. Security considerations

- Never put secret values in `environment` — see §8 and `SECURITY.md`.
- Prefer `readOnly: true` on mount points unless write access is required (§12).
- Scope the execution role's secret-retrieval permissions to the specific secret ARN, not a wildcard —
  see `core/standards/aws-security.md` and `iam-roles-and-permissions.md`.

## 22. References

- Task definition parameters: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html
- Pass sensitive data to a container (secrets): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html
- Send ECS logs to CloudWatch (awslogs): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_awslogs.html
- Container health checks: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html
- Example task definitions (including container dependency examples): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/example_task_definitions.html

## Related documents

- `fundamentals.md` — task/task definition/service vocabulary.
- `instance-capacity-and-placement.md` — how CPU/memory settings affect scheduling.
- `iam-roles-and-permissions.md` — full execution role vs. task role breakdown.
- `networking.md` — network modes and port mapping in depth.
- `deployment.md` — how a new revision actually gets rolled out.
- `core/standards/naming-conventions.md` — image tagging and family naming.
