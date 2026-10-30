---
title: "Deployment standard"
category: standard
technology: general
status: CONFIRMED
created: 2026-10-30
last_verified: 2026-10-30
source: "General industry practice (see References section)"
---

# Deployment standard

## Purpose

A generic, reusable checklist for deploying changes safely — any workload, any platform. This file
describes the *process*; it does not describe any specific pipeline, environment, or account. Project-specific
deployment procedures (actual pipeline names, actual approval chains, actual rollback commands) belong in
`projects/<project-slug>/deployment.md`.

**Status of this document:** CONFIRMED as general industry practice for safe deployment (see references
for platform-specific mechanics). The approval chain described here is a template — confirm your
organization's actual required approvers before treating it as policy.

## Principles

1. A deployment should be boring: predictable, observable, and reversible.
2. Every deployment has a known-good rollback target before it starts, not improvised after it fails.
3. Verification happens after every deployment, not only when something looks wrong.
4. Production changes require a human approval step that is distinct from "CI passed."

## Pre-deployment checks

- [ ] The correct branch/commit/artifact version is confirmed — not assumed from habit.
- [ ] The diff being deployed has been reviewed (code review, or infrastructure plan review for IaC).
- [ ] All required CI checks passed: tests, linting, security scan (e.g. Trivy for images, Gitleaks for
      secrets), and `terraform plan`/`cdk diff` output reviewed if infrastructure is changing.
- [ ] No unresolved high-severity vulnerability or secret-scan finding on the artifact being deployed.
- [ ] The target environment is explicitly confirmed (not inferred) — wrong-environment deploys are a
      common and avoidable incident class.
- [ ] A rollback path exists and is known *before* deploying (see below).
- [ ] Anyone who needs to be aware (on-call, dependent teams) has been notified if the change is
      significant.

**Common mistake:** treating "CI is green" as equivalent to "safe to deploy to production." CI validates
the artifact; it does not validate that this is the right time, environment, or approver.

## Deployment verification

After every deployment, verify — do not assume success because the deploy command returned without error:

- [ ] Service/task health checks are passing (e.g. ECS service reaches steady state, ALB targets healthy).
- [ ] Application logs show no new error patterns since the deployment started.
- [ ] Key metrics (latency, error rate, CPU/memory, queue depth) are within expected range post-deploy.
- [ ] A smoke test or synthetic check exercises the critical path, not just a `/health` endpoint.
- [ ] If the platform supports gradual rollout (e.g. ECS rolling deployment, Kubernetes rollout), confirm
      the new revision actually reached 100% of desired count/replicas, not just "deployment started."

Record the actual verification outcome in the relevant runbook or changelog entry — per `AGENTS.md`,
never claim a deployment succeeded without evidence.

## Rollback planning

- Know the rollback mechanism *before* you need it: previous task definition revision, previous image
  tag, previous Terraform state/plan, or a feature flag — whichever applies to the platform.
- Prefer deployment mechanisms with a built-in automatic rollback trigger (e.g. ECS deployment circuit
  breaker, Kubernetes readiness-gated rollout) over manual-only rollback for production services.
- A rollback is itself a change: treat it with the same verification step (confirm service health after
  rolling back, don't assume reverting fixes things).
- If rollback is not possible for a given change (e.g. a destructive database migration), say so
  explicitly before deploying and get separate, explicit approval for that risk.
- Document the rollback outcome, not just that rollback was attempted.

## Production change approval

- Production-impacting changes require sign-off from a human who is not the sole author of the change,
  unless your organization has an explicitly documented exception (e.g. solo-maintainer project).
- Use protected branches/environments with required reviewers for production deployment pipelines (see
  `core/patterns/github-actions.md` for the CI/CD security checklist this pairs with).
- Infrastructure changes (Terraform apply, IAM policy changes, security group changes, DNS changes) get
  the same approval bar as application deployments — often higher, since they're harder to reverse. See
  `core/patterns/terraform.md`.
- An AI agent may propose a deployment plan or diff. It does not have authority to approve or execute a
  production change — see `AGENTS.md` and `core/standards/change-safety.md`.
- Record who approved a production change and when, even briefly (e.g. in the PR, the changelog, or the
  runbook's "Evidence and update history" section).

## Security considerations

- Deployment credentials (CI → cloud) should be scoped separately from build/test credentials, and
  should prefer short-lived OIDC federation over long-lived access keys — see
  `core/patterns/github-actions.md` and `core/standards/aws-security.md`.
- Never let a deployment pipeline print secret values to logs, even for debugging.
- Restrict who can trigger a production deployment workflow (protected environment + required reviewers),
  not just who can merge to the branch that triggers it.

## Troubleshooting

- Deployment stuck "in progress" → check whether health checks are failing (app issue) or whether the
  platform can't place new capacity (infrastructure issue) — these have different fixes; don't assume
  one root cause.
- Rollback didn't restore expected behavior → confirm you rolled back *all* coupled changes (app version,
  config, schema) — a partial rollback can leave the system in a new, unverified state.

## References

- ECS deployment types and circuit breaker: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html
- GitHub Actions environments and required reviewers: https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment
- Terraform plan/apply workflow: https://developer.hashicorp.com/terraform/tutorials/cli/plan

## Related documents

- `core/standards/change-safety.md` — the general principle this file specializes for deployments.
- `core/standards/aws-security.md` — security controls relevant during deployment.
- `core/patterns/github-actions.md` — CI/CD-specific security checklist.
- `core/patterns/terraform.md` — infrastructure-change-specific checklist.
- `templates/runbook.md` — the template used to document any specific deployment procedure.
