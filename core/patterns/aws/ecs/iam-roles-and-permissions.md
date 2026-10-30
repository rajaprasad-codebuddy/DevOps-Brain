---
title: "ECS on EC2 — IAM roles and permissions"
category: pattern
technology: ecs
status: CONFIRMED
created: 2026-10-30
last_verified: 2026-10-30
source: "AWS documentation (see References section)"
---

# ECS on EC2 — IAM roles and permissions

**Status:** CONFIRMED against AWS documentation (see References). The exact managed-policy JSON shown
below was fetched directly from the AWS Managed Policy Reference and is reproduced verbatim — do not
assume it still matches without re-checking, since AWS can add permissions to managed policies over
time (it does not remove them).

## 1. Purpose

ECS on EC2 involves **five** distinct IAM roles that are easy to confuse because several of their names
contain the word "task" or "ECS." This document explains each one separately: who assumes it, when it's
used, what it needs, what breaks without it, and how to tell which one is the problem when something
fails with "access denied."

## 2. Prerequisites

- Read `fundamentals.md` (cluster/task/service vocabulary) and `task-definitions.md` (where
  `executionRoleArn` and `taskRoleArn` are set) first.
- Basic IAM familiarity: what a role, a policy, and `sts:AssumeRole` are.

## 3. The five roles, at a glance

| Role | Assumed by | Purpose |
|---|---|---|
| **ECS task execution role** | The ECS agent (infrastructure), via the `ecs-tasks.amazonaws.com` trust | Pull the container image, write logs, retrieve secrets — *before and around* your application code running |
| **ECS task role** | Your application code inside the container, via the `ecs-tasks.amazonaws.com` trust | Let your application call other AWS APIs (S3, DynamoDB, etc.) |
| **EC2 container instance role (instance profile)** | The EC2 instance itself, via the `ec2.amazonaws.com` trust | Let the ECS agent and Docker daemon on that instance call ECS/ECR/CloudWatch Logs APIs to register and operate |
| **ECS service-linked role** (`AWSServiceRoleForECS`) | The ECS service itself, via an AWS-internal trust | Let ECS manage resources on your behalf (e.g. ALB target group registration, ENI management) without you manually granting those permissions anywhere |
| **Deployment role** (e.g. for GitHub Actions) | Your CI/CD pipeline's identity, via OIDC federation | Let a pipeline run deploy actions (register a task definition, update a service) without long-lived AWS credentials |

## 4. ECS task execution role

**Who assumes it:** the ECS agent / ECS infrastructure — not your application code.
**When it's used:** before and during task startup — pulling the container image from ECR, writing
container logs to CloudWatch Logs, and retrieving `secrets` values referenced in the task definition
(`task-definitions.md` §8).
**Referenced by:** the task definition's `executionRoleArn` field.

The AWS managed policy `AmazonECSTaskExecutionRolePolicy` covers image pull and logging. Its exact JSON
(fetched directly from the AWS Managed Policy Reference):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

**Important and easy to miss:** this managed policy does **not** include `secretsmanager:GetSecretValue`
or `ssm:GetParameters`. If your task definition uses `secrets` (`task-definitions.md` §8), you must add a
separate, narrowly-scoped statement yourself:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "<SECRET_ARN>"
    }
  ]
}
```

Scope `Resource` to the specific secret ARN(s) this task actually needs — not `*` — per
`core/standards/aws-security.md`.

**What happens if permissions are missing:** the task fails to start. A missing ECR permission produces
a `CannotPullContainerError` in the task's stopped reason. A missing secrets permission produces a
`ResourceInitializationError` mentioning the secret ARN. A missing logging permission does not stop the
task but silently prevents logs from reaching CloudWatch — the container may appear to run with no
visible output anywhere.

**Troubleshooting:** check `aws ecs describe-tasks ... --query 'tasks[0].stoppedReason'` first — ECR and
secrets failures are both visible there with a specific error, not just "task stopped."

## 5. ECS task role

**Who assumes it:** your application code running inside the container (via the AWS SDK/CLI's default
credential chain) — **not** the ECS agent.
**When it's used:** any time your application needs to call an AWS API directly (e.g. read from S3,
write to DynamoDB).
**Referenced by:** the task definition's `taskRoleArn` field.

There is no single managed policy for this role — it is always a custom policy scoped to what that
specific application actually needs. Example: a task that only needs to read one S3 prefix:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::<BUCKET_NAME>/<PREFIX>/*"]
    }
  ]
}
```

Trust policy (who is allowed to assume this role) — the task role and the execution role share the same
trust principal, `ecs-tasks.amazonaws.com`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": ["ecs-tasks.amazonaws.com"] },
      "Action": "sts:AssumeRole",
      "Condition": {
        "ArnLike": { "aws:SourceArn": "arn:aws:ecs:<AWS_REGION>:<ACCOUNT_ID>:*" },
        "StringEquals": { "aws:SourceAccount": "<ACCOUNT_ID>" }
      }
    }
  ]
}
```

AWS recommends the `aws:SourceAccount`/`aws:SourceArn` condition keys shown above specifically to
prevent the "confused deputy" problem (a different account's ECS tasks tricking your role into being
assumed) — see References.

**Important distinction confirmed by AWS documentation:** on EC2 (unlike Fargate), containers are **not**
strongly isolated from each other at the task-role-credential level — a container on a shared EC2
instance can potentially access another co-located task's credentials or the instance's own metadata
service unless you've applied the IMDS-blocking mitigations AWS documents for `awsvpc` and `bridge`
modes. This is a real EC2-specific security consideration, not a Fargate one — see §9 and References.

**What happens if permissions are missing:** the application gets an `AccessDenied` error from the AWS
SDK/CLI at the point it calls the API — the task itself still starts and runs; this is purely an
application-level permissions problem, distinguishable from an execution-role failure because the task
is `RUNNING`, not stuck or stopped.

**Troubleshooting:** check CloudTrail for the denied API call — task role sessions carry a `taskArn` in
their session context, so CloudTrail logs show exactly which task the denied call came from.

## 6. EC2 container instance role (instance profile)

**Who assumes it:** the EC2 instance itself (technically, the ECS agent and Docker daemon running on it),
via an EC2 instance profile — **not** anything related to a specific task.
**When it's used:** continuously, for the agent to register the instance into the cluster
(`RegisterContainerInstance`), poll for assigned tasks, and report state — see `fundamentals.md` §5.
**Referenced by:** the EC2 launch template/instance's IAM instance profile — not the task definition.

The AWS managed policy `AmazonEC2ContainerServiceforEC2Role`, exact JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeTags",
        "ecs:CreateCluster",
        "ecs:DeregisterContainerInstance",
        "ecs:DiscoverPollEndpoint",
        "ecs:Poll",
        "ecs:RegisterContainerInstance",
        "ecs:StartTelemetrySession",
        "ecs:UpdateContainerInstancesState",
        "ecs:Submit*",
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "ecs:TagResource",
      "Resource": "*",
      "Condition": {
        "StringEquals": { "ecs:CreateAction": ["CreateCluster", "RegisterContainerInstance"] }
      }
    },
    {
      "Effect": "Allow",
      "Action": ["ecs:ListTagsForResource"],
      "Resource": ["arn:aws:ecs:*:*:task/*/*", "arn:aws:ecs:*:*:container-instance/*/*"]
    }
  ]
}
```

Notice this policy *also* contains ECR pull and CloudWatch Logs write actions, duplicating part of the
task execution role. AWS's own guidance (see References) explicitly recommends narrowing this managed
policy if you don't need every permission in it — e.g. drop `ecs:UpdateContainerInstancesState` if you
don't use Spot Instance draining — and notes that containers on the instance can read this role's
permissions via the EC2 instance metadata service unless mitigated, which is a reason to keep it as
narrow as the cluster genuinely needs.

**What happens if permissions are missing:** the EC2 instance never successfully registers as a
container instance — it simply never appears in `aws ecs list-container-instances`, and the cluster has
no usable capacity from it (see `fundamentals.md` §5 and `instance-capacity-and-placement.md` §6).

**Troubleshooting:** check the ECS agent logs on the instance (`/var/log/ecs/ecs-agent.log` on the
Amazon ECS-optimized AMI) for an access-denied error from `RegisterContainerInstance` or `Poll`.

## 7. ECS service-linked role (`AWSServiceRoleForECS`)

**Who assumes it:** the ECS service itself, internally — this is an AWS "service-linked role," a
special role type predefined by AWS and linked directly to the ECS service, not something you attach to
an EC2 instance or a task.
**When it's used:** when ECS needs to call other AWS services on your behalf to manage a cluster/service
— for example, registering/deregistering targets with an ALB target group during a deployment (see
`networking.md` and `deployment.md`).
**You do not normally create or manage this role's permissions** — AWS creates it automatically the
first time it's needed and maintains the attached `AmazonECSServiceRolePolicy` managed policy.

**What happens if permissions are missing / the role doesn't exist:** cluster or service operations that
depend on ECS calling another service fail — most visibly, ALB target group registration during
deployment fails even though the task definition, task role, and execution role are all correct. This is
a distinct failure mode worth knowing about precisely because it is **not** the task execution role, the
task role, or the instance role — none of which would explain an ALB integration failure.

**Troubleshooting:** if you suspect this role is missing or was deleted, check the IAM console for
`AWSServiceRoleForECS`; AWS documents how to recreate it if needed (see References). This is rarely the
cause of a problem in an account where ECS has been used before, but worth ruling out explicitly rather
than assuming.

## 8. Deployment role (example: GitHub Actions)

**Who assumes it:** your CI/CD pipeline's identity — e.g. a GitHub Actions workflow, via OIDC federation
(`sts:AssumeRoleWithWebIdentity`), not a long-lived IAM user access key.
**When it's used:** when the pipeline builds and pushes an image, registers a new task definition
revision, and updates the service — see `deployment.md` for the full workflow.

This role has no AWS-provided managed policy (it is not an AWS service role) — it is composed from the
specific actions the pipeline performs, each individually documented:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EcrPush",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EcrPushToOneRepo",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage"
      ],
      "Resource": "arn:aws:ecr:<AWS_REGION>:<ACCOUNT_ID>:repository/<project>-<component>"
    },
    {
      "Sid": "EcsDeploy",
      "Effect": "Allow",
      "Action": [
        "ecs:RegisterTaskDefinition",
        "ecs:DescribeTaskDefinition",
        "ecs:DescribeServices",
        "ecs:UpdateService"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassExecutionAndTaskRolesToEcs",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "<EXECUTION_ROLE_ARN>",
        "<TASK_ROLE_ARN>"
      ]
    }
  ]
}
```

- `ecr:GetAuthorizationToken` must use `Resource: "*"` — this specific action does not support
  resource-level restriction (confirmed by AWS ECR documentation).
- `ecs:RegisterTaskDefinition`, `ecs:DescribeTaskDefinition`, `ecs:DescribeServices`, and
  `ecs:UpdateService` are ECS API actions and, as of this writing, are typically granted with
  `Resource: "*"` since ECS resource-level permission support is limited for some of these actions —
  ASSUMPTION flagged: verify current resource-level support before tightening further, since AWS
  periodically expands which ECS actions support resource ARNs.
- `iam:PassRole` is required because `RegisterTaskDefinition`/`UpdateService` pass the execution role and
  task role ARNs to ECS — without it, the deploy fails with an `iam:PassRole`-denied error even though
  every ECS permission above is correct. Scope it to the exact role ARNs the pipeline needs to pass, per
  AWS's documented guidance on `PassRole` (see References) — never `Resource: "*"` for `PassRole`, since
  an overly broad grant would let the pipeline deploy *any* role, including ones with far more access
  than intended.

**What happens if permissions are missing:** the pipeline step fails with an explicit `AccessDenied`
naming the missing action — this is usually the easiest of the five roles to debug, since CI/CD logs
show the exact failing AWS API call.

## 9. Trust policies, identity permissions, permission boundaries, and resource-based policies

These four IAM concepts are often conflated. They answer different questions:

| Concept | Question it answers | Example in this document |
|---|---|---|
| **Identity-based permissions policy** | "What can this role/user do?" | The `AmazonECSTaskExecutionRolePolicy` JSON in §4 |
| **Trust policy** | "Who/what is allowed to assume this role?" | The `ecs-tasks.amazonaws.com` trust policy in §5 — itself a kind of resource-based policy, attached to the role, not to the caller |
| **Permission boundary** | "What is the *maximum* this role/user could ever be granted, even if its identity policy says more?" | Not used in the examples above — an advanced control for limiting what a role can be granted later, e.g. by a less-trusted admin |
| **Resource-based policy** | "Who can access this specific resource, regardless of their own identity policy?" | An ECR repository policy or VPC endpoint policy (see `core/standards/aws-security.md`) — not shown here since this document is about roles, not resource policies |

A role's **effective permissions are the intersection** of what its identity policy allows and what any
permission boundary caps it at — both must allow an action for it to succeed, which is a common source
of "but the policy clearly allows this" confusion when a boundary is also in play.

## 10. Common mistakes

- Attaching secrets/application permissions to the **execution** role instead of the **task** role (or
  vice versa) — the execution role is infrastructure-only; application code never assumes it.
- Forgetting `iam:PassRole` for the deployment role, then being confused by an error that looks unrelated
  to the actual ECS permissions, which were correct.
- Using `AmazonEC2ContainerServiceforEC2Role` unmodified when some of its permissions (e.g. Spot
  draining) aren't needed — AWS explicitly suggests narrowing it, not just accepting the default.
- Assuming the task role protects data between co-located tasks on the same EC2 instance the same way
  Fargate does — it does not, by default, without the IMDS-blocking mitigations (§5, References).
- Granting `iam:PassRole` with `Resource: "*"` "to make the pipeline work" — this defeats the purpose of
  scoping the role in the first place.

## 11. Troubleshooting approach across all five roles

When something fails with "access denied" or a task won't start for a permissions-shaped reason, check
in this order (don't assume which role is at fault before checking):

1. Is the task not starting at all, with an ECR/secrets error in `stoppedReason`? → execution role (§4).
2. Is the task running, but the application gets `AccessDenied` calling an AWS API? → task role (§5).
3. Does the cluster have zero registered container instances even though EC2 instances exist? → instance
   role (§6).
4. Does everything about the task/service look correct, but ALB/target-group integration fails during
   deployment? → service-linked role (§7).
5. Is the failure happening in CI/CD before anything reaches ECS? → deployment role (§8).

## 12. Security considerations

- Every example above uses the narrowest `Resource` the underlying AWS action supports — where `*` is
  used, it is because the action does not support resource-level restriction, and this is called out
  explicitly rather than left silent.
- Never grant `iam:PassRole` with a wildcard resource for a deployment role (§8, §10).
- See `core/standards/aws-security.md` for the general least-privilege and auditability standard this
  document applies to ECS/EC2 specifically.

## 13. References

- ECS task execution IAM role: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-execution-IAM-role.html
- ECS task IAM role: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html
- ECS container instance IAM role: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/instance_IAM_role.html
- ECS service-linked roles: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using-service-linked-roles.html
- AWS managed policies for ECS (index): https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-iam-awsmanpol.html
- `AmazonECSTaskExecutionRolePolicy` JSON: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonECSTaskExecutionRolePolicy.html
- `AmazonEC2ContainerServiceforEC2Role` JSON: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonEC2ContainerServiceforEC2Role.html
- IAM permissions for pushing images to ECR: https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html
- Granting `iam:PassRole`: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html
- The confused deputy problem: https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html

## Related documents

- `task-definitions.md` — where `executionRoleArn` and `taskRoleArn` are set.
- `fundamentals.md` — ECS agent and container instance registration.
- `deployment.md` — GitHub Actions OIDC deployment workflow using the deployment role from §8.
- `core/standards/aws-security.md` — the general IAM/least-privilege standard.
- `core/standards/naming-conventions.md` — role naming pattern used in the examples above.
