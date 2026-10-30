---
title: "Runbook: ECR image pull failure"
category: runbook
technology: ecs
status: CONFIRMED
created: 2026-10-31
last_verified: 2026-10-31
source: "AWS documentation (see References section)"
---

# Runbook: ECR image pull failure

## 1. Title and purpose

A task stops with a `CannotPullContainer`-category error. This runbook distinguishes the three
fundamentally different causes AWS documents for this — permissions, connectivity, and image/registry
problems — since the fix for each is completely different and the error text alone can look similar.

## 2. Symptoms

- `stoppedReason` contains text like "The task can't pull the image..." or
  "CannotPullContainerError: ...".
- Tasks fail consistently at startup, before the application container ever runs.

## 3. Possible root causes

1. **Permissions** — the execution role (EC2: the container instance role) lacks ECR pull permissions.
2. **Connectivity** — no network path from the task/instance to the ECR API/registry endpoints or the
   S3 bucket backing image layers.
3. **Image/tag problem** — the image or tag doesn't exist, or ECS's image-digest resolution can't
   re-resolve a `:latest`-style mutable tag to the version it originally pinned.
4. **Disk space** — the container instance is out of disk space to write the pulled layers.
5. **Registry-side throttling** — rate limiting (relevant mainly for public/Docker Hub images, not
   typically private ECR).

## 4. Architecture context

Full background: `core/patterns/aws/ecs/iam-roles-and-permissions.md` §4 and §6 (execution role vs.
container instance role — both can independently cause this) and `core/patterns/aws/ecs/networking.md`
§5 (the three VPC endpoints EC2 tasks need: `ecr.api`, `ecr.dkr`, and the S3 gateway endpoint). AWS's own
documentation separates image pull errors into these distinct message families — use the exact error
text to identify which family you're in before picking a fix.

## 5. Prerequisites and required permissions

Read-only IAM permissions: `ecs:DescribeTasks`, `ecr:DescribeImages`, `ecr:DescribeRepositories`,
`iam:GetRole`, `iam:ListAttachedRolePolicies`, `ec2:DescribeVpcEndpoints`.

## 6. Step-by-step investigation

1. Get the exact `stoppedReason` text — AWS's documented error messages map directly to a cause family
   (§9).
2. If the message mentions permissions ("Check that the role has the permissions to pull images..."),
   check the execution role (Fargate) or container instance role (EC2) for the required ECR actions.
3. If the message mentions a connection issue or network configuration, check for a route to the
   internet (public subnet + public IP, or NAT Gateway) or the required VPC endpoints.
4. Confirm the image and tag actually exist in the repository.
5. If the error mentions disk space, check the instance's actual free disk space.
6. Confirm the image's tag isn't `:latest` combined with a since-deleted/overwritten image — ECS's
   image-digest resolution deliberately fails rather than silently running a different image than the
   one originally pinned.

## 7. Read-only AWS CLI commands

```bash
# Exact stopped reason
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn> \
  --query 'tasks[0].{stoppedReason:stoppedReason,containers:containers[*].reason}'
```

```bash
# Does the image/tag actually exist?
aws ecr describe-images --repository-name <repository-name> --image-ids imageTag=<image-tag>
```

```bash
# Container instance role's attached policies (EC2 launch type)
aws iam list-attached-role-policies --role-name <instance-role-name>
```

```bash
# Execution role's attached/inline policies (if this task definition sets executionRoleArn)
aws iam list-attached-role-policies --role-name <execution-role-name>
aws iam list-role-policies --role-name <execution-role-name>
```

```bash
# Do the required VPC endpoints exist in this VPC?
aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=<vpc-id>" \
  --query 'VpcEndpoints[*].{service:ServiceName,state:State}'
```

```bash
# On the instance: disk space check (read-only)
df -h /
du -Sh / | sort -rh | head -20
```

All commands above are read-only.

## 8. Expected output or relevant output fields

- `describe-images` returning the image confirms the image/tag exists; a `ImageNotFoundException`
  confirms root cause 3.
- `describe-vpc-endpoints` should show `com.amazonaws.<region>.ecr.api`, `com.amazonaws.<region>.ecr.dkr`
  (both `interface` type, `state: available`), and `com.amazonaws.<region>.s3` (`gateway` type) if the
  subnet has no NAT Gateway route — see `core/patterns/aws/ecs/networking.md` §5.
- `df -h /` showing very low available space confirms root cause 4.

## 9. How to interpret the results

| `stoppedReason` text (abbreviated) | Cause family | Where to look |
|---|---|---|
| "Check that the role has the permissions to pull images from the registry" | Permissions | Execution role (Fargate) or container instance role (EC2) ECR actions — `core/patterns/aws/ecs/iam-roles-and-permissions.md` §4/§6 |
| "...connection issue between the task and Amazon ECR. Check your task network configuration" | Connectivity | NAT Gateway route or VPC endpoints — `core/patterns/aws/ecs/networking.md` §5 |
| "net/http: request canceled while waiting for connection" / "Context canceled" | Connectivity | Same as above — no route to the internet or to the required VPC endpoint |
| "pull image manifest has been retried 5 time(s): failed to resolve ref" | Image/tag | Image tag changed/deleted since first pinned — avoid `:latest`, use an immutable tag per `core/standards/naming-conventions.md` |
| "pull access denied" | Permissions | Same as the first row — the identity pulling isn't authorized for this repository |
| "write ... no space left on device" | Disk space | Free up space on the container instance; consider the `awslogs` driver instead of `json-file` to avoid log-driven disk usage |
| "toomanyrequests: ... pull rate limit" | Throttling | Public registry rate limit — authenticate pulls or use ECR instead of a public registry |

## 10. Root-cause identification

Quote the exact `stoppedReason` string and map it to one row in §9 — these messages are specific enough
that the cause family is rarely ambiguous once you have the exact text, which is why getting the precise
`stoppedReason` in step 1 matters more than any other single action in this runbook.

## 11. Resolution options

**Documented recommendations only — see §12.**

- Missing permission → add the specific ECR actions to the correct role, scoped to the specific
  repository ARN where possible (`core/patterns/aws/ecs/iam-roles-and-permissions.md` §8 shows the exact
  action list for pushing; pulling needs `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`,
  `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`).
- Missing connectivity → add the missing VPC endpoint(s) or NAT Gateway route
  (`core/patterns/aws/ecs/networking.md` §5).
- Image/tag problem → push the correct tag, or if intentionally rotating a mutable tag, understand that
  ECS's version-consistency feature will reject a changed digest by design — pin an immutable tag
  instead.
- Disk space → clean up unused images/logs on the instance, or configure log rotation
  (`max-size` on `json-file`, or switch to `awslogs`).

## 12. Risks and approval requirements

- IAM role changes require approval per `core/standards/change-safety.md` and
  `core/standards/aws-security.md` — scope additions to the specific repository ARN, not `*`.
- Adding a VPC endpoint is an infrastructure change with cost and routing implications — plan and
  approve it rather than adding it reactively without review.
- Do not grant broad ECR permissions "to make the error go away" without scoping to the specific
  repository — this is exactly the kind of overly broad grant `core/standards/aws-security.md` warns
  against.

## 13. Post-resolution verification

```bash
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn> --query 'tasks[0].lastStatus'
```

Confirm the task reaches `RUNNING` and stays there — a permissions or connectivity fix should resolve
the *next* task launch attempt, not require intervention on the already-stopped one.

## 14. Related Brain documentation

- `core/patterns/aws/ecs/iam-roles-and-permissions.md` §4, §6 — execution role and container instance
  role ECR permissions.
- `core/patterns/aws/ecs/networking.md` §5 — required VPC endpoints for private-subnet ECR access.
- `core/runbooks/aws/ecs/ecs-task-stopped.md` — broader stopped-task triage this runbook specializes.
- `core/runbooks/aws/ecs/ecs-networking-connectivity.md` — deeper network diagnosis if the endpoint
  configuration looks correct but connectivity still fails.

## 15. Official AWS references

- `CannotPullContainer` troubleshooting (all message variants): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_cannot_pull_image.html
- ECR VPC endpoints: https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html
- ECS container image resolution (digest pinning, `:latest` behavior): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html#deployment-container-image-stability
- IAM permissions for pulling/pushing ECR images: https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html

## 16. Verification status

CONFIRMED — every error message variant and its documented cause in §9 was fetched directly from AWS's
`CannotPullContainer` troubleshooting page for this runbook.
