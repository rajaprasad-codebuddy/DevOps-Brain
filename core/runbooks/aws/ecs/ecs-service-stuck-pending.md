---
title: "Runbook: ECS service unable to reach desired count (tasks stuck PENDING)"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: ECS service unable to reach desired count (tasks stuck PENDING)

## 1. Title and purpose

A service's `runningCount` stays below `desiredCount`, with tasks stuck in `PENDING`, for longer than
the time a task normally takes to start. This runbook diagnoses **why the scheduler can't place the
task**, which is a distinct problem from a task that places successfully and then fails (see
`ecs-task-stopped.md` for that case).

## 2. Symptoms

- `aws ecs describe-services` shows `pendingCount > 0` persisting for several minutes or longer.
- Service events (visible in the console or via `describe-services`) report an inability to place a
  task.
- No corresponding entries in `ecs-task-stopped.md`'s territory — the task never reached `RUNNING` in
  the first place, so there's no container-level stopped reason to inspect yet.

## 3. Possible root causes

Checked independently — a pending task can stem from any one of these, and more than one can be true
at once:

1. Insufficient CPU or memory on any single eligible container instance.
2. No available (registered, `ACTIVE`) container instances at all.
3. A placement constraint (e.g. `distinctInstance`) can't currently be satisfied.
4. The placement strategy doesn't prevent placement by itself, but combined with constraints leaves no
   eligible instance.
5. No capacity provider is associated with the cluster/service, or the one associated has no available
   capacity.
6. The backing ASG is already at `MaxSize` and can't scale out further.
7. ENI attachment limit reached on all eligible instances (`awsvpc` mode specifically).
8. Subnet IP address exhaustion (for `awsvpc` tasks needing an IP in that subnet).
9. The task definition requires something no container instance currently has (e.g. a specific Docker
   attribute, or a host port already in use).

## 4. Architecture context

Full background: `core/patterns/aws/ecs/instance-capacity-and-placement.md` (placement strategies/
constraints, resource accounting) and `core/patterns/aws/ecs/capacity-providers.md` (how capacity is
supplied). The scheduler only places a task on a container instance that simultaneously: is `ACTIVE`,
has enough free registered resources, satisfies every placement constraint, and (for `awsvpc` mode) has
ENI/IP capacity available. Any one of these failing is enough to leave the task `PENDING` — this is why
root cause isn't single-cause by design.

## 5. Prerequisites and required permissions

Read-only IAM permissions: `ecs:DescribeServices`, `ecs:DescribeTasks`, `ecs:ListTasks`,
`ecs:DescribeContainerInstances`, `ecs:ListContainerInstances`, `ecs:DescribeCapacityProviders`,
`autoscaling:DescribeAutoScalingGroups`.

## 6. Step-by-step investigation

1. Confirm the symptom and read the service's own event log — ECS often states the reason in plain
   text (§7, §9).
2. Check whether any container instances are registered and `ACTIVE` at all.
3. If instances exist, check their remaining CPU/memory against the task definition's requirements.
4. Check the service's placement constraints and strategy against the current instance count/attributes.
5. If a capacity provider is in use, check its managed scaling status and the backing ASG's current vs.
   maximum capacity.
6. For `awsvpc` tasks, check ENI/subnet IP availability specifically — this is a distinct failure mode
   from CPU/memory.

## 7. Read-only AWS CLI commands

```bash
# Service-level view: counts and the actual service events (often names the cause directly)
aws ecs describe-services --cluster <cluster-name> --services <service-name> \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,events:events[0:5]}'
```

```bash
# Is there any usable capacity at all?
aws ecs list-container-instances --cluster <cluster-name> --filter "status==ACTIVE"
```

```bash
# Per-instance remaining resources — compare against the task definition's cpu/memory
aws ecs describe-container-instances --cluster <cluster-name> --container-instances <container-instance-arn> \
  --query 'containerInstances[0].{remaining:remainingResources,registered:registeredResources,status:status,agentConnected:agentConnected}'
```

```bash
# What does the task definition actually require?
aws ecs describe-task-definition --task-definition <task-definition-family>:<revision> \
  --query 'taskDefinition.{cpu:cpu,memory:memory,networkMode:networkMode}'
```

```bash
# Capacity provider health and managed scaling status
aws ecs describe-capacity-providers --capacity-providers <capacity-provider-name> \
  --query 'capacityProviders[0].{status:status,managedScaling:autoScalingGroupProvider.managedScaling}'
```

```bash
# ASG headroom — can it scale out further?
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names <asg-name> \
  --query 'AutoScalingGroups[0].{desired:DesiredCapacity,min:MinSize,max:MaxSize}'
```

```bash
# Why a specific task is still pending, directly from the task record
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn> \
  --query 'tasks[0].{lastStatus:lastStatus,stoppedReason:stoppedReason}'
```

All commands above are read-only `describe`/`list` calls — none mutate a resource.

## 8. Expected output or relevant output fields

- `events` on a healthy service repeats "has reached a steady state." On a stuck one, look instead for
  text like "was unable to place a task because no container instance met all of its requirements" —
  AWS documents several specific sub-reasons appended to this message (not enough CPU, not enough
  memory, not enough ports, not enough ENI attachment points, container instance missing a required
  attribute) — read the full event text, not just the first clause.
- `remainingResources` with a `CPU` or `MEMORY` entry lower than the task definition's requirement on
  every eligible instance confirms root cause 1.
- `list-container-instances --filter "status==ACTIVE"` returning an empty list confirms root cause 2.
- ASG `DesiredCapacity == MaxSize` confirms root cause 6 — the capacity provider has nowhere further to
  scale.

## 9. How to interpret the results

| Service event text (abbreviated) | Meaning |
|---|---|
| "...insufficient CPU units available" | Root cause 1 (CPU). |
| "...Not enough memory" | Root cause 1 (memory). |
| "No container instances were found in your cluster" | Root cause 2. |
| "No Container Instances were found in your capacity provider" | Root cause 5. |
| "...Not enough available ENI attachment points" | Root cause 7 — `awsvpc` mode specific. |
| "...Container instance missing required attribute" | Root cause 9 — often an `awsvpc` subnet mismatch between the service's network configuration and where container instances actually sit. |
| "...is already using a port required by your task" | Root cause 9 — fixed host port collision, see `core/patterns/aws/ecs/task-definitions.md` §7. |

## 10. Root-cause identification

State which specific reservation or constraint failed, using the exact service event text and the
corresponding `describe-container-instances`/`describe-auto-scaling-groups` output — e.g. "every `ACTIVE`
container instance has less than 512 CPU units remaining, and the ASG is already at `MaxSize=4`," not
just "not enough capacity."

## 11. Resolution options

**Documented recommendations only — see §12 before acting.**

- Insufficient CPU/memory, ASG not at max → allow or trigger capacity provider managed scaling to add
  instances (`core/patterns/aws/ecs/capacity-providers.md` §4–§5).
- ASG at `MaxSize` → raise the ASG's maximum size, after confirming the increase is intentional and
  within account service quotas.
- Placement constraint too restrictive relative to instance count → relax the constraint or add more
  eligible instances (`core/patterns/aws/ecs/instance-capacity-and-placement.md` §4).
- ENI/subnet IP exhaustion → add subnet capacity, use additional subnets in the service's network
  configuration, or opt into the `awsvpcTrunking` account setting for higher ENI density per instance.
- Fixed host port collision → switch to `awsvpc` mode or dynamic host ports (`bridge` mode) instead of
  a fixed `hostPort`.

## 12. Risks and approval requirements

- Changing an ASG's `MaxSize`, a service's placement configuration, or subnet/network configuration are
  all infrastructure changes requiring explicit approval under `core/standards/change-safety.md` and
  `core/standards/deployment-standards.md` — do not apply them as part of investigation.
- Do not force-scale a service or delete/recreate it to "unstick" a pending task before root cause is
  understood — this can mask the actual constraint and make the same failure recur under load.

## 13. Post-resolution verification

```bash
aws ecs describe-services --cluster <cluster-name> --services <service-name> \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'
```

Confirm `running == desired` and `pending == 0`, and that this holds steady (not just momentarily) over
a few minutes.

## 14. Related Brain documentation

- `core/patterns/aws/ecs/instance-capacity-and-placement.md` — placement strategies, constraints, and
  resource accounting.
- `core/patterns/aws/ecs/capacity-providers.md` — managed scaling and ASG integration.
- `core/patterns/aws/ecs/fundamentals.md` §6 — desired/running/pending count definitions.
- `core/runbooks/aws/ecs/ecs-insufficient-capacity.md` — deeper dive specifically on fragmented/
  insufficient resources.
- `core/runbooks/aws/ecs/ecs-capacity-provider-scaling.md` — if the capacity provider itself isn't
  scaling as expected.

## 15. Official AWS references

- ECS service event messages (placement failure reasons, verbatim): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-event-messages-list.html
- Task placement strategies: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-placement-strategies.html
- Task placement constraints: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-placement-constraints.html
- ECS capacity providers: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/cluster-capacity-providers.html

## 16. Verification status

CONFIRMED — service event message text is quoted/paraphrased directly from AWS's own documented list of
service event messages, fetched for this runbook.
