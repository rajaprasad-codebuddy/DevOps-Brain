---
title: "Runbook: ECS deployment stuck or failed"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: ECS deployment stuck or failed

## 1. Title and purpose

A service update (new task definition revision) doesn't complete — it either stays `IN_PROGRESS`
indefinitely or transitions to `FAILED`. This runbook diagnoses which, and why, building on
`core/patterns/aws/ecs/deployment.md` rather than repeating its theory.

## 2. Symptoms

- `aws ecs describe-services` shows a deployment with `rolloutState: "IN_PROGRESS"` well past the time a
  normal rollout takes.
- `rolloutState: "FAILED"`, with or without an automatic rollback having occurred.
- A service event stating it "could not launch N tasks for deployment" or "was unable to stop or start
  tasks during a deployment because of the service deployment configuration."

## 3. Possible root causes

1. The new revision's tasks fail to start at all (capacity, placement, or task-definition problem — see
   `ecs-service-stuck-pending.md` / `ecs-task-stopped.md`).
2. `minimumHealthyPercent`/`maximumPercent` leave no room for the scheduler to start or stop any task.
3. ALB target group health checks fail for the new tasks even though they reach `RUNNING`.
4. The deployment circuit breaker tripped and rolled back — but there's no prior `COMPLETED` deployment
   to roll back to (first deployment of a new service).
5. Insufficient capacity specifically *during* the deployment (enough for steady state, not enough to
   run old and new tasks simultaneously under the current `maximumPercent`).

## 4. Architecture context

Full background: `core/patterns/aws/ecs/deployment.md` (deployment lifecycle, §4 min/max percent, §5
circuit breaker, §6 controller types). This runbook assumes that background and focuses on distinguishing
*which* of the failure points in that lifecycle is the actual blocker for a specific stuck deployment.

## 5. Prerequisites and required permissions

Read-only IAM permissions: `ecs:DescribeServices`, `ecs:DescribeTasks`, `ecs:ListTasks`,
`ecs:DescribeTaskDefinition`, `elasticloadbalancing:DescribeTargetHealth`.

## 6. Step-by-step investigation

1. Check `rolloutState` and `rolloutStateReason` first — this often states the blocker directly.
2. Read the service's events for the specific deployment-related messages in §9.
3. If tasks for the new revision aren't reaching `RUNNING` at all, treat this as
   `ecs-service-stuck-pending.md` or `ecs-task-stopped.md` territory — don't re-diagnose placement or
   startup failures here.
4. If tasks reach `RUNNING` but the deployment still doesn't progress, check the ALB target group health
   of the *new* task set specifically (old tasks may still be healthy and masking the problem at a
   glance).
5. If the circuit breaker rolled back, check whether a prior `COMPLETED` deployment existed — if not,
   this is root cause 4, not a configuration bug.
6. Check `minimumHealthyPercent`/`maximumPercent` arithmetic against the current desired count.

## 7. Read-only AWS CLI commands

```bash
# Deployment-level status and reason
aws ecs describe-services --cluster <cluster-name> --services <service-name> \
  --query 'services[0].{rolloutState:deployments[0].rolloutState,reason:deployments[0].rolloutStateReason,events:events[0:5]}'
```

```bash
# Deployment configuration currently in effect
aws ecs describe-services --cluster <cluster-name> --services <service-name> \
  --query 'services[0].deploymentConfiguration'
```

```bash
# Health of the specific new task set's target group registrations
aws elbv2 describe-target-health --target-group-arn <target-group-arn>
```

```bash
# Tasks belonging to the new deployment/revision specifically
aws ecs list-tasks --cluster <cluster-name> --service-name <service-name> \
  --query 'taskArns'
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn> \
  --query 'tasks[0].{taskDefinitionArn:taskDefinitionArn,lastStatus:lastStatus,healthStatus:healthStatus}'
```

All commands above are read-only.

## 8. Expected output or relevant output fields

- A healthy, completed deployment: `rolloutState: "COMPLETED"`.
- `rolloutState: "IN_PROGRESS"` persisting with no change in `runningCount` over several minutes — stuck,
  not merely slow.
- `rolloutState: "FAILED"` — check whether a rollback deployment was also started (visible as a second,
  newer deployment entry targeting the previous task definition revision).

## 9. How to interpret the results

| Service event / state (abbreviated) | Interpretation |
|---|---|
| "...unable to stop or start tasks during a deployment because of the service deployment configuration" | Root cause 2 — `minimumHealthyPercent`/`maximumPercent` leave no room to maneuver; see `core/patterns/aws/ecs/deployment.md` §4 for the exact rounding rules. |
| "...could not launch N tasks for deployment..." | Root cause 1 or 5 — insufficient capacity specifically blocking the new tasks; cross-check with `ecs-insufficient-capacity.md`. |
| Target health `Unhealthy` for new tasks, `Healthy` for old | Root cause 3 — the new revision itself (app, port, health check path) is the problem, not deployment mechanics. |
| `rolloutState: "FAILED"` with no subsequent rollback deployment | Root cause 4 — no prior `COMPLETED` deployment existed to roll back to. |

## 10. Root-cause identification

State which stage of the deployment lifecycle (new task placement, new task health, or old task
drain/stop) is the one not progressing, with the specific service event text as evidence — "deployment
stuck" alone isn't a root cause; "new tasks are RUNNING but failing ALB health checks on
`/health` with a 404" is.

## 11. Resolution options

**Documented recommendations only — see §12.**

- `minimumHealthyPercent`/`maximumPercent` leave no room → adjust the percentages so at least one task
  can start or stop, per `core/patterns/aws/ecs/deployment.md` §4.
- New revision fails ALB health checks → fix the application/health-check-path mismatch and register a
  corrected revision; don't force the old target group config to match a broken app.
- Capacity shortfall specific to deployment overlap → either temporarily raise `maximumPercent`'s
  required headroom via more capacity, or deploy with a lower `maximumPercent` that fits existing
  capacity (accepting a brief dip in redundancy instead).
- No `COMPLETED` deployment to roll back to → this is expected behavior for a first-ever deployment of a
  new service; fix the new revision directly rather than expecting an automatic rollback.

## 12. Risks and approval requirements

- Changing `deploymentConfiguration` or forcing a new deployment are service-level changes — follow
  `core/standards/deployment-standards.md` approval requirements, even when done to recover from a stuck
  state.
- Do not manually stop tasks to "force" a deployment to progress — this can leave the service below its
  `minimumHealthyPercent` unintentionally and defeats the purpose of that safety setting.
- A rollback (manual or automatic) is itself a production change — verify its outcome, don't assume
  reverting fixed things (`core/standards/deployment-standards.md` §Rollback planning).

## 13. Post-resolution verification

```bash
aws ecs describe-services --cluster <cluster-name> --services <service-name> \
  --query 'services[0].{rolloutState:deployments[0].rolloutState,running:runningCount,desired:desiredCount}'
```

Confirm `rolloutState: "COMPLETED"` and `running == desired` on the intended task definition revision —
check `taskDefinition` on the service to confirm it's the revision you expect, not an unexpected
rollback target.

## 14. Related Brain documentation

- `core/patterns/aws/ecs/deployment.md` — full deployment lifecycle, circuit breaker, controller types.
- `core/runbooks/aws/ecs/ecs-service-stuck-pending.md` — if new tasks never reach `RUNNING`.
- `core/runbooks/aws/ecs/ecs-task-stopped.md` — if new tasks reach `RUNNING` then stop.
- `core/runbooks/aws/ecs/ecs-alb-health-check-failed.md` — if the new tasks run but fail ALB health
  checks.
- `core/runbooks/aws/ecs/ecs-insufficient-capacity.md` — if capacity is the blocker.

## 15. Official AWS references

- ECS rolling deployments: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html
- ECS deployment circuit breaker: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html
- ECS service event messages: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-event-messages-list.html

## 16. Verification status

CONFIRMED — deployment-configuration and circuit-breaker behavior and the service event message text
were fetched directly from AWS documentation. Exact circuit-breaker failure-threshold tuning
(`resetOnHealthyTask`, `thresholdConfiguration`) is detailed in `core/patterns/aws/ecs/deployment.md` §5
rather than repeated here.
