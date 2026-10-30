---
title: "Naming conventions standard"
category: standard
technology: general
status: ASSUMPTION
created: 2026-10-30
last_verified: 2026-10-30
source: "Recommended convention — not an AWS-enforced standard (see References section)"
---

# Naming conventions standard

## Purpose

Consistent, predictable names make resources easier to find, audit, and tie back to CloudTrail/billing
data. This file defines generic naming *patterns* with placeholders — it does not define any real
project's actual names. Real resource names belong in `projects/<project-slug>/` documents.

**Status of this document:** ASSUMPTION / recommended convention, not an AWS-enforced standard. AWS does
not require any particular naming scheme (with a few hard constraints noted below); these patterns are a
common, reusable practice. Confirm against your organization's actual naming policy before applying it
to real resources — if one doesn't exist yet, this file is a reasonable default to propose.

## Principles

1. A name should tell you what it is, which project it belongs to, and which environment it's in,
   without needing to open the resource.
2. Prefer lowercase-with-hyphens for anything AWS or Docker treats as a string identifier; reserve
   UPPER_SNAKE_CASE for environment variables only.
3. Put the environment and project in a fixed position so names sort and filter predictably.
4. Tags carry structured metadata; names carry only what's needed for human scanning — don't try to
   encode everything into the name itself.

## General pattern

```text
<project>-<component>-<environment>[-<region-or-index>]
```

- `<project>`: short, stable slug for the project (matches the `projects/<project-slug>/` directory name).
- `<component>`: what this resource is for, e.g. `api`, `worker`, `db`, `cache`.
- `<environment>`: `dev`, `staging`, `prod` (or your organization's equivalent — confirm before using).
- `<region-or-index>`: optional, only when a name must disambiguate across regions or multiple instances.

Example (placeholders only): `<project>-api-prod`, `<project>-worker-staging`.

## AWS resource naming

| Resource | Pattern | Example (placeholder) |
|---|---|---|
| VPC | `<project>-vpc-<env>` | `<project>-vpc-prod` |
| Subnet | `<project>-subnet-<tier>-<az>-<env>` | `<project>-subnet-private-a-prod` |
| Security group | `<project>-sg-<purpose>-<env>` | `<project>-sg-alb-prod` |
| S3 bucket | `<project>-<purpose>-<env>-<account-id-or-random-suffix>` | `<project>-logs-prod-<SUFFIX>` |
| RDS instance | `<project>-<engine>-<env>` | `<project>-postgres-prod` |
| Secrets Manager secret | `<project>/<env>/<component>/<secret-name>` | `<project>/prod/api/database-password` |

**S3 bucket names are globally unique** across all AWS accounts, so a disambiguating suffix (account ID
fragment or random string) is often necessary — this is an AWS hard constraint, not a style choice.

## Terraform resource naming

- Terraform **resource addresses** (the identifier after the resource type, e.g.
  `resource "aws_instance" "this"`) should describe role, not environment — environment is handled by
  workspace/state separation, not by baking it into the Terraform identifier.
  - Prefer a short, generic local name like `this` or `main` when there's only one instance of that
    resource type in the module; use a descriptive name (`api`, `worker`) when there are several.
- The **AWS-side name** you pass via a `name` argument or tag should follow the AWS pattern above and
  typically comes from an input variable (e.g. `var.project`, `var.environment`), not a literal.
- Module names: short, lowercase-with-hyphens, describing what the module provisions (e.g.
  `ecs-service`, `vpc-baseline`) — avoid encoding a specific project name into a *reusable* module name.
- See `core/patterns/terraform.md` for the broader Terraform checklist this complements.

## Docker image naming

```text
<registry>/<project>-<component>:<tag>
```

- `<registry>`: e.g. an ECR repository URI — keep as a placeholder (`<ECR_REPO_URI>`) outside of
  project-specific docs.
- `<tag>`: prefer an immutable, traceable tag — a Git SHA or a semantic version — over `latest` for
  anything deployed. `latest` is fine for local development only.
- Example (placeholder): `<ECR_REPO_URI>/<project>-api:<GIT_SHA>`.

**Common mistake:** deploying `:latest` to production. It's not traceable to a specific commit and makes
rollback ambiguous — always deploy a specific, immutable tag.

## ECS naming

| Resource | Pattern | Example (placeholder) |
|---|---|---|
| ECS cluster | `<project>-cluster-<env>` | `<project>-cluster-prod` |
| ECS service | `<project>-<component>-svc-<env>` | `<project>-api-svc-prod` |
| Task definition family | `<project>-<component>-<env>` | `<project>-api-prod` |
| Container name (within task def) | `<component>` | `api` |

The task definition **family** name is what you reference when deploying a new revision — keep it stable
across revisions (ECS appends the revision number automatically, e.g. `<project>-api-prod:7`).

## IAM role naming

```text
<project>-<role-purpose>-<env>
```

| Role type | Example (placeholder) |
|---|---|
| EC2 instance profile role | `<project>-ec2-instance-role-<env>` |
| ECS task execution role | `<project>-ecs-task-execution-role-<env>` |
| ECS task role | `<project>-<component>-task-role-<env>` |
| CI/CD deployment role (OIDC) | `<project>-deploy-role-<env>` |

Naming the role by *purpose* (what it's allowed to do) rather than by *which service happens to assume
it today* makes least-privilege review easier later — see `core/standards/aws-security.md`.

## Environment-specific resources

- Keep the environment token (`dev` / `staging` / `prod`) consistent across every resource type for the
  same logical environment — don't mix `production` in one place and `prod` in another.
- Never let an environment-specific name imply it's safe to copy into another environment's config
  wholesale; names should make cross-environment copy-paste mistakes visible, not easy.
- Tag every resource with at least: `Project`, `Environment`, `Owner` (team or role, not a real person's
  name unless your organization's tagging policy requires it), and `ManagedBy` (e.g. `terraform` vs.
  manual). This supports the auditability principle in `core/standards/aws-security.md`.

## Security considerations

- Do not encode secret values, account IDs, or customer names into resource names "for clarity" — a
  name is visible in CloudTrail, billing exports, and often in error messages; treat it as semi-public
  within the account.
- A predictable naming scheme also makes IAM policy scoping easier (e.g. `Resource: arn:aws:s3:::<project>-*`)
  — but keep in mind wildcard resource matches still need a narrow enough prefix to avoid accidentally
  granting access to a sibling project's resources.

## References

- S3 bucket naming rules: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
- Tagging AWS resources: https://docs.aws.amazon.com/tag-editor/latest/userguide/tagging.html
- ECS task definition families and revisions: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html
- Terraform naming conventions (community style guide, not an AWS/HashiCorp hard rule): https://developer.hashicorp.com/terraform/language/syntax/style

## Related documents

- `core/standards/aws-security.md` — why consistent naming/tagging supports auditability.
- `core/standards/deployment-standards.md` — immutable image tags as part of safe deployment.
- `core/patterns/terraform.md` — broader Terraform checklist.
- `projects/README.md` — project slug convention that this file's `<project>` placeholder refers to.
