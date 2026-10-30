---
title: "Runbook: ECS cluster not receiving new EC2 capacity (capacity provider / ASG not scaling)"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: ECS cluster not receiving new EC2 capacity (capacity provider / ASG not scaling)

## 1. Title and purpose

A cluster using a capacity provider should automatically grow its backing EC2 Auto Scaling Group (ASG)
when tasks need more room, but it isn't scaling out (or in) as expected. This runbook diagnoses where in
that automation chain the problem is, reusing the mechanics already documented in
`core/patterns/aws/ecs/capacity-providers.md` rather than re-explaining them.

## 2. Symptoms

- Tasks stay `PENDING` for insufficient capacity, even though the cluster has a capacity provider
  attached and the ASG is below its `MaxSize`.
- The ASG's `DesiredCapacity` doesn't change even as task demand on the cluster rises or falls.
- Service event: "No Container Instances were found in your capacity provider."

## 3. Possible root causes

1. No capacity provider is actually associated with the cluster/service (vs. assumed to be).
2. The capacity provider exists but managed scaling is disabled or misconfigured.
3. Managed scaling is working, but the ASG itself can't launch instances (separate EC2-layer problem —
   see `ec2-instance-not-registering.md` §3 item 1 for ASG launch failures specifically).
4. The ASG is already at `MaxSize` — capacity provider has nowhere further to scale.
5. A manually-attached scaling policy on the same ASG is fighting with managed scaling.
6. Managed termination protection is disabled, so scale-in is terminating instances that still have
   running tasks (a scale-in-time problem, not scale-out).

## 4. Architecture context

Full background: `core/patterns/aws/ecs/capacity-providers.md` (capacity provider, managed scaling,
managed termination protection, `base`/`weight` strategy). This runbook assumes that mechanism is
understood and focuses on checking each link in the chain for a specific cluster/ASG pair.

**Why ECS service desired count and ASG desired capacity are different values:** these are two separate,
loosely-coupled numbers (full explanation in `core/patterns/aws/ecs/fundamentals.md` §6). The **ECS
service desired count** is how many *tasks* you want running; the **ASG desired capacity** is how many
*EC2 instances* the ASG wants running. Nothing keeps them numerically equal or proportional — capacity
provider managed scaling *indirectly* adjusts ASG desired capacity based on how much of the cluster's
registered resources are reserved by tasks (`CapacityProviderReservation`), not based on the service's
desired count number itself. A service with `desiredCount: 50` tiny tasks might need only 2 EC2
instances; a service with `desiredCount: 2` huge tasks might need 5. Expecting one number to directly
track the other is a common source of confusion when capacity doesn't seem to "match" a service's
desired count — keep that distinction in mind throughout the investigation below.

## 5. Prerequisites and required permissions

Read-only IAM permissions: `ecs:DescribeCapacityProviders`, `ecs:DescribeClusters`,
`autoscaling:DescribeAutoScalingGroups`, `cloudwatch:GetMetricData` (for `CapacityProviderReservation`,
if you have access to view it).

## 6. Step-by-step investigation

1. Confirm a capacity provider is actually associated with the cluster and that the service/task is
   using a capacity provider strategy (not a bare `--launch-type EC2`, which bypasses capacity providers
   entirely — see `core/patterns/aws/ecs/capacity-providers.md` §1).
2. Check the capacity provider's `status` and its managed scaling configuration.
3. Check the ASG's current `DesiredCapacity` vs. `MinSize`/`MaxSize`.
4. If the ASG is below `MaxSize` and managed scaling is `ENABLED` but nothing is happening, check for a
   separately-attached scaling policy on the same ASG that could be overriding or conflicting with it.
5. For a scale-in-related problem (tasks disrupted during scale-in), check whether managed termination
   protection is `ENABLED`.

## 7. Read-only AWS CLI commands

```bash
# Is a capacity provider associated with this cluster, and what's its default strategy?
aws ecs describe-clusters --clusters <cluster-name> \
  --query 'clusters[0].{capacityProviders:capacityProviders,defaultStrategy:defaultCapacityProviderStrategy}'
```

```bash
# Capacity provider configuration and status
aws ecs describe-capacity-providers --capacity-providers <capacity-provider-name> \
  --query 'capacityProviders[0].{status:status,autoScalingGroupArn:autoScalingGroupProvider.autoScalingGroupArn,managedScaling:autoScalingGroupProvider.managedScaling,managedTerminationProtection:autoScalingGroupProvider.managedTerminationProtection}'
```

```bash
# Is the service actually using a capacity provider strategy?
aws ecs describe-services --cluster <cluster-name> --services <service-name> \
  --query 'services[0].{launchType:launchType,capacityProviderStrategy:capacityProviderStrategy}'
```

```bash
# ASG's current state and limits
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names <asg-name> \
  --query 'AutoScalingGroups[0].{desired:DesiredCapacity,min:MinSize,max:MaxSize,instances:length(Instances)}'
```

```bash
# Any separately-attached scaling policies that might conflict with managed scaling
aws autoscaling describe-policies --auto-scaling-group-name <asg-name>
```

All commands above are read-only.

## 8. Expected output or relevant output fields

- `launchType: null` and a populated `capacityProviderStrategy` confirms the service is actually using a
  capacity provider; if `launchType: "EC2"` is set instead, the capacity provider isn't in play for this
  service at all regardless of its own configuration.
- `managedScaling.status: "ENABLED"` with a `targetCapacity` value — if `status` is `DISABLED`, nothing
  will scale automatically no matter how much demand exists.
- `describe-policies` returning any results on an ASG that's supposed to be purely capacity-provider
  managed is a red flag — AWS doesn't recommend mixing the two.

## 9. How to interpret the results

| Observation | Interpretation |
|---|---|
| Service uses bare `launchType: "EC2"`, no capacity provider strategy | Root cause 1 — capacity provider isn't involved for this service at all; it's relying on pre-existing capacity only. |
| `managedScaling.status: "DISABLED"` | Root cause 2. |
| Managed scaling `ENABLED`, ASG `DesiredCapacity < MaxSize`, but no change over time despite pending tasks | Likely root cause 3 — check ASG activity history for launch failures (this moves into EC2/ASG-layer troubleshooting, not ECS). |
| ASG `DesiredCapacity == MaxSize` | Root cause 4 — capacity provider has no further room; this is a capacity *ceiling*, not a malfunction. |
| A target-tracking or step-scaling policy exists on the same ASG | Root cause 5 — the two mechanisms can issue conflicting `DesiredCapacity` changes. |
| `managedTerminationProtection: "DISABLED"` and tasks disrupted during scale-in | Root cause 6. |

## 10. Root-cause identification

Name the specific configuration value that's blocking automation — e.g. "the capacity provider's
`managedScaling.status` is `DISABLED`," or "the ASG's `MaxSize` is 4 and it's already at 4" — rather than
"scaling isn't working."

## 11. Resolution options

**Documented recommendations only — see §12.**

- Service not using the capacity provider → add a capacity provider strategy to the service, or rely on
  the cluster's default strategy (`core/patterns/aws/ecs/capacity-providers.md` §5).
- Managed scaling disabled → enable it on the capacity provider.
- ASG at `MaxSize` → raise `MaxSize` after confirming the increase is intentional and within account
  limits.
- Conflicting scaling policy → remove the separately-attached policy, letting managed scaling be the
  sole mechanism, per AWS's own recommendation.
- Managed termination protection disabled → enable it (requires the ASG's own instance-protection
  setting to be compatible — verify before enabling).

## 12. Risks and approval requirements

- Changing `MaxSize`, managed scaling settings, or termination protection are infrastructure changes to
  shared capacity — require explicit approval per `core/standards/change-safety.md`.
- Removing an existing scaling policy could have been placed intentionally for a reason not visible in
  this runbook's scope — confirm with whoever owns that ASG before removing it.
- Do not manually set ASG `DesiredCapacity` as a one-off fix — this fights the capacity provider's own
  management and the two will likely conflict again on the next scaling event.

## 13. Post-resolution verification

```bash
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names <asg-name> \
  --query 'AutoScalingGroups[0].DesiredCapacity'
```

Confirm `DesiredCapacity` rises in response to actual pending demand (or falls in response to reduced
demand), and that previously-`PENDING` tasks successfully place once new capacity registers (cross-check
with `ec2-instance-not-registering.md` if a newly-launched instance doesn't register).

## 14. Related Brain documentation

- `core/patterns/aws/ecs/capacity-providers.md` — full capacity provider and managed scaling mechanics.
- `core/patterns/aws/ecs/fundamentals.md` §6 — desired/running/pending count vs. ASG desired capacity.
- `core/runbooks/aws/ecs/ec2-instance-not-registering.md` — if a newly-launched instance doesn't
  register once the ASG does scale out.
- `core/runbooks/aws/ecs/ecs-insufficient-capacity.md` — if capacity exists but is fragmented/
  insufficient per-instance rather than absent cluster-wide.

## 15. Official AWS references

- ECS capacity providers: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/cluster-capacity-providers.html
- Capacity provider managed scaling: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/asg-capacity-providers.html
- ECS service event messages (capacity provider related): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-event-messages-list.html

## 16. Verification status

CONFIRMED against AWS documentation for capacity provider/managed scaling mechanics (fetched in Phase 4
and reused here). The specific recommendation against mixing a manual scaling policy with managed
scaling reflects AWS's general operational guidance; if your account has a documented exception, treat
that as the authoritative source instead.
