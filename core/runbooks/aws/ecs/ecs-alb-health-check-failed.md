---
title: "Runbook: ECS target group health check failure"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: ECS target group health check failure

## 1. Title and purpose

Tasks reach `RUNNING` but the ALB never considers them healthy, so they never receive traffic (and may
be killed and replaced repeatedly as a result). This runbook diagnoses target-group-level health check
failures specifically, distinct from a container's own `healthCheck` (covered in `ecs-task-stopped.md`).

## 2. Symptoms

- ALB returns `503` or routes no traffic even though `aws ecs describe-services` shows
  `runningCount == desiredCount`.
- `aws elbv2 describe-target-health` shows targets in `unhealthy` state.
- Service event: "...is unhealthy in (elb ...) due to (reason Instance has failed at least the
  UnhealthyThreshold number of health checks consecutively.)"

## 3. Possible root causes

1. Target group health check path/port doesn't match what the application actually serves.
2. Security group doesn't allow the ALB to reach the task/instance on the health check port.
3. Target type mismatch — `instance` used for an `awsvpc` task (which needs `ip`), or vice versa.
4. The application isn't listening on the address/port ECS and the target group expect (e.g. bound to
   `127.0.0.1` instead of `0.0.0.0`).
5. Health check timeout/threshold too aggressive for the application's actual startup or response time.
6. The ECS service-linked role (`AWSServiceRoleForECS`) doesn't exist, so ECS can't manage target group
   registration at all — a different failure mode from "health checks fail," worth ruling out first.
7. The load balancer isn't configured for the Availability Zone the task is actually running in.

## 4. Architecture context

Full background: `core/patterns/aws/ecs/networking.md` §8 (ALB integration, target types) and
`core/patterns/aws/ecs/iam-roles-and-permissions.md` §7 (service-linked role). The target group's own
health check is independent of the container definition's `healthCheck` — a task can be `RUNNING` and
pass its container health check while still failing here, because this check is performed by the ALB
over the network, not by the ECS agent locally.

## 5. Prerequisites and required permissions

Read-only IAM permissions: `elasticloadbalancing:DescribeTargetHealth`,
`elasticloadbalancing:DescribeTargetGroups`, `ec2:DescribeSecurityGroups`, `ecs:DescribeServices`,
`ecs:DescribeTasks`.

## 6. Step-by-step investigation

1. Confirm the service-linked role exists (rules out root cause 6 quickly).
2. Check target health and the specific `Reason`/`Description` ELB reports for the unhealthy target.
3. Confirm the target group's target type matches the task's network mode
   (`core/patterns/aws/ecs/networking.md` §8).
4. Confirm the health check path/port against what the application actually serves — test this
   independently of the ALB if possible (e.g. exec into the running task and curl locally, if ECS Exec
   is enabled; otherwise rely on application logs).
5. Confirm the security group governing the target (task ENI for `awsvpc`, instance SG for
   `bridge`/`host`) allows inbound traffic from the ALB's security group on the health check port.
6. Check the health check's timeout, interval, and unhealthy threshold against how long the application
   actually takes to respond, especially right after startup.

## 7. Read-only AWS CLI commands

```bash
# Current health state and the specific failure reason/description
aws elbv2 describe-target-health --target-group-arn <target-group-arn> \
  --query 'TargetHealthDescriptions[*].{target:Target,state:TargetHealth.State,reason:TargetHealth.Reason,description:TargetHealth.Description}'
```

```bash
# Target group configuration: type, health check path/port/thresholds
aws elbv2 describe-target-groups --target-group-arns <target-group-arn> \
  --query 'TargetGroups[0].{targetType:TargetType,healthCheckPath:HealthCheckPath,healthCheckPort:HealthCheckPort,healthyThreshold:HealthyThresholdCount,unhealthyThreshold:UnhealthyThresholdCount,timeout:HealthCheckTimeoutSeconds,interval:HealthCheckIntervalSeconds}'
```

```bash
# Does the service-linked role exist at all?
aws iam get-role --role-name AWSServiceRoleForECS --query 'Role.RoleName'
```

```bash
# Security group inbound rules on the relevant SG (task ENI SG for awsvpc, instance SG otherwise)
aws ec2 describe-security-groups --group-ids <security-group-id> \
  --query 'SecurityGroups[0].IpPermissions'
```

```bash
# Confirm the task's own network mode and port mapping, to cross-check against target type/port
aws ecs describe-task-definition --task-definition <task-definition-family>:<revision> \
  --query 'taskDefinition.{networkMode:networkMode,portMappings:containerDefinitions[0].portMappings}'
```

All commands above are read-only.

## 8. Expected output or relevant output fields

- A healthy target: `TargetHealth.State: "healthy"`.
- `TargetHealth.Reason: "Target.Timeout"` — the application didn't respond within the configured
  timeout.
- `TargetHealth.Reason: "Target.FailedHealthChecks"` — the application responded, but with a non-2xx/3xx
  status or otherwise failed the check.
- `TargetHealth.Reason: "Target.NotRegistered"` or similar — registration itself didn't happen; this
  points back toward the service-linked role or ECS-to-ALB integration rather than the application.
- `TargetType: "ip"` required for `awsvpc` tasks; `"instance"` for `bridge` mode with dynamic ports.

## 9. How to interpret the results

| Observation | Interpretation |
|---|---|
| `Reason: "Target.Timeout"` | Root cause 4 or 5 — app too slow to respond, or not listening where expected. |
| `Reason: "Target.FailedHealthChecks"`, app does respond manually | Root cause 1 — wrong path/port configured on the target group itself. |
| No inbound rule on the relevant SG for the health check port from the ALB's SG | Root cause 2. |
| `TargetType` doesn't match network mode | Root cause 3 — see `core/patterns/aws/ecs/networking.md` §8 for which type each mode requires. |
| `aws iam get-role --role-name AWSServiceRoleForECS` fails | Root cause 6 — rare, but a decisive finding when it happens. |

## 10. Root-cause identification

Combine the target health `Reason`/`Description` with the target group's own configuration and the
task definition's actual port mapping — e.g. "target group health check targets port 8080, but the
container's `portMappings` only exposes 3000" is a precise, actionable root cause.

## 11. Resolution options

**Documented recommendations only — see §12.**

- Wrong health check path/port → correct the target group's health check configuration.
- Security group missing the rule → add an inbound rule from the ALB's security group on the health
  check port, per `core/patterns/aws/ecs/networking.md` §4.
- Target type mismatch → this typically requires recreating the target group with the correct type,
  since target type can't be changed after creation.
- Application not listening on the expected interface → fix the application binding (e.g. `0.0.0.0`
  instead of `127.0.0.1`) and deploy a new task definition revision.
- Thresholds too aggressive for a slow-starting app → raise the timeout/interval or unhealthy threshold
  to give the app realistic startup time, balanced against how quickly you want a genuinely broken task
  detected.

## 12. Risks and approval requirements

- Recreating a target group affects the live service's traffic path — plan this as a deployment with
  rollback considerations per `core/standards/deployment-standards.md`, not an ad hoc fix.
- Loosening a security group rule beyond "allow the ALB's security group on the health check port" is
  not necessary to fix this class of problem and should not be done — keep the fix scoped per
  `core/standards/aws-security.md`.
- Raising unhealthy thresholds/timeouts too far reduces how quickly a genuinely broken deployment is
  detected — balance against `core/standards/deployment-standards.md` §Deployment verification.

## 13. Post-resolution verification

```bash
aws elbv2 describe-target-health --target-group-arn <target-group-arn> \
  --query 'TargetHealthDescriptions[*].TargetHealth.State'
```

Confirm every target shows `"healthy"`, and that this is stable (not flapping) over several health
check intervals.

## 14. Related Brain documentation

- `core/patterns/aws/ecs/networking.md` §8 — ALB integration, target types.
- `core/patterns/aws/ecs/iam-roles-and-permissions.md` §7 — ECS service-linked role.
- `core/runbooks/aws/ecs/ecs-task-stopped.md` — container-level `healthCheck` failures (a different,
  related failure mode).
- `core/runbooks/aws/ecs/ecs-networking-connectivity.md` — broader connectivity diagnosis if the
  security-group fix doesn't resolve it.

## 15. Official AWS references

- Troubleshooting service load balancers in ECS: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/troubleshoot-service-load-balancers.html
- ALB target groups and target types: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html
- ECS service event messages (ELB health-check-related): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-event-messages-list.html

## 16. Verification status

CONFIRMED — target-type requirements, service-linked role dependency, and the specific causes listed
(security group, AZ coverage, health check parameter misconfiguration) are documented directly in AWS's
ECS load-balancer troubleshooting guide, fetched for this runbook.
