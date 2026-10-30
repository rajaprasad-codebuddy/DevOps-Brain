---
title: "AWS security standard"
category: standard
technology: aws
status: CONFIRMED
created: 2026-10-30
last_verified: 2026-10-30
source: "AWS/industry best practice (see References section)"
---

# AWS security standard

## Purpose

Generic, reusable security principles for any AWS workload documented in this Brain. This file covers
shared expectations; it does not describe any specific account, resource, or customer environment.
Project-specific security facts (actual role ARNs, actual security group IDs, actual findings) belong
in `projects/<project-slug>/security.md`, not here.

**Status of this document:** CONFIRMED as general AWS/industry best practice (see references). It is not
a substitute for your organization's actual security policy — confirm that policy before applying these
principles to a real account.

## Principles

1. Least privilege by default — grant only the permissions a role needs, scoped to the resources it
   needs, nothing more.
2. No long-lived credentials where a short-lived or federated alternative exists.
3. Secrets are referenced, never embedded — in code, in Terraform, or in this Brain.
4. Encrypt data at rest and in transit by default, not as an exception.
5. Network access is deny-by-default; open only what a component demonstrably needs.
6. Every privileged or state-changing action should be attributable to an identity and visible in logs.

## IAM and least privilege

- Start from an empty policy and add only the actions a role needs to do its job. Avoid `"Action": "*"`
  and `"Resource": "*"` outside of narrowly scoped, time-boxed break-glass roles.
- Prefer AWS-managed policies only for quick prototyping; for anything durable, write a scoped
  customer-managed policy.
- Use IAM roles for workloads (EC2 instance profiles, ECS task roles, Lambda execution roles) instead of
  long-lived IAM user access keys. See `core/patterns/aws/ecs/iam-roles-and-permissions.md` for the ECS-specific
  role breakdown — this file only covers the general pattern.
- Use `Condition` blocks to narrow permissions further: source IP, VPC endpoint, tag-based access,
  `aws:RequestedRegion`, MFA presence for sensitive actions.
- Separate duties: the identity that can deploy infrastructure should not necessarily be the identity
  that can read application secrets, and vice versa.

**Example — scoped least-privilege policy for a role that only needs to read one S3 prefix:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyOneBucketPrefix",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::<BUCKET_NAME>",
        "arn:aws:s3:::<BUCKET_NAME>/<PREFIX>/*"
      ],
      "Condition": {
        "StringLike": { "s3:prefix": ["<PREFIX>/*"] }
      }
    }
  ]
}
```

Replace `<BUCKET_NAME>` and `<PREFIX>` with real values only in a project-specific document, never here.

**Common mistake:** attaching `AdministratorAccess` or a wildcard policy "temporarily" during
development and forgetting to narrow it before the role is used for anything persistent.

## Secrets management

- Store secrets in AWS Secrets Manager or SSM Parameter Store (SecureString), not in environment files,
  task definitions, Terraform variables files, or this Brain.
- Grant read access to a specific secret ARN, not `secretsmanager:GetSecretValue` on `*`.
- Rotate secrets on a defined schedule or via Secrets Manager automatic rotation where supported.
- It is acceptable to record a secret's **logical name or ARN** in documentation if necessary to explain
  architecture (e.g. "the task reads `DATABASE_PASSWORD` from `<SECRET_ARN>`"). Never record the secret
  **value**. See `SECURITY.md` for the full rule.
- Treat any secret that was ever committed to Git as exposed, even after deletion — rotate it.

## Encryption

- Encrypt data at rest: enable encryption on S3 buckets, EBS volumes, RDS instances, and Secrets
  Manager/SSM by default (most are encrypted by default today, but verify for older resources).
- Prefer customer-managed KMS keys over AWS-managed keys when you need audit control over who can
  decrypt, or need to restrict key usage to specific roles.
- Encrypt data in transit: use TLS for ALB listeners, RDS connections, and any service-to-service calls
  crossing a network boundary you don't fully control.
- Do not disable encryption "for performance" without a measured, documented reason — AWS encryption at
  rest has negligible overhead for most workloads.

## Network security

- Place workloads in private subnets by default; only put a resource in a public subnet if it must be
  directly internet-reachable (e.g. an ALB, a NAT gateway, a bastion).
- Security groups should allow only the specific port and source needed — avoid `0.0.0.0/0` on anything
  other than a public-facing load balancer's listener port (80/443).
- Use security-group-to-security-group references instead of CIDR ranges when traffic is between your
  own components — it survives IP/subnet changes and documents intent.
- Use VPC endpoints (interface or gateway) for AWS service traffic (S3, ECR, Secrets Manager, CloudWatch
  Logs) that should not traverse the public internet via a NAT gateway.
- Review security groups and NACLs periodically for unused, overly broad rules — "temporary" rules tend
  to outlive their justification.

## Auditability

- Enable CloudTrail in all regions and send logs to a dedicated, restricted-access account or bucket if
  your organization operates multiple accounts.
- Enable AWS Config to track resource configuration drift and evaluate compliance rules.
- Enable GuardDuty for threat detection and Security Hub to aggregate findings if your organization uses
  them — treat findings as input to a human review process, not an auto-remediation trigger, unless that
  has been explicitly designed and approved.
- Tag resources consistently (see `core/standards/naming-conventions.md`) so that CloudTrail and billing
  data can be attributed to an owner, environment, and project.
- Log who approved a production change, not just that CI ran — see `core/standards/deployment-standards.md`.

## Troubleshooting pointers

- "Access denied" on a role that should have access → check for an explicit `Deny` elsewhere (SCP,
  permissions boundary, resource policy) before widening the role's own policy.
- Secret not resolving in a running task/instance → confirm the execution role (not just the task/app
  role) has `secretsmanager:GetSecretValue` / `ssm:GetParameters` on that specific ARN.
- Unexpected public exposure → check security groups, NACLs, S3 bucket policies/ACLs, and (for S3)
  account- and bucket-level Block Public Access settings together; any one of them can be the gap.

## Security considerations

This document is itself a security control: never let its examples drift into real values. Any pull
request that adds a real account ID, ARN, security group ID, or secret value to this file should be
rejected per `SECURITY.md`.

## References

- IAM best practices: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
- Secrets Manager: https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html
- Data encryption at rest (KMS): https://docs.aws.amazon.com/kms/latest/developerguide/overview.html
- VPC security groups: https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html
- VPC endpoints: https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints.html
- CloudTrail: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-user-guide.html
- AWS Config: https://docs.aws.amazon.com/config/latest/developerguide/WhatIsConfig.html

## Related documents

- `SECURITY.md` — repository-wide rule on what must never be stored.
- `AGENTS.md` — AI agent security rules (no cloud mutation, no secret retrieval).
- `core/standards/change-safety.md` — general change-safety standard this file specializes for AWS.
- `core/standards/deployment-standards.md` — deployment-time approval and verification.
- `core/standards/naming-conventions.md` — consistent, auditable resource naming/tagging.
