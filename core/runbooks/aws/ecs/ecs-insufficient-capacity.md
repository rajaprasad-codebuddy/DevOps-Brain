---
title: "Runbook: Insufficient CPU or memory for ECS task placement"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: Insufficient CPU or memory for ECS task placement

## 1. Title and purpose

Tasks are `PENDING` and the service event points at CPU/memory, but there appears to be "enough"
capacity in the cluster overall. This runbook focuses specifically on interpreting registered vs.
remaining resources correctly — a narrower, deeper companion to `ecs-service-stuck-pending.md`, which
covers placement failures more broadly.

## 2. Symptoms

- Service event: "...insufficient CPU units available" or "Not enough memory."
- The cluster has multiple container instances, and the *sum* of their free resources looks like it
  should be enough — but tasks still won't place.

## 3. Possible root causes

1. **Fragmentation** — no *single* instance has enough free CPU/memory, even though the total across
   all instances would be enough. Placement is always per-instance, never pooled.
2. The instance type itself is too small for the task definition's requirements, regardless of current
   load — no instance of this type could ever fit this task.
3. A placement constraint (e.g. `distinctInstance`, or an attribute-based `memberOf`) excludes
   instances that otherwise have room — see `core/patterns/aws/ecs/instance-capacity-and-placement.md`
   §4.
4. Availability Zone distribution — if the service's placement strategy spreads across AZs, an AZ with
   no eligible instance can block placement even if other AZs have room.
5. The ASG backing the cluster is at `MaxSize`, so no new capacity can be added to relieve the shortage
   (see `ecs-capacity-provider-scaling.md`).
6. GPU or other special resource requirements (e.g. `gpu` in the task definition) that only a subset of
   instance types can satisfy.

## 4. Architecture context

Full background: `core/patterns/aws/ecs/instance-capacity-and-placement.md` §1–§2 (registered vs.
remaining resources, CPU units, memory hard/soft limits). The key architectural fact this runbook
depends on: ECS tracks **registered resources** (total CPU/memory the instance contributed when it
registered) and **remaining resources** (what's currently unallocated) *per container instance* — there
is no cluster-wide pool the scheduler draws from. A task either fits on one specific instance or it
doesn't; partial fits across instances never happen.

## 5. Prerequisites and required permissions

Read-only IAM permissions: `ecs:DescribeContainerInstances`, `ecs:ListContainerInstances`,
`ecs:DescribeTaskDefinition`, `ec2:DescribeInstanceTypes`.

## 6. Step-by-step investigation

1. Get the task definition's exact CPU/memory requirement.
2. List every `ACTIVE` container instance and its `remainingResources` individually — not summed.
3. Compare each instance's remaining CPU *and* memory against the requirement — both must fit on the
   *same* instance.
4. If every instance individually falls short despite the cluster-wide total being sufficient, this is
   fragmentation (root cause 1) — not a true capacity shortage.
5. If no instance type in the cluster could ever fit the task regardless of load, this is root cause 2
   — a task-definition-sizing-vs-instance-type mismatch, not a transient issue.
6. Cross-check any placement constraints and the service's placement strategy against the instances that
   do have room (root causes 3–4).

## 7. Read-only AWS CLI commands

```bash
# Task definition's requirement
aws ecs describe-task-definition --task-definition <task-definition-family>:<revision> \
  --query 'taskDefinition.{cpu:cpu,memory:memory}'
```

```bash
# Every ACTIVE instance's remaining resources, one by one
aws ecs list-container-instances --cluster <cluster-name> --filter "status==ACTIVE" \
  --query 'containerInstanceArns'

aws ecs describe-container-instances --cluster <cluster-name> --container-instances <container-instance-arn> \
  --query 'containerInstances[0].{remaining:remainingResources,registered:registeredResources,runningTasks:runningTasksCount}'
```

```bash
# What instance type is this, and what does it actually offer?
aws ec2 describe-instance-types --instance-types <instance-type> \
  --query 'InstanceTypes[0].{vCpus:VCpuInfo.DefaultVCpus,MemoryMiB:MemoryInfo.SizeInMiB}'
```

All commands above are read-only.

## 8. Expected output or relevant output fields

- `registeredResources` for `CPU`/`MEMORY` — the instance's total contribution at registration time
  (lower than the instance's raw spec, since the OS/agent reserve some of it).
- `remainingResources` for `CPU`/`MEMORY` — what's actually available right now. Compare this, per
  instance, against the task definition's `cpu`/`memory`.
- If `remainingResources.MEMORY` is below the task's `memory` on *every* instance, but the *sum* across
  instances clearly exceeds it, that confirms fragmentation.

## 9. How to interpret the results

| Observation | Interpretation |
|---|---|
| Every instance's remaining CPU/memory individually < task requirement, but cluster total > requirement | Fragmentation (root cause 1) — adding one more correctly-sized instance resolves it; rebalancing existing load does not, since placement doesn't repack running tasks. |
| `registeredResources` itself (not just remaining) is below the task's requirement on every instance type in the cluster | Root cause 2 — the instance type is fundamentally too small; no amount of waiting or scaling helps without changing instance type. |
| Instances with room exist, but are excluded by `distinctInstance` or a `memberOf` constraint | Root cause 3. |
| Instances with room exist, but not in the AZ the spread strategy is currently balancing toward | Root cause 4. |
| ASG `DesiredCapacity == MaxSize` | Root cause 5 — see `ecs-capacity-provider-scaling.md`. |

## 10. Root-cause identification

State the specific numbers: "every container instance has ≤768 MiB remaining memory; the task definition
requires 1024 MiB; the cluster's total remaining memory across 5 instances is 3200 MiB" — this
distinguishes fragmentation (true) from a simple capacity shortage (false, in this example) precisely.

## 11. Resolution options

**Documented recommendations only — see §12.**

- Fragmentation → add one more appropriately-sized instance (via capacity provider managed scaling or
  manually), rather than assuming more total capacity alone will fix it.
- Instance type fundamentally too small → change the ASG's launch template to a larger instance type,
  or reduce the task definition's resource requirement if it was over-provisioned.
- Constraint excluding otherwise-eligible instances → relax the constraint or ensure eligible instances
  exist in every required category (AZ, attribute, etc.).
- GPU/special resource requirement → ensure the ASG includes instance types that actually provide that
  resource.

## 12. Risks and approval requirements

- Changing instance types in a launch template is a capacity-affecting infrastructure change — requires
  approval per `core/standards/change-safety.md`, and should be tested in a non-production environment
  first where possible.
- Reducing a task definition's CPU/memory to "fit better" without understanding actual application usage
  risks instability under load — verify real usage before resizing down.

## 13. Post-resolution verification

```bash
aws ecs describe-container-instances --cluster <cluster-name> --container-instances <container-instance-arn> \
  --query 'containerInstances[0].remainingResources'
```

Confirm at least one individual instance now has enough remaining CPU *and* memory for the task, then
confirm the previously-pending task actually reaches `RUNNING`.

## 14. Related Brain documentation

- `core/patterns/aws/ecs/instance-capacity-and-placement.md` — registered/remaining resource model in
  full.
- `core/runbooks/aws/ecs/ecs-service-stuck-pending.md` — broader placement-failure triage.
- `core/runbooks/aws/ecs/ecs-capacity-provider-scaling.md` — if the ASG itself needs to grow.

## 15. Official AWS references

- `ContainerInstance` API reference (`registeredResources`/`remainingResources`): https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ContainerInstance.html
- Reserving ECS Linux container instance memory: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/memory-management.html
- ECS service event messages (CPU/memory placement failures): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-event-messages-list.html

## 16. Verification status

CONFIRMED — the registered/remaining resource model and the per-instance (non-pooled) placement
behavior are documented directly in the AWS `ContainerInstance` API reference fetched for this runbook.
