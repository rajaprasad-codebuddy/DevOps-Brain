---
title: "Runbook: ECS IAM permission denied"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: ECS IAM permission denied

## 1. Title and purpose

An ECS-related operation fails with an access-denied error, but there are **five** distinct roles in
play (`core/patterns/aws/ecs/iam-roles-and-permissions.md`), plus trust policies, permission boundaries,
and SCPs that can each independently cause a denial. This runbook's main job is identifying **which
principal** made the failed request before guessing at a fix.

## 2. Symptoms

- A task fails to start with a permissions-flavored `stoppedReason` (see `ecs-ecr-image-pull-failed.md`
  and `ecs-task-stopped.md` for the ECR/secrets-specific variants).
- A CI/CD deployment step fails with `AccessDenied` calling an ECS or IAM API.
- A service event states: "IAM permissions policies have been misconfigured or changed, and ECS can no
  longer maintain your service" or "IAM trust relationship has been misconfigured or changed...".
- An application running inside a task gets `AccessDenied` calling an AWS API directly.

## 3. Possible root causes

Mapped to the five roles in `core/patterns/aws/ecs/iam-roles-and-permissions.md`:

1. **Task execution role** missing a permission (ECR pull, log write, secret retrieval) — affects task
   startup, not application code.
2. **Task role** missing a permission — affects the running application's own AWS API calls.
3. **EC2 container instance role** missing a permission — affects agent registration/operation, not any
   specific task.
4. **ECS service-linked role** missing or its policy insufficient — affects ECS's own ability to manage
   resources like ALB target groups on your behalf.
5. **Deployment role** (CI/CD) missing a permission, most commonly `iam:PassRole` on the execution/task
   role ARNs it needs to pass to ECS.
6. **Trust policy** mismatch — the role exists and has the right permissions, but the calling principal
   isn't allowed to assume it (wrong `Principal`, wrong `Condition`).
7. **Permission boundary** — an identity's effective permissions are capped below what its own identity
   policy grants.
8. **Service Control Policy (SCP)** — an AWS Organizations-level policy denies the action account-wide,
   regardless of any role's own policy.
9. **Resource-based policy** — the target resource itself (e.g. an ECR repository policy, a VPC endpoint
   policy, a KMS key policy) denies access independently of the caller's own identity permissions.

## 4. Architecture context

Full background: `core/patterns/aws/ecs/iam-roles-and-permissions.md` — this runbook does not repeat the
role descriptions or the exact managed-policy JSON documented there; it focuses on the diagnostic
process for figuring out which one is actually at fault for a specific denial.

## 5. Prerequisites and required permissions

Read-only IAM/CloudTrail permissions: `iam:GetRole`, `iam:GetRolePolicy`,
`iam:ListAttachedRolePolicies`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `cloudtrail:LookupEvents`,
`organizations:DescribeEffectivePolicy` (if you have Organizations access and SCPs are suspected).

## 6. Step-by-step investigation

1. **Identify the exact denied action and resource** from the error message — AWS's own `AccessDenied`
   errors typically name both.
2. **Identify the calling principal** — for an AWS-service-initiated call (ECS agent, ECS itself), this
   is one of the five roles; for a human/CI action, check CloudTrail's `userIdentity` field directly.
3. **Check that principal's identity-based policy** for the denied action on the denied resource.
4. **Check for a permission boundary** on that same identity — effective permissions are the
   intersection of the identity policy and the boundary (`core/patterns/aws/ecs/iam-roles-and-permissions.md`
   §9); both must allow the action.
5. **Check for an applicable SCP** if the account is part of an AWS Organization — an SCP can deny an
   action even if every role-level policy allows it.
6. **Check the trust policy** if the error is about *assuming* the role rather than performing the
   action — this is a different failure mode from a missing permission on an already-assumed role.
7. **Check resource-based policies** on the specific target resource if identity-side permissions all
   look correct.

## 7. Read-only AWS CLI commands

```bash
# Find the exact denied call via CloudTrail — who, what action, what resource, when
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=<api-action-name> \
  --max-results 10 \
  --query 'Events[*].{time:EventTime,username:Username,errorCode:CloudTrailEvent}'
```

```bash
# Inspect a role's identity-based policies
aws iam list-attached-role-policies --role-name <role-name>
aws iam list-role-policies --role-name <role-name>
aws iam get-role-policy --role-name <role-name> --policy-name <inline-policy-name>
```

```bash
# Inspect a role's trust policy (who can assume it)
aws iam get-role --role-name <role-name> --query 'Role.AssumeRolePolicyDocument'
```

```bash
# Check for a permission boundary on a role
aws iam get-role --role-name <role-name> --query 'Role.PermissionsBoundary'
```

```bash
# Check a managed policy's actual document (for a specific version)
aws iam get-policy --policy-arn <policy-arn> --query 'Policy.DefaultVersionId'
aws iam get-policy-version --policy-arn <policy-arn> --version-id <version-id> \
  --query 'PolicyVersion.Document'
```

All commands above are read-only.

## 8. Expected output or relevant output fields

- CloudTrail's `errorCode: "AccessDenied"` events include a `requestParameters` and `userIdentity` block
  — `userIdentity.arn` tells you exactly which role/session made the call; for an ECS task role session,
  this includes the `taskArn` in context, letting you tie a denial to a specific task
  (`core/patterns/aws/ecs/iam-roles-and-permissions.md` §5).
- `Role.PermissionsBoundary` is absent (`null`) for a role with no boundary — if present, you must check
  the boundary policy's own permissions too.
- `AssumeRolePolicyDocument` lists the trusted `Principal` and any `Condition` — an `AccessDenied` on
  `AssumeRole`/`AssumeRoleWithWebIdentity` itself (not on a subsequent action) means the caller's own
  identity doesn't satisfy this trust policy, regardless of what permissions the role would grant once
  assumed.

## 9. How to interpret the results

| Observation | Interpretation |
|---|---|
| CloudTrail shows `ecs-tasks.amazonaws.com` or similar service principal as the assuming entity for a denied action | Likely the task execution role or task role, not a human/CI identity — see §3 rows 1–2. |
| Denial on `RegisterContainerInstance`/`Poll` from an EC2 instance's role session | Container instance role (§3 row 3) — see `ec2-instance-not-registering.md`. |
| Service event explicitly names "IAM trust relationship has been misconfigured" | Root cause 6 — fix the trust policy's `Principal`/`Condition`, not the permissions policy. |
| Role's identity policy clearly allows the action, denial persists | Check permission boundary (root cause 7), SCP (root cause 8), or a resource-based policy (root cause 9) next — in that order, since these commonly get missed when someone only checks the role's own policy. |
| CI/CD pipeline denial specifically on `iam:PassRole` | Root cause 5 — the deployment role's `PassRole` statement doesn't cover the specific execution/task role ARN being passed. |

## 10. Root-cause identification

State which of the five roles (or which of the trust-policy/boundary/SCP/resource-policy layers) is
responsible, with the exact denied action and resource ARN from CloudTrail — "permission denied" alone
isn't a root cause; "the task role `<task-role-arn>` lacks `s3:GetObject` on
`arn:aws:s3:::<bucket>/<prefix>/*`" is.

## 11. Resolution options

**Documented recommendations only — see §12.**

- Missing identity-based permission → add the specific, narrowly-scoped action/resource to the correct
  role's policy — never widen to a wildcard "to be safe" (`core/standards/aws-security.md`).
- Trust policy mismatch → correct the `Principal`/`Condition` in the trust policy to match the actual
  calling identity.
- Permission boundary too restrictive → either adjust the boundary (if it was set more narrowly than
  intended) or recognize this as an intentional guardrail that shouldn't be loosened without the
  boundary's owner's sign-off.
- SCP blocking the action → this requires the AWS Organization management account/delegated admin to
  review — not something fixable at the member-account role level.
- Resource-based policy denial → correct the specific resource's policy (e.g. ECR repository policy),
  scoped to the specific principal that needs access.

## 12. Risks and approval requirements

- Every fix above is an IAM change — these require explicit human approval under
  `core/standards/change-safety.md` and `core/standards/aws-security.md`, regardless of how small the
  change looks.
- Do not attach `AdministratorAccess` or broaden a wildcard "temporarily" to unblock a deployment — this
  is explicitly the kind of shortcut `core/standards/aws-security.md` warns against, and it tends to
  outlive its "temporary" justification.
- SCP and permission-boundary changes affect scope far beyond ECS — treat them as organization/account
  level changes requiring the appropriate broader approval, not an ECS-specific one.

## 13. Post-resolution verification

Re-attempt the originally-denied action (read-only check first if possible, e.g. re-check via
CloudTrail that the next attempt succeeds) and confirm via CloudTrail that the subsequent call shows
`errorCode` absent (success) rather than `AccessDenied`.

## 14. Related Brain documentation

- `core/patterns/aws/ecs/iam-roles-and-permissions.md` — full role breakdown, trust policies, permission
  boundaries, resource-based policies, with least-privilege examples.
- `core/runbooks/aws/ecs/ec2-instance-not-registering.md` — container instance role denials
  specifically.
- `core/runbooks/aws/ecs/ecs-ecr-image-pull-failed.md` — execution/instance role ECR permission
  denials specifically.
- `core/standards/aws-security.md` — least-privilege standard this runbook's resolutions follow.

## 15. Official AWS references

- ECS service event messages (IAM-related): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-event-messages-list.html
- Granting `iam:PassRole`: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html
- The confused deputy problem: https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html
- IAM policy evaluation logic (identity policy, boundary, SCP interaction): https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html

## 16. Verification status

CONFIRMED for the role breakdown and PassRole/trust-policy mechanics (sourced in Phase 4 and reused
here) and for the two IAM-specific service event message strings (fetched directly from AWS
documentation for this runbook). The exact IAM policy evaluation order (identity policy ∩ boundary, then
SCP, then resource policy) follows AWS's documented evaluation logic — reference it directly if a
specific evaluation-order question arises that this summary doesn't resolve.
